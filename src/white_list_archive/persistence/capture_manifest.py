from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

try:
    import psycopg
except ImportError as exc:  # pragma: no cover - exercised only without database extra
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


OFFICE_TYPE_TO_DB = {
    "prefettura_utg": "prefecture_utg",
    "government_commissariat": "government_commissioner",
    "valle_d_aosta_special": "other",
}

POPULATION_SCOPE_TO_DB = {
    "listed": ("listed",),
    "applicant": ("applicant",),
    "listed_and_applicant": ("listed", "applicant"),
}


@dataclass(frozen=True)
class RegistryContext:
    authority_key: str
    authority_name: str
    authority_type_code: str
    jurisdiction_name: str
    source_series_key: str
    regime_code: str
    population_types: tuple[str, ...]


def _read_csv_index(path: Path, key: str) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row[key]: row for row in rows}


def load_context(
    manifest: dict[str, Any],
    authority_csv: Path,
    series_csv: Path,
) -> RegistryContext:
    authorities = _read_csv_index(authority_csv, "authority_key")
    series = _read_csv_index(series_csv, "source_series_key")

    authority_key = manifest["authority_key"]
    series_key = manifest["source_series_key"]
    if authority_key not in authorities:
        raise ValueError(f"Unknown authority_key in manifest: {authority_key}")
    if series_key not in series:
        raise ValueError(f"Unknown source_series_key in manifest: {series_key}")

    authority = authorities[authority_key]
    source_series = series[series_key]
    if source_series["authority_key"] != authority_key:
        raise ValueError(
            f"Series {series_key} belongs to {source_series['authority_key']}, not {authority_key}"
        )
    office_type = authority["office_type"]
    try:
        authority_type_code = OFFICE_TYPE_TO_DB[office_type]
    except KeyError as exc:
        raise ValueError(f"No database authority mapping for office_type={office_type}") from exc
    scope = source_series["population_scope"]
    try:
        population_types = POPULATION_SCOPE_TO_DB[scope]
    except KeyError as exc:
        raise ValueError(f"Unsupported population_scope for manifest importer: {scope}") from exc

    return RegistryContext(
        authority_key=authority_key,
        authority_name=authority["authority_name"],
        authority_type_code=authority_type_code,
        jurisdiction_name=authority["jurisdiction_name"],
        source_series_key=series_key,
        regime_code=source_series["regime_code"],
        population_types=population_types,
    )


def _fetchone_value(cur) -> Any:
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("Expected a row but query returned none")
    return row[0]


def ensure_authority(cur, context: RegistryContext):
    cur.execute(
        "SELECT public_authority_id FROM core.public_authority WHERE authority_code=%s",
        (context.authority_key,),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        """
        INSERT INTO core.public_authority(authority_code, authority_type_code, preferred_name)
        VALUES (%s,%s,%s)
        RETURNING public_authority_id
        """,
        (context.authority_key, context.authority_type_code, context.authority_name),
    )
    return _fetchone_value(cur)


def ensure_register(cur, authority_id, context: RegistryContext):
    register_code = f"WL-REGISTER-{context.authority_key.upper()}-ORDINARY"
    cur.execute(
        "SELECT register_id FROM whitelist.white_list_register WHERE register_code=%s",
        (register_code,),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "SELECT regime_id FROM whitelist.white_list_regime WHERE regime_code=%s",
        (context.regime_code,),
    )
    regime_id = _fetchone_value(cur)
    cur.execute(
        """
        INSERT INTO whitelist.white_list_register(
            public_authority_id, regime_id, register_code, official_name, effective_period
        ) VALUES (%s,%s,%s,%s,NULL)
        RETURNING register_id
        """,
        (
            authority_id,
            regime_id,
            register_code,
            f"White List - {context.jurisdiction_name}",
        ),
    )
    return _fetchone_value(cur)


def ensure_series(cur, authority_id, register_id, context: RegistryContext):
    cur.execute(
        "SELECT series_id FROM source.source_series WHERE series_code=%s",
        (context.source_series_key,),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        """
        INSERT INTO source.source_series(
            series_code, publisher_authority_id, register_id, series_name, series_type_code
        ) VALUES (%s,%s,%s,%s,'list')
        RETURNING series_id
        """,
        (
            context.source_series_key,
            authority_id,
            register_id,
            f"{context.jurisdiction_name} White List - {context.source_series_key}",
        ),
    )
    return _fetchone_value(cur)


