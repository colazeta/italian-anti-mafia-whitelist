"""Reconcile *existing* immutable historical capture checks into source tables.

Three known historical byte pins have verified complete CaptureCatalogue entries.
Persist their exact provenance with the existing append-only writer. Never acquire a
mutable URL, fabricate an edition/date, parse a row, or publish any record.
Every operational report contains closed aggregate counters only.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

from white_list_archive.acquisition.historical_object_audit import MAX_EXPECTED_SOURCE_BYTES
from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.catalogue_recovery import load_catalogued_capture
from white_list_archive.storage.evidence import object_key
from white_list_archive.storage.historical_capture_provenance_audit import (
    MAX_KEYS_PER_SOURCE, TARGETS, _valid_capture_key,
)

_REQUIRED = ("origin_type", "authority_rank_code", "resource_type_code")
_ALLOWED_SERIES = frozenset({"lodi-listed", "lodi-applicants", "milano-combined"})


def select_verified_historical_checks(
    store: Any, *, targets: tuple = TARGETS, limit: int = MAX_KEYS_PER_SOURCE,
) -> tuple[list[tuple[dict, dict]], dict]:
    """Select only positively verified, complete archive provenance; fail closed."""
    if (type(limit) is not int or not 1 <= limit <= MAX_KEYS_PER_SOURCE
            or not isinstance(targets, tuple) or not targets
            or len({scope for _, scope, _ in targets}) != len(targets)
            or any(
                not isinstance(scope, str) or not scope
                or series not in _ALLOWED_SERIES
                or not isinstance(sha, str) or len(sha) != 64
                or any(c not in "0123456789abcdef" for c in sha)
                for series, scope, sha in targets
            )):
        raise ValueError("Invalid closed historical selection")
    by_series: dict[str, dict[str, str]] = defaultdict(dict)
    for series, scope, sha in targets:
        if sha in by_series[series]:
            raise ValueError("Duplicate historical digest in one series")
        by_series[series][sha] = scope

    catalogue = CaptureCatalogue(store)
    selected = []
    positives = {scope: set() for _, scope, _ in targets}
    incomplete = 0
    metadata_blocked = 0
    for series, pinned in by_series.items():
        try:
            listing = store.client.list_objects_v2(
                Bucket=store.config.bucket, Prefix=f"captures/v1/{series}/",
                MaxKeys=limit,
            )
            objects = listing.get("Contents")
            if (listing.get("IsTruncated") is not False or
                    not isinstance(objects, list) or len(objects) > limit):
                incomplete += 1
                continue
        except Exception:
            incomplete += 1
            continue
        # A complete listing is a bounded candidate index, not an approval.
        for item in objects:
            if not isinstance(item, dict):
                continue
            capture_id = _valid_capture_key(item.get("Key"), source_key=series)
            if capture_id is None:
                continue
            try:
                manifest, receipt = load_catalogued_capture(
                    catalogue, source_key=series, capture_id=capture_id,
                )
                sha = manifest["sha256"]
                if (sha not in pinned or manifest["source_key"] != series
                        or manifest["capture_id"] != capture_id
                        or manifest["byte_size"] > MAX_EXPECTED_SOURCE_BYTES):
                    continue
                # This re-reads original bytes and checks the manifest SHA/size.
                store.read_verified(manifest)
                if not all(isinstance(manifest.get(f), str) and manifest[f].strip()
                           for f in _REQUIRED):
                    metadata_blocked += 1
                    continue
                positives[pinned[sha]].add(capture_id)
                selected.append((manifest, receipt))
            except Exception:
                # Never include an exception that may carry a private key or URL.
                continue

    summary = {
        "historical_pins_checked": len(targets),
        "pins_with_eligible_capture_provenance": sum(bool(s) for s in positives.values()),
        "historical_pins_unknown_or_unverified": sum(not s for s in positives.values()),
        "eligible_capture_checks": len(selected),
        "missing_writer_metadata_checks": metadata_blocked,
        "incomplete_or_unavailable_prefix_listings": incomplete,
    }
    return selected, summary


def persist_and_independently_readback(store: Any, manifest: dict, receipt: dict, dsn: str) -> tuple[bool, bool]:
    """Append via current writer, commit, then independently verify on new TLS hop."""
    from white_list_archive.acquisition.archive_first import ArchivedCapture
    from white_list_archive.acquisition.auto_transform import private_connection
    from white_list_archive.persistence.archived_capture import persist_archived_capture

    content_receipt = {
        "sha256": manifest["sha256"], "byte_size": manifest["byte_size"],
        "content_type": manifest["content_type"],
        "storage_uri": f"{store.config.endpoint.rstrip('/')}/{store.config.bucket}/{object_key(manifest)}",
    }
    archived = ArchivedCapture(
        path=Path("."), manifest=manifest,
        content_receipt=content_receipt, catalogue_receipt=receipt,
    )
    with private_connection(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM source.source_capture WHERE capture_id=%s",
                        (manifest["capture_id"],))
            already_captured = cur.fetchone() is not None
            cur.execute("SELECT 1 FROM source.content_object WHERE sha256=%s",
                        (manifest["sha256"],))
            already_registered = cur.fetchone() is not None
        # Existing writer independently checks ContentObject and catalogue again.
        # It refuses conflicting immutable capture UUID/provenance and never
        # creates a SourceEdition, parser run or canonical entity.
        persist_archived_capture(conn, archived, store)
        conn.commit()

    with private_connection(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT ss.series_code, co.sha256, co.file_size,
                          co.storage_status_code, c.captured_at,
                          sr.canonical_locator, c.origin_type_code,
                          c.authority_rank_code, c.declared_reference_date
                   FROM source.source_capture c
                   JOIN source.source_series ss ON ss.series_id=c.series_id
                   JOIN source.content_object co ON co.content_object_id=c.content_object_id
                   JOIN source.source_resource sr ON sr.resource_id=c.resource_id
                   WHERE c.capture_id=%s""",
                (manifest["capture_id"],),
            )
            row = cur.fetchone()
    frozen_date = manifest.get("reference_date")
    expected = (
        manifest["source_key"], manifest["sha256"], manifest["byte_size"],
        "durable", datetime.fromisoformat(manifest["captured_at"].replace("Z", "+00:00")),
        manifest["resource_url"], manifest["origin_type"],
        manifest["authority_rank_code"],
        None if frozen_date in (None, "") else datetime.fromisoformat(frozen_date).date(),
    )
    if row is None or tuple(row) != expected:
        raise RuntimeError("Historical capture post-commit provenance readback failed")
    return not already_captured, not already_registered



