from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import threading
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPOSITORY = "colazeta/italian-anti-mafia-whitelist"
MANIFEST_URL = (
    "https://raw.githubusercontent.com/"
    + REPOSITORY
    + "/main/data/publication/public_snapshot.json"
)
RELEASE_BASE = "https://github.com/" + REPOSITORY + "/releases/download/{tag}"
ROBOTS_URL = (
    "https://raw.githubusercontent.com/"
    + REPOSITORY
    + "/main/public-site/data/robots.json"
)

STATUSES = frozenset(
    {
        "listed",
        "pending",
        "renewal_update_in_progress",
        "renewal_requested",
        "expired_observed",
        "rejected_or_denied",
        "cancellation_related",
        "other_or_unknown",
    }
)

REGISTRY_FIELDS = (
    "record_locator",
    "authority_name",
    "register_name",
    "reference_date",
    "name",
    "registered_office",
    "secondary_office",
    "identifiers",
    "requested_activities",
    "source_status",
    "primary_date_label",
    "primary_date",
    "application_date",
    "observed_listing_date",
    "decision_date",
    "registration_date",
    "observed_expiry_date",
    "outcome_raw",
    "source_page_url",
    "resource_url",
    "capture_sha256",
)

PUBLIC_ROW_FIELDS = REGISTRY_FIELDS + ("authority_key",)

LEGAL_NOTE = (
    "These are source-backed observations from the reviewed public archive. "
    "They are not a nationally deduplicated company register and do not by themselves "
    "certify an enterprise's present legal or administrative status."
)


class SnapshotError(RuntimeError):
    pass