def ensure_edition(cur, series_id, manifest: dict[str, Any], context: RegistryContext):
    edition_code = manifest["reference_date"]
    cur.execute(
        """
        SELECT edition_id FROM source.source_edition
        WHERE series_id=%s AND edition_code=%s
        """,
        (series_id, edition_code),
    )
    row = cur.fetchone()
    if row:
        edition_id = row[0]
    else:
        ref = date.fromisoformat(edition_code)
        cur.execute(
            """
            INSERT INTO source.source_edition(
                series_id, edition_code, reference_period, publication_date,
                edition_identity_status_code,
                population_scope_completeness_code,
                sector_scope_completeness_code
            ) VALUES (%s,%s,daterange(%s,%s,'[)'),NULL,'explicit','all','all')
            RETURNING edition_id
            """,
            (series_id, edition_code, ref, ref + timedelta(days=1)),
        )
        edition_id = _fetchone_value(cur)

    for population in context.population_types:
        cur.execute(
            """
            INSERT INTO source.edition_population_scope(edition_id, population_type_code)
            VALUES (%s,%s)
            ON CONFLICT DO NOTHING
            """,
            (edition_id, population),
        )
    return edition_id


def ensure_resource(cur, manifest: dict[str, Any]):
    locator = manifest["resource_url"]
    cur.execute(
        "SELECT resource_id FROM source.source_resource WHERE canonical_locator=%s",
        (locator,),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        """
        INSERT INTO source.source_resource(canonical_locator, web_url, resource_type_code)
        VALUES (%s,%s,'pdf')
        RETURNING resource_id
        """,
        (locator, locator),
    )
    return _fetchone_value(cur)


def _ephemeral_storage_uri(manifest: dict[str, Any]) -> str:
    run_id = manifest["workflow_run_id"]
    artifact_id = manifest["workflow_artifact_id"]
    reference_date = manifest["reference_date"]
    return (
        "github-actions://colazeta/italian-anti-mafia-whitelist/"
        f"runs/{run_id}/artifacts/{artifact_id}/cosenza-capture/{reference_date}/combined.pdf"
    )


def ensure_content_object(cur, manifest: dict[str, Any]):
    sha256 = manifest["sha256"]
    cur.execute(
        """
        SELECT content_object_id, mime_type, file_size
        FROM source.content_object WHERE sha256=%s
        """,
        (sha256,),
    )
    row = cur.fetchone()
    if row:
        content_object_id, mime_type, file_size = row
        if mime_type != manifest["content_type"] or file_size != manifest["byte_size"]:
            raise ValueError("Existing ContentObject metadata conflicts with manifest byte identity")
        return content_object_id
    cur.execute(
        """
        INSERT INTO source.content_object(
            sha256, mime_type, file_size, storage_uri, storage_status_code
        ) VALUES (%s,%s,%s,%s,'ephemeral')
        RETURNING content_object_id
        """,
        (
            sha256,
            manifest["content_type"],
            manifest["byte_size"],
            _ephemeral_storage_uri(manifest),
        ),
    )
    return _fetchone_value(cur)


def ensure_capture(cur, resource_id, content_object_id, manifest: dict[str, Any]):
    captured_at = datetime.fromisoformat(manifest["captured_at"])
    cur.execute(
        """
        SELECT capture_id FROM source.source_capture
        WHERE resource_id=%s AND content_object_id=%s AND captured_at=%s
        """,
        (resource_id, content_object_id, captured_at),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        """
        INSERT INTO source.source_capture(
            resource_id, content_object_id, captured_at, http_status,
            origin_type_code, authority_rank_code,
            resolved_url, etag, last_modified
        ) VALUES (%s,%s,%s,%s,%s,'primary_official',%s,%s,%s)
        RETURNING capture_id
        """,
        (
            resource_id,
            content_object_id,
            captured_at,
            manifest["http_status"],
            manifest["origin_type"],
            manifest.get("final_url"),
            manifest.get("etag"),
            manifest.get("last_modified"),
        ),
    )
    return _fetchone_value(cur)