_FAILURE_CODES = frozenset({
    "capture_uuid_original_conflict",
    "capture_uuid_metadata_conflict",
    "resource_locator_type_conflict",
    "resource_locator_web_url_conflict",
    "resource_locator_web_url_and_type_conflict",
    "content_object_registration_conflict",
    "source_series_not_registered",
    "sql_integrity_or_permission_failure",
    "other_writer_or_readback_failure",
    "diagnostic_unavailable",
})


_RESOURCE_METADATA_CONFLICT_CODES = frozenset({
    "resource_locator_type_conflict",
    "resource_locator_web_url_conflict",
    "resource_locator_web_url_and_type_conflict",
})


def _resource_conflict_reason(
    *, stored_url: str, stored_type: str, archived_url: str, archived_type: str,
) -> str | None:
    """Classify immutable metadata differences; never alter the stored resource."""
    url_conflict = stored_url != archived_url
    type_conflict = stored_type != archived_type
    if url_conflict and type_conflict:
        return "resource_locator_web_url_and_type_conflict"
    if url_conflict:
        return "resource_locator_web_url_conflict"
    if type_conflict:
        return "resource_locator_type_conflict"
    return None


def classify_failed_capture(store: Any, manifest: dict, dsn: str, exc: Exception) -> str:
    """Use read-only SQL after a failed append; emit a fixed redacted code only."""
    from white_list_archive.acquisition.auto_transform import private_connection
    try:
        with private_connection(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT ss.series_code, co.sha256, c.captured_at,
                              sr.canonical_locator, sr.resource_type_code,
                              c.origin_type_code, c.authority_rank_code
                       FROM source.source_capture c
                       JOIN source.source_series ss ON ss.series_id=c.series_id
                       JOIN source.content_object co ON co.content_object_id=c.content_object_id
                       JOIN source.source_resource sr ON sr.resource_id=c.resource_id
                       WHERE c.capture_id=%s""",
                    (manifest["capture_id"],),
                )
                prior = cur.fetchone()
                if prior:
                    if prior[0] != manifest["source_key"] or prior[1] != manifest["sha256"]:
                        return "capture_uuid_original_conflict"
                    timestamp = datetime.fromisoformat(
                        manifest["captured_at"].replace("Z", "+00:00"),
                    )
                    if (prior[2] != timestamp
                            or prior[3] != manifest["resource_url"]
                            or prior[4] != manifest["resource_type_code"]
                            or prior[5] != manifest["origin_type"]
                            or prior[6] != manifest["authority_rank_code"]):
                        return "capture_uuid_metadata_conflict"
                cur.execute(
                    "SELECT web_url, resource_type_code FROM source.source_resource "
                    "WHERE canonical_locator=%s",
                    (manifest["resource_url"],),
                )
                resource = cur.fetchone()
                if resource:
                    resource_conflict = _resource_conflict_reason(
                        stored_url=resource[0], stored_type=resource[1],
                        archived_url=manifest["resource_url"],
                        archived_type=manifest["resource_type_code"],
                    )
                    if resource_conflict:
                        return resource_conflict
                cur.execute(
                    "SELECT file_size, storage_uri, storage_status_code "
                    "FROM source.content_object WHERE sha256=%s",
                    (manifest["sha256"],),
                )
                obj = cur.fetchone()
                uri = (
                    f"{store.config.endpoint.rstrip('/')}/{store.config.bucket}/"
                    f"{object_key(manifest)}"
                )
                if obj and (
                    obj[0] != manifest["byte_size"]
                    or (obj[2] == "durable" and obj[1] != uri)
                ):
                    return "content_object_registration_conflict"
                cur.execute(
                    "SELECT 1 FROM source.source_series WHERE series_code=%s",
                    (manifest["source_key"],),
                )
                if cur.fetchone() is None:
                    return "source_series_not_registered"
    except Exception:
        return "diagnostic_unavailable"
    if getattr(exc, "sqlstate", None) in {"23503", "23505", "23514", "42501"}:
        return "sql_integrity_or_permission_failure"
    return "other_writer_or_readback_failure"


def reconcile_historical_capture_checks(
    store: Any, dsn: str, *, targets: tuple = TARGETS,
) -> dict:
    checked, report = select_verified_historical_checks(store, targets=targets)
    new_captures = 0
    new_originals = 0
    readbacks = 0
    errors = 0
    failure_categories = {name: 0 for name in sorted(_FAILURE_CODES)}
    resource_conflicts_by_series = {name: 0 for name in sorted(_ALLOWED_SERIES)}
    if dsn:
        for manifest, receipt in checked:
            try:
                capture_created, original_created = persist_and_independently_readback(
                    store, manifest, receipt, dsn,
                )
                new_captures += int(capture_created)
                new_originals += int(original_created)
                readbacks += 1
            except Exception as exc:
                errors += 1
                reason = classify_failed_capture(store, manifest, dsn, exc)
                reason = reason if reason in _FAILURE_CODES else "diagnostic_unavailable"
                failure_categories[reason] += 1
                if reason in _RESOURCE_METADATA_CONFLICT_CODES:
                    # Only three reviewed SourceSeries codes are exposed, never
                    # per-capture provenance, resource URLs, or private keys.
                    resource_conflicts_by_series[manifest["source_key"]] += 1
    return {
        **report,
        "writer_configured": bool(dsn),
        "source_capture_checks_postcommit_verified": readbacks,
        "new_source_capture_checks": new_captures,
        "new_content_objects": new_originals,
        "relational_reconciliation_failures": errors,
        "reconciliation_failure_categories": failure_categories,
        "resource_metadata_conflicts_by_series": resource_conflicts_by_series,
        "editions_approved": 0,
        "semantic_or_canonical_writes": 0,
        "public_promotions": 0,
        "independent_restore_verified": False,
    }


def main() -> int:
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    try:
        config = StoreConfig.from_env()
        store = EvidenceStore(client_for(config), config)
        result = reconcile_historical_capture_checks(
            store, os.environ.get("EVIDENCE_DATABASE_URL", ""),
        )
    except Exception:
        result = {
            "historical_pins_checked": 4, "pins_with_eligible_capture_provenance": 0,
            "historical_pins_unknown_or_unverified": 4,
            "eligible_capture_checks": 0, "writer_configured": False,
            "source_capture_checks_postcommit_verified": 0,
            "new_source_capture_checks": 0, "new_content_objects": 0,
            "relational_reconciliation_failures": 0,
            "reconciliation_failure_categories": {name: 0 for name in sorted(_FAILURE_CODES)},
            "resource_metadata_conflicts_by_series": {
                name: 0 for name in sorted(_ALLOWED_SERIES)
            },
            "status": "unavailable_or_unverified",
            "editions_approved": 0, "semantic_or_canonical_writes": 0,
            "public_promotions": 0, "independent_restore_verified": False,
        }
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    # Local recovery failure does not abort the independent current-source lane.
    # Only nonzero real post-commit readbacks count as completed recovery.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
