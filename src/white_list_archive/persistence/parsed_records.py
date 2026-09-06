from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError as exc:  # pragma: no cover - exercised only without database extra
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from white_list_archive.persistence.capture_manifest import persist_manifest

NAME_FIELD = {
    "source_label": "Ragione sociale",
    "normalised_source_label": "ragione_sociale",
    "ordinal_position": 1,
    "observed_datatype": "text",
    "observed_cardinality": "one",
    "structural_locator": "cosenza_combined_v1:operator_name",
}
IDENTIFIER_FIELD = {
    "source_label": "Codice fiscale/Partita IVA",
    "normalised_source_label": "codice_fiscale_partita_iva",
    "ordinal_position": 4,
    "observed_datatype": "text",
    "observed_cardinality": "one",
    "structural_locator": "cosenza_combined_v1:identifier",
}

REQUIRED_RECORD_COLUMNS = {
    "row_ordinal",
    "identifier_raw",
    "operator_name_raw",
    "operator_name_normalised",
    "source_status",
    "record_hash",
    "mention_key",
    "raw_block",
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def _parse_input(parse_manifest: dict[str, Any], label: str) -> dict[str, Any]:
    matches = [item for item in parse_manifest.get("inputs", []) if item.get("label") == label]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one parse input labelled {label!r}")
    return matches[0]


def _read_records(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or set(reader.fieldnames) != REQUIRED_RECORD_COLUMNS:
            raise ValueError(
                f"Unexpected Cosenza records schema in {path}: {reader.fieldnames}"
            )
        return list(reader)


def _parse_run_code(content_sha256: str, parse_manifest: dict[str, Any]) -> str:
    material = "\x1f".join(
        [
            content_sha256,
            parse_manifest["parser_name"],
            str(parse_manifest["parser_version"]),
            parse_manifest["processing_revision"],
            parse_manifest["configuration_hash"],
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _ensure_parse_run(cur, content_object_id, content_sha256: str, parse_manifest: dict[str, Any]):
    parse_run_code = _parse_run_code(content_sha256, parse_manifest)
    cur.execute(
        "SELECT parse_run_id FROM source.parse_run WHERE parse_run_code=%s",
        (parse_run_code,),
    )
    row = cur.fetchone()
    if row:
        return row[0], parse_run_code

    software_version = (
        f"{parse_manifest['parser_version']}+git.{parse_manifest['processing_revision']}"
    )
    cur.execute(
        """
        INSERT INTO provenance.processing_activity(
            activity_type_code, software_name, software_version,
            configuration_hash, started_at, completed_at
        ) VALUES ('parse',%s,%s,%s,%s,%s)
        RETURNING processing_activity_id
        """,
        (
            parse_manifest["parser_name"],
            software_version,
            parse_manifest["configuration_hash"],
            parse_manifest["started_at"],
            parse_manifest["completed_at"],
        ),
    )
    processing_activity_id = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO source.parse_run(
            content_object_id, processing_activity_id, status_code, parse_run_code
        ) VALUES (%s,%s,'succeeded',%s)
        RETURNING parse_run_id
        """,
        (content_object_id, processing_activity_id, parse_run_code),
    )
    return cur.fetchone()[0], parse_run_code


def _ensure_field_definition(cur, schema_version_id, definition: dict[str, Any]):
    locator = definition["structural_locator"]
    cur.execute(
        """
        SELECT field_definition_id
        FROM source.source_field_definition
        WHERE schema_version_id=%s AND structural_locator=%s
        """,
        (schema_version_id, locator),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        """
        INSERT INTO source.source_field_definition(
            schema_version_id, source_label, normalised_source_label,
            ordinal_position, observed_datatype, observed_cardinality,
            structural_locator
        ) VALUES (%s,%s,%s,%s,%s,%s,%s)
        RETURNING field_definition_id
        """,
        (
            schema_version_id,
            definition["source_label"],
            definition["normalised_source_label"],
            definition["ordinal_position"],
            definition["observed_datatype"],
            definition["observed_cardinality"],
            locator,
        ),
    )
    return cur.fetchone()[0]


def _ensure_parsed_record(cur, parse_run_id, schema_version_id, row: dict[str, str]):
    locator = f"row:{int(row['row_ordinal']):06d}"
    cur.execute(
        """
        SELECT parsed_record_id, record_hash, raw_record_text
        FROM source.parsed_record
        WHERE parse_run_id=%s AND record_locator=%s
        """,
        (parse_run_id, locator),
    )
    existing = cur.fetchone()
    if existing:
        parsed_record_id, record_hash, raw_record_text = existing
        if record_hash != row["record_hash"] or raw_record_text != row["raw_block"]:
            raise ValueError(
                f"Existing parsed record conflicts with deterministic locator {locator}"
            )
        return parsed_record_id

    cur.execute(
        """
        INSERT INTO source.parsed_record(
            parse_run_id, schema_version_id, record_locator, record_hash, raw_record_text
        ) VALUES (%s,%s,%s,%s,%s)
        RETURNING parsed_record_id
        """,
        (
            parse_run_id,
            schema_version_id,
            locator,
            row["record_hash"],
            row["raw_block"],
        ),
    )
    return cur.fetchone()[0]


def _ensure_field_value(
    cur,
    parsed_record_id,
    field_definition_id,
    schema_version_id,
    raw_value: str,
    parsed_value: dict[str, Any] | None,
    structural_locator: str,
) -> None:
    cur.execute(
        """
        INSERT INTO source.source_field_value(
            parsed_record_id, field_definition_id, schema_version_id,
            raw_value, parsed_value_json, structural_locator
        ) VALUES (%s,%s,%s,%s,%s::jsonb,%s)
        ON CONFLICT DO NOTHING
        """,
        (
            parsed_record_id,
            field_definition_id,
            schema_version_id,
            raw_value,
            json.dumps(parsed_value, ensure_ascii=False) if parsed_value is not None else None,
            structural_locator,
        ),
    )


def _ensure_entity_mention(cur, parsed_record_id) -> None:
    cur.execute(
        """
        INSERT INTO source.entity_mention(parsed_record_id, mention_role_code)
        VALUES (%s,'unknown')
        ON CONFLICT DO NOTHING
        """,
        (parsed_record_id,),
    )


def persist_records(
    conn,
    capture_manifest: dict[str, Any],
    parse_manifest: dict[str, Any],
    parse_label: str,
    records_path: Path,
    authority_csv: Path,
    series_csv: Path,
) -> dict[str, Any]:
    parse_input = _parse_input(parse_manifest, parse_label)
    if parse_input["text_sha256"] != capture_manifest["text_sha256"]:
        raise ValueError("Parser input text hash does not match capture manifest text_sha256")

    records = _read_records(records_path)
    if int(parse_input["record_count"]) != len(records):
        raise ValueError("Parse manifest record count does not match records CSV")

    graph = persist_manifest(conn, capture_manifest, authority_csv, series_csv)
    content_object_id = graph["content_object_id"]
    schema_version_id = graph["schema_version_id"]

    with conn.cursor() as cur:
        parse_run_id, parse_run_code = _ensure_parse_run(
            cur,
            content_object_id,
            capture_manifest["sha256"],
            parse_manifest,
        )
        name_field_id = _ensure_field_definition(cur, schema_version_id, NAME_FIELD)
        identifier_field_id = _ensure_field_definition(cur, schema_version_id, IDENTIFIER_FIELD)

        for row in records:
            parsed_record_id = _ensure_parsed_record(
                cur, parse_run_id, schema_version_id, row
            )
            _ensure_field_value(
                cur,
                parsed_record_id,
                name_field_id,
                schema_version_id,
                row["operator_name_raw"],
                {"normalised": row["operator_name_normalised"]},
                "operator_name",
            )
            _ensure_field_value(
                cur,
                parsed_record_id,
                identifier_field_id,
                schema_version_id,
                row["identifier_raw"],
                {
                    "scheme_code": "UNRESOLVED_CF_OR_VAT",
                    "interpretation": "source composite CF/Partita IVA field",
                },
                "identifier",
            )
            _ensure_entity_mention(cur, parsed_record_id)

    return {
        "reference_date": capture_manifest["reference_date"],
        "parse_run_id": str(parse_run_id),
        "parse_run_code": parse_run_code,
        "record_count": len(records),
        "field_value_count": len(records) * 2,
        "entity_mention_count": len(records),
    }


def persist_from_paths(
    dsn: str,
    capture_manifest_path: Path,
    parse_manifest_path: Path,
    parse_label: str,
    records_path: Path,
    authority_csv: Path,
    series_csv: Path,
) -> dict[str, Any]:
    if psycopg is None:
        raise RuntimeError("psycopg is required; install the 'database' extra") from _IMPORT_ERROR
    capture_manifest = _load_json(capture_manifest_path)
    parse_manifest = _load_json(parse_manifest_path)
    with psycopg.connect(dsn) as conn:
        result = persist_records(
            conn,
            capture_manifest,
            parse_manifest,
            parse_label,
            records_path,
            authority_csv,
            series_csv,
        )
        conn.commit()
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--capture-manifest", type=Path, required=True)
    parser.add_argument("--parse-manifest", type=Path, required=True)
    parser.add_argument("--parse-label", choices=["before", "after"], required=True)
    parser.add_argument("--records", type=Path, required=True)
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
    result = persist_from_paths(
        args.dsn,
        args.capture_manifest,
        args.parse_manifest,
        args.parse_label,
        args.records,
        args.authority_csv,
        args.series_csv,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