def normalise_text(value: str) -> str:
    folded = (
        unicodedata.normalize("NFKD", str(value or ""))
        .encode("ascii", "ignore")
        .decode("ascii")
        .casefold()
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", folded).split())


def normalise_identifier(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKC", str(value or "")).upper())


def _is_identifier_query(value: str) -> bool:
    normalised = normalise_identifier(value)
    return bool(re.fullmatch(r"(?:\d{11}|[A-Z0-9]{16})", normalised))


class SnapshotStore:
    """Read-only query layer over the selected reviewed public snapshot.

    The selected release is always read from public_snapshot.json. A previously
    verified local cache remains usable if GitHub is temporarily unavailable;
    every response discloses which release actually backed the answer.
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        *,
        manifest_url: str = MANIFEST_URL,
        release_base: str = RELEASE_BASE,
        robots_url: str = ROBOTS_URL,
        refresh_seconds: int = 300,
    ) -> None:
        self.cache_dir = Path(
            cache_dir
            or os.environ.get("WHITELIST_MCP_CACHE_DIR")
            or "/tmp/whitelist-explorer"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_url = manifest_url
        self.release_base = release_base
        self.robots_url = robots_url
        self.refresh_seconds = max(30, int(refresh_seconds))
        self.db_path = self.cache_dir / "registry.sqlite3"
        self.manifest_path = self.cache_dir / "manifest.json"
        self.prefectures_path = self.cache_dir / "prefectures.json"
        self.history_path = self.cache_dir / "history.json"
        self.robots_path = self.cache_dir / "robots.json"
        self._lock = threading.RLock()
        self._last_checked = 0.0
        self._robots_last_checked = 0.0
        self._release_tag: str | None = None
        self._last_refresh_error: str | None = None
        self._robots_refresh_error: str | None = None
        self._hydrate_local_state()

    def _hydrate_local_state(self) -> None:
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            self._validate_manifest(manifest)
            if self.db_path.exists() and self.prefectures_path.exists() and self.history_path.exists():
                self._release_tag = str(manifest["release_tag"])
        except (OSError, ValueError, json.JSONDecodeError, KeyError):
            self._release_tag = None

    @staticmethod
    def _validate_manifest(manifest: dict[str, Any]) -> None:
        expected_files = {
            "registry.json",
            "registry.csv",
            "prefectures.json",
            "prefectures.csv",
            "history.json",
        }
        if (
            set(manifest) != {"schema_version", "repository", "release_tag", "files"}
            or manifest.get("schema_version") != 1
            or manifest.get("repository") != REPOSITORY
            or not re.fullmatch(r"public-data-[A-Za-z0-9.-]+", str(manifest.get("release_tag") or ""))
            or set(manifest.get("files", {})) != expected_files
        ):
            raise SnapshotError("Unapproved public snapshot manifest")
        for name, item in manifest["files"].items():
            if (
                set(item) != {"sha256", "bytes"}
                or not re.fullmatch(r"[a-f0-9]{64}", str(item.get("sha256") or ""))
                or type(item.get("bytes")) is not int
                or not 0 < item["bytes"] <= 300_000_000
            ):
                raise SnapshotError(f"Invalid public snapshot entry: {name}")

    @staticmethod
    def _request(url: str, timeout: int = 120):
        return urlopen(
            Request(url, headers={"User-Agent": "whitelist-explorer-mcp/0.2"}),
            timeout=timeout,
        )

    def _fetch_bytes(self, url: str, *, limit: int = 5_000_000, timeout: int = 60) -> bytes:
        error: Exception | None = None
        for attempt in range(3):
            try:
                with self._request(url, timeout=timeout) as response:
                    body = response.read(limit + 1)
                if len(body) > limit:
                    raise SnapshotError(f"Remote resource exceeds safety limit: {url}")
                return body
            except (HTTPError, URLError, TimeoutError, ConnectionError, OSError) as exc:
                error = exc
                if attempt < 2:
                    time.sleep(attempt + 1)
        raise SnapshotError(f"Unable to fetch {url}: {type(error).__name__}") from error

    def _fetch_json(self, url: str, *, limit: int = 5_000_000) -> dict[str, Any]:
        try:
            value = json.loads(self._fetch_bytes(url, limit=limit).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SnapshotError(f"Invalid JSON from {url}") from exc
        if not isinstance(value, dict):
            raise SnapshotError(f"JSON object expected from {url}")
        return value

    def _download_snapshot_file(
        self,
        manifest: dict[str, Any],
        name: str,
        destination: Path,
    ) -> None:
        item = manifest["files"][name]
        url = f"{self.release_base.format(tag=manifest['release_tag'])}/{name}.gz"
        expected_bytes = int(item["bytes"])
        expected_sha = str(item["sha256"])
        temp_path = destination.with_suffix(destination.suffix + ".tmp")
        digest = hashlib.sha256()
        total = 0
        try:
            with self._request(url, timeout=180) as response:
                with gzip.GzipFile(fileobj=response) as source:
                    with temp_path.open("wb") as output:
                        while True:
                            chunk = source.read(1024 * 1024)
                            if not chunk:
                                break
                            total += len(chunk)
                            if total > expected_bytes:
                                raise SnapshotError(f"Snapshot size mismatch for {name}")
                            digest.update(chunk)
                            output.write(chunk)
            if total != expected_bytes or digest.hexdigest() != expected_sha:
                raise SnapshotError(f"Snapshot integrity mismatch for {name}")
            temp_path.replace(destination)
        finally:
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def _authority_key_for_name(authority_name: str, prefectures: list[dict[str, Any]]) -> str:
        target = normalise_text(authority_name)
        matches: list[tuple[int, str]] = []
        for item in prefectures:
            jurisdiction = normalise_text(str(item.get("jurisdiction_name") or ""))
            if jurisdiction and jurisdiction in target:
                matches.append((len(jurisdiction), str(item.get("authority_key") or "")))
        matches = [item for item in matches if item[1]]
        if not matches:
            return ""
        matches.sort(reverse=True)
        if len(matches) > 1 and matches[0][0] == matches[1][0] and matches[0][1] != matches[1][1]:
            return ""
        return matches[0][1]

    def _build_database(
        self,
        registry_csv: Path,
        prefectures: dict[str, Any],
        output: Path,
    ) -> None:
        rows = prefectures.get("prefectures")
        if not isinstance(rows, list):
            raise SnapshotError("Invalid Prefecture index")
        output.unlink(missing_ok=True)
        connection = sqlite3.connect(output)
        try:
            connection.execute("PRAGMA journal_mode=OFF")
            connection.execute("PRAGMA synchronous=OFF")
            connection.execute("PRAGMA temp_store=MEMORY")
            columns = ", ".join(f'"{name}" TEXT NOT NULL DEFAULT \'\'' for name in REGISTRY_FIELDS)
            connection.execute(
                f"""
                CREATE TABLE registry (
                    {columns},
                    authority_key TEXT NOT NULL DEFAULT '',
                    name_norm TEXT NOT NULL,
                    identifiers_norm TEXT NOT NULL,
                    search_norm TEXT NOT NULL
                )
                """
            )
            placeholders = ",".join("?" for _ in range(len(REGISTRY_FIELDS) + 4))
            insert_sql = f"INSERT INTO registry VALUES ({placeholders})"
            batch: list[tuple[str, ...]] = []
            with registry_csv.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                missing = set(REGISTRY_FIELDS) - set(reader.fieldnames or [])
                if missing:
                    raise SnapshotError(f"Registry CSV missing fields: {sorted(missing)}")
                for source in reader:
                    values = tuple(str(source.get(field) or "") for field in REGISTRY_FIELDS)
                    authority_key = self._authority_key_for_name(source.get("authority_name", ""), rows)
                    name_norm = normalise_text(source.get("name", ""))
                    identifiers_norm = normalise_identifier(source.get("identifiers", ""))
                    search_norm = normalise_text(
                        " ".join(
                            str(source.get(field) or "")
                            for field in (
                                "name",
                                "registered_office",
                                "secondary_office",
                                "identifiers",
                                "requested_activities",
                                "outcome_raw",
                                "authority_name",
                                "register_name",
                                "reference_date",
                                "application_date",
                                "observed_listing_date",
                                "decision_date",
                                "registration_date",
                                "observed_expiry_date",
                            )
                        )
                    )
                    batch.append(values + (authority_key, name_norm, identifiers_norm, search_norm))
                    if len(batch) >= 2000:
                        connection.executemany(insert_sql, batch)
                        batch.clear()
                if batch:
                    connection.executemany(insert_sql, batch)
            connection.execute("CREATE UNIQUE INDEX idx_registry_locator ON registry(record_locator)")
            connection.execute("CREATE INDEX idx_registry_authority ON registry(authority_key)")
            connection.execute("CREATE INDEX idx_registry_status ON registry(source_status)")
            connection.execute("CREATE INDEX idx_registry_reference_date ON registry(reference_date)")
            connection.execute("CREATE INDEX idx_registry_application_date ON registry(application_date)")
            connection.execute("CREATE INDEX idx_registry_expiry_date ON registry(observed_expiry_date)")
            connection.commit()
        finally:
            connection.close()

    def _install_release(self, manifest: dict[str, Any]) -> None:
        with tempfile.TemporaryDirectory(prefix="whitelist-mcp-", dir=self.cache_dir) as directory:
            stage = Path(directory)
            registry_csv = stage / "registry.csv"
            prefectures_path = stage / "prefectures.json"
            history_path = stage / "history.json"
            self._download_snapshot_file(manifest, "registry.csv", registry_csv)
            self._download_snapshot_file(manifest, "prefectures.json", prefectures_path)
            self._download_snapshot_file(manifest, "history.json", history_path)
            prefectures = json.loads(prefectures_path.read_text(encoding="utf-8"))
            history = json.loads(history_path.read_text(encoding="utf-8"))
            if not isinstance(prefectures, dict) or not isinstance(prefectures.get("prefectures"), list):
                raise SnapshotError("Invalid Prefecture index payload")
            if (
                not isinstance(history, dict)
                or history.get("version") != 1
                or any(not isinstance(history.get(key), list) for key in ("editions", "checks", "comparisons"))
            ):
                raise SnapshotError("Invalid public history payload")
            db_path = stage / "registry.sqlite3"
            self._build_database(registry_csv, prefectures, db_path)
            db_path.replace(self.db_path)
            prefectures_path.replace(self.prefectures_path)
            history_path.replace(self.history_path)
            temp_manifest = stage / "manifest.json"
            temp_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            temp_manifest.replace(self.manifest_path)
        self._release_tag = str(manifest["release_tag"])

    def ensure(self, *, force: bool = False) -> None:
        with self._lock:
            now = time.monotonic()
            if (
                not force
                and self._release_tag
                and self.db_path.exists()
                and now - self._last_checked < self.refresh_seconds
            ):
                return
            try:
                manifest = self._fetch_json(self.manifest_url, limit=100_000)
                self._validate_manifest(manifest)
                required = self.db_path.exists() and self.prefectures_path.exists() and self.history_path.exists()
                if str(manifest["release_tag"]) != self._release_tag or not required:
                    self._install_release(manifest)
                self._last_refresh_error = None
            except Exception as exc:
                self._last_refresh_error = f"{type(exc).__name__}: {exc}"
                if not (
                    self._release_tag
                    and self.db_path.exists()
                    and self.prefectures_path.exists()
                    and self.history_path.exists()
                ):
                    raise
            finally:
                self._last_checked = now

    def _connect(self) -> sqlite3.Connection:
        self.ensure()
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _load_prefectures(self) -> dict[str, Any]:
        self.ensure()
        return json.loads(self.prefectures_path.read_text(encoding="utf-8"))

    def _load_history(self) -> dict[str, Any]:
        self.ensure()
        return json.loads(self.history_path.read_text(encoding="utf-8"))

    def _provenance(self) -> dict[str, Any]:
        self.ensure()
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return {
            "repository": REPOSITORY,
            "snapshot_selector": self.manifest_url,
            "release_tag": manifest["release_tag"],
            "cache_refresh_error": self._last_refresh_error,
            "interpretation": LEGAL_NOTE,
        }

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, str]:
        return {field: str(row[field] or "") for field in PUBLIC_ROW_FIELDS}

    def _resolve_authority(self, value: str) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
        query = normalise_text(value)
        if not query:
            return None, []
        prefectures = self._load_prefectures().get("prefectures", [])
        exact: list[dict[str, Any]] = []
        partial: list[dict[str, Any]] = []
        for row in prefectures:
            key = normalise_text(str(row.get("authority_key") or ""))
            jurisdiction = normalise_text(str(row.get("jurisdiction_name") or ""))
            labels = {key, jurisdiction, normalise_text("Prefettura di " + str(row.get("jurisdiction_name") or ""))}
            if query in labels:
                exact.append(row)
            elif query and (query in jurisdiction or query in key):
                partial.append(row)
        candidates = exact or partial
        if len(candidates) == 1:
            return candidates[0], []
        return None, [
            {
                "authority_key": str(item.get("authority_key") or ""),
                "jurisdiction_name": str(item.get("jurisdiction_name") or ""),
            }
            for item in candidates[:20]
        ]

    def search_registry(
        self,
        query: str = "",
        *,
        authority: str | None = None,
        status: str | None = None,
        register: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit), 100))
        offset = max(0, min(int(offset), 10_000))
        clauses: list[str] = []
        params: list[Any] = []
        match_basis = "filters_only"
        query = str(query or "").strip()
        if query:
            if _is_identifier_query(query):
                identifier = normalise_identifier(query)
                clauses.append("instr(identifiers_norm, ?) > 0")
                params.append(identifier)
                match_basis = "identifier"
            else:
                clauses.append("instr(search_norm, ?) > 0")
                params.append(normalise_text(query))
                match_basis = "text"
        authority_resolution = None
        if authority:
            resolved, candidates = self._resolve_authority(authority)
            if not resolved:
                return {
                    "error": "authority_ambiguous_or_unknown",
                    "query": authority,
                    "candidates": candidates,
                    "provenance": self._provenance(),
                }
            authority_resolution = {
                "authority_key": resolved["authority_key"],
                "jurisdiction_name": resolved["jurisdiction_name"],
            }
            clauses.append("authority_key = ?")
            params.append(resolved["authority_key"])
        if status:
            if status not in STATUSES:
                return {
                    "error": "invalid_status",
                    "allowed_statuses": sorted(STATUSES),
                    "provenance": self._provenance(),
                }
            clauses.append("source_status = ?")
            params.append(status)
        if register:
            clauses.append("instr(search_norm, ?) > 0")
            params.append(normalise_text(register))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as connection:
            total = connection.execute(f"SELECT COUNT(*) FROM registry{where}", params).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT {", ".join(PUBLIC_ROW_FIELDS)}
                FROM registry
                {where}
                ORDER BY name_norm, authority_name, register_name, reference_date DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        return {
            "query": query,
            "match_basis": match_basis,
            "filters": {
                "authority": authority_resolution,
                "status": status,
                "register": register,
            },
            "total_matches": total,
            "offset": offset,
            "limit": limit,
            "results": [self._row(row) for row in rows],
            "provenance": self._provenance(),
        }

    def get_observation(self, record_locator: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT {', '.join(PUBLIC_ROW_FIELDS)} FROM registry WHERE record_locator = ?",
                (record_locator,),
            ).fetchone()
        return {
            "record_locator": record_locator,
            "observation": self._row(row) if row else None,
            "found": row is not None,
            "provenance": self._provenance(),
        }

    def get_prefecture(self, authority: str) -> dict[str, Any]:
        resolved, candidates = self._resolve_authority(authority)
        if not resolved:
            return {
                "error": "authority_ambiguous_or_unknown",
                "query": authority,
                "candidates": candidates,
                "provenance": self._provenance(),
            }
        key = str(resolved["authority_key"])
        with self._connect() as connection:
            status_counts = dict(
                connection.execute(
                    """
                    SELECT source_status, COUNT(*)
                    FROM registry
                    WHERE authority_key = ?
                    GROUP BY source_status
                    ORDER BY source_status
                    """,
                    (key,),
                ).fetchall()
            )
            aggregate = connection.execute(
                """
                SELECT COUNT(*) AS records,
                       MIN(NULLIF(reference_date, '')) AS earliest_reference_date,
                       MAX(NULLIF(reference_date, '')) AS latest_reference_date,
                       COUNT(DISTINCT register_name) AS register_count
                FROM registry
                WHERE authority_key = ?
                """,
                (key,),
            ).fetchone()
        return {
            "prefecture": resolved,
            "archive": {
                "record_count": int(aggregate["records"]),
                "register_count": int(aggregate["register_count"]),
                "earliest_reference_date": aggregate["earliest_reference_date"],
                "latest_reference_date": aggregate["latest_reference_date"],
                "status_counts": status_counts,
            },
            "provenance": self._provenance(),
        }

    def compare_prefectures(
        self,
        authorities: list[str],
        *,
        status: str | None = None,
    ) -> dict[str, Any]:
        if not authorities:
            return {"error": "at_least_one_authority_required", "provenance": self._provenance()}
        if len(authorities) > 20:
            return {"error": "too_many_authorities", "maximum": 20, "provenance": self._provenance()}
        if status and status not in STATUSES:
            return {
                "error": "invalid_status",
                "allowed_statuses": sorted(STATUSES),
                "provenance": self._provenance(),
            }
        output: list[dict[str, Any]] = []
        for value in authorities:
            resolved, candidates = self._resolve_authority(value)
            if not resolved:
                output.append({"query": value, "error": "authority_ambiguous_or_unknown", "candidates": candidates})
                continue
            key = str(resolved["authority_key"])
            clause = "authority_key = ?"
            params: list[Any] = [key]
            if status:
                clause += " AND source_status = ?"
                params.append(status)
            with self._connect() as connection:
                row = connection.execute(
                    f"""
                    SELECT COUNT(*) AS records,
                           COUNT(DISTINCT register_name) AS register_count,
                           MIN(NULLIF(reference_date, '')) AS earliest_reference_date,
                           MAX(NULLIF(reference_date, '')) AS latest_reference_date
                    FROM registry
                    WHERE {clause}
                    """,
                    params,
                ).fetchone()
                statuses = dict(
                    connection.execute(
                        """
                        SELECT source_status, COUNT(*)
                        FROM registry
                        WHERE authority_key = ?
                        GROUP BY source_status
                        ORDER BY source_status
                        """,
                        (key,),
                    ).fetchall()
                )
            output.append(
                {
                    "authority_key": key,
                    "jurisdiction_name": resolved["jurisdiction_name"],
                    "mapping_status": resolved.get("mapping_status"),
                    "published_registers": resolved.get("published_registers", []),
                    "record_count": int(row["records"]),
                    "register_count": int(row["register_count"]),
                    "earliest_reference_date": row["earliest_reference_date"],
                    "latest_reference_date": row["latest_reference_date"],
                    "all_status_counts": statuses,
                }
            )
        return {
            "status_filter": status,
            "comparisons": output,
            "denominator": "public source observations in the selected reviewed snapshot",
            "provenance": self._provenance(),
        }

    def date_distribution(
        self,
        kind: str,
        *,
        authority: str | None = None,
        status: str | None = None,
        bucket: str = "month",
    ) -> dict[str, Any]:
        fields = {
            "application": "application_date",
            "expiry": "observed_expiry_date",
            "reference": "reference_date",
            "listing": "observed_listing_date",
        }
        if kind not in fields:
            return {
                "error": "invalid_date_kind",
                "allowed_kinds": sorted(fields),
                "provenance": self._provenance(),
            }
        widths = {"year": 4, "month": 7, "day": 10}
        if bucket not in widths:
            return {
                "error": "invalid_bucket",
                "allowed_buckets": sorted(widths),
                "provenance": self._provenance(),
            }
        if status and status not in STATUSES:
            return {
                "error": "invalid_status",
                "allowed_statuses": sorted(STATUSES),
                "provenance": self._provenance(),
            }
        clauses: list[str] = []
        params: list[Any] = []
        authority_resolution = None
        if authority:
            resolved, candidates = self._resolve_authority(authority)
            if not resolved:
                return {
                    "error": "authority_ambiguous_or_unknown",
                    "query": authority,
                    "candidates": candidates,
                    "provenance": self._provenance(),
                }
            authority_resolution = {
                "authority_key": resolved["authority_key"],
                "jurisdiction_name": resolved["jurisdiction_name"],
            }
            clauses.append("authority_key = ?")
            params.append(resolved["authority_key"])
        if status:
            clauses.append("source_status = ?")
            params.append(status)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        field = fields[kind]
        valid = f"date(NULLIF({field}, '')) IS NOT NULL"
        conjunction = " AND " if clauses else " WHERE "
        with self._connect() as connection:
            total = connection.execute(f"SELECT COUNT(*) FROM registry{where}", params).fetchone()[0]
            known = connection.execute(
                f"SELECT COUNT(*) FROM registry{where}{conjunction}{valid}",
                params,
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT substr({field}, 1, ?) AS bucket, COUNT(*) AS count
                FROM registry
                {where}{conjunction}{valid}
                GROUP BY substr({field}, 1, ?)
                ORDER BY bucket
                """,
                [widths[bucket], *params, widths[bucket]],
            ).fetchall()
        return {
            "kind": kind,
            "field": field,
            "bucket": bucket,
            "authority": authority_resolution,
            "status": status,
            "total_observations_in_scope": total,
            "dated_observations": known,
            "unknown_or_unusable_dates": total - known,
            "distribution": [{"bucket": row["bucket"], "count": row["count"]} for row in rows],
            "provenance": self._provenance(),
        }

    def get_history(self, *, authority: str | None = None, limit: int = 50) -> dict[str, Any]:
        limit = max(1, min(int(limit), 200))
        history = self._load_history()
        editions = list(history["editions"])
        resolution = None
        if authority:
            resolved, candidates = self._resolve_authority(authority)
            if not resolved:
                return {
                    "error": "authority_ambiguous_or_unknown",
                    "query": authority,
                    "candidates": candidates,
                    "provenance": self._provenance(),
                }
            resolution = {
                "authority_key": resolved["authority_key"],
                "jurisdiction_name": resolved["jurisdiction_name"],
            }
            editions = [item for item in editions if item.get("authority_key") == resolved["authority_key"]]
        editions.sort(key=lambda item: (str(item.get("reference_date") or ""), str(item.get("id") or "")), reverse=True)
        editions = editions[:limit]
        ids = {item["id"] for item in editions}
        checks = [item for item in history["checks"] if item.get("edition_id") in ids]
        comparisons = [
            item
            for item in history["comparisons"]
            if item.get("before_id") in ids and item.get("after_id") in ids
        ]
        return {
            "authority": resolution,
            "editions": editions,
            "checks": checks,
            "comparisons": comparisons,
            "interpretation": (
                "History comparisons are observational. Disappearance between editions is not, "
                "by itself, an administrative cancellation or removal."
            ),
            "provenance": self._provenance(),
        }

    def _load_robots(self) -> dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            if self.robots_path.exists() and now - self._robots_last_checked < self.refresh_seconds:
                return json.loads(self.robots_path.read_text(encoding="utf-8"))
            try:
                robots = self._fetch_json(self.robots_url, limit=2_000_000)
                if (
                    robots.get("schema_version") != 1
                    or not isinstance(robots.get("robots"), list)
                    or robots.get("schedule") != "daily"
                ):
                    raise SnapshotError("Invalid public robot directory")
                temporary = self.robots_path.with_suffix(".json.tmp")
                temporary.write_text(json.dumps(robots, ensure_ascii=False), encoding="utf-8")
                temporary.replace(self.robots_path)
                self._robots_refresh_error = None
                return robots
            except Exception as exc:
                self._robots_refresh_error = f"{type(exc).__name__}: {exc}"
                if self.robots_path.exists():
                    return json.loads(self.robots_path.read_text(encoding="utf-8"))
                raise
            finally:
                self._robots_last_checked = now

    def get_robot_directory(self, *, authority: str | None = None) -> dict[str, Any]:
        robots = self._load_robots()
        items = list(robots["robots"])
        resolution = None
        if authority:
            resolved, candidates = self._resolve_authority(authority)
            if not resolved:
                return {
                    "error": "authority_ambiguous_or_unknown",
                    "query": authority,
                    "candidates": candidates,
                    "provenance": self._provenance(),
                }
            resolution = {
                "authority_key": resolved["authority_key"],
                "jurisdiction_name": resolved["jurisdiction_name"],
            }
            items = [item for item in items if item.get("authority_key") == resolved["authority_key"]]
        return {
            "schedule": robots["schedule"],
            "authority": resolution,
            "robots": items,
            "note": (
                "This directory describes reviewed robot configuration and source mapping. "
                "It is not a live execution-health feed."
            ),
            "robots_refresh_error": self._robots_refresh_error,
            "provenance": self._provenance(),
        }

    def get_dataset_metadata(self) -> dict[str, Any]:
        prefectures = self._load_prefectures()
        history = self._load_history()
        with self._connect() as connection:
            record_count = connection.execute("SELECT COUNT(*) FROM registry").fetchone()[0]
            authority_count = connection.execute(
                "SELECT COUNT(DISTINCT authority_key) FROM registry WHERE authority_key <> ''"
            ).fetchone()[0]
            register_count = connection.execute(
                "SELECT COUNT(DISTINCT authority_key || '|' || register_name) FROM registry"
            ).fetchone()[0]
            status_counts = dict(
                connection.execute(
                    "SELECT source_status, COUNT(*) FROM registry GROUP BY source_status ORDER BY source_status"
                ).fetchall()
            )
            latest_reference_date = connection.execute(
                "SELECT MAX(NULLIF(reference_date, '')) FROM registry"
            ).fetchone()[0]
        return {
            "selected_public_snapshot": self._release_tag,
            "registry": {
                "record_count": record_count,
                "published_authority_count": authority_count,
                "authority_register_count": register_count,
                "status_counts": status_counts,
                "latest_reference_date": latest_reference_date,
                "unit": "source-backed public observation",
            },
            "prefecture_index": prefectures.get("meta", {}),
            "history": {
                "edition_count": len(history["editions"]),
                "check_count": len(history["checks"]),
                "comparison_count": len(history["comparisons"]),
            },
            "provenance": self._provenance(),
        }