def ensure_capture_edition(cur, capture_id, edition_id):
    cur.execute(
        """
        INSERT INTO source.capture_edition(
            capture_id, edition_id, relation_type_code, attribution_status_code
        ) VALUES (%s,%s,'is_representation_of','explicit')
        ON CONFLICT DO NOTHING
        """,
        (capture_id, edition_id),
    )


def ensure_schema_version(cur, series_id, manifest: dict[str, Any]):
    schema_name = "Cosenza combined White List PDF layout"
    cur.execute(
        """
        SELECT source_schema_id FROM source.source_schema
        WHERE series_id=%s AND schema_name=%s
        """,
        (series_id, schema_name),
    )
    row = cur.fetchone()
    if row:
        source_schema_id = row[0]
    else:
        cur.execute(
            """
            INSERT INTO source.source_schema(series_id, schema_name)
            VALUES (%s,%s)
            RETURNING source_schema_id
            """,
            (series_id, schema_name),
        )
        source_schema_id = _fetchone_value(cur)

    observed = datetime.fromisoformat(manifest["captured_at"])
    fingerprint = manifest["schema_fingerprint"]
    cur.execute(
        """
        SELECT schema_version_id, first_observed_at, last_observed_at
        FROM source.source_schema_version
        WHERE source_schema_id=%s AND structural_fingerprint=%s
        """,
        (source_schema_id, fingerprint),
    )
    row = cur.fetchone()
    if row:
        schema_version_id, first_seen, last_seen = row
        values = [value for value in [first_seen, last_seen, observed] if value is not None]
        cur.execute(
            """
            UPDATE source.source_schema_version
            SET first_observed_at=%s, last_observed_at=%s
            WHERE schema_version_id=%s
            """,
            (min(values), max(values), schema_version_id),
        )
        return schema_version_id

    cur.execute(
        """
        INSERT INTO source.source_schema_version(
            source_schema_id, structural_fingerprint, first_observed_at, last_observed_at
        ) VALUES (%s,%s,%s,%s)
        RETURNING schema_version_id
        """,
        (source_schema_id, fingerprint, observed, observed),
    )
    return _fetchone_value(cur)


def persist_manifest(
    conn,
    manifest: dict[str, Any],
    authority_csv: Path,
    series_csv: Path,
) -> dict[str, str]:
    context = load_context(manifest, authority_csv, series_csv)
    with conn.cursor() as cur:
        authority_id = ensure_authority(cur, context)
        register_id = ensure_register(cur, authority_id, context)
        series_id = ensure_series(cur, authority_id, register_id, context)
        edition_id = ensure_edition(cur, series_id, manifest, context)
        resource_id = ensure_resource(cur, manifest)
        content_object_id = ensure_content_object(cur, manifest)
        capture_id = ensure_capture(cur, resource_id, content_object_id, manifest)
        ensure_capture_edition(cur, capture_id, edition_id)
        schema_version_id = ensure_schema_version(cur, series_id, manifest)
    return {
        "authority_id": str(authority_id),
        "register_id": str(register_id),
        "series_id": str(series_id),
        "edition_id": str(edition_id),
        "resource_id": str(resource_id),
        "content_object_id": str(content_object_id),
        "capture_id": str(capture_id),
        "schema_version_id": str(schema_version_id),
    }


def persist_paths(
    dsn: str,
    manifest_paths: Iterable[Path],
    authority_csv: Path,
    series_csv: Path,
) -> list[dict[str, str]]:
    if psycopg is None:
        raise RuntimeError("psycopg is required; install the 'database' extra") from _IMPORT_ERROR
    with psycopg.connect(dsn) as conn:
        results = []
        for path in manifest_paths:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            results.append(persist_manifest(conn, manifest, authority_csv, series_csv))
        conn.commit()
        return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest_paths", nargs="+", type=Path)
    parser.add_argument("--dsn", required=True)
    parser.add_argument(
        "--authority-csv",
        type=Path,
        default=Path("data/source_registry/territorial_authorities.csv"),
    )
    parser.add_argument(
        "--series-csv",
        type=Path,
        default=Path("data/source_registry/source_series_inventory.csv"),
    )
    args = parser.parse_args()
    results = persist_paths(
        args.dsn,
        args.manifest_paths,
        args.authority_csv,
        args.series_csv,
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
