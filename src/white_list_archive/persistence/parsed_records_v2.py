from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from white_list_archive.persistence.capture_manifest import persist_manifest
from white_list_archive.persistence.parsed_records import (
    _ensure_entity_mention,
    _ensure_field_definition,
    _ensure_field_value,
    _ensure_parse_run,
    _ensure_parsed_record,
    _load_json,
    _parse_input,
)

FIELD_DEFINITIONS = [
    {
        "key": "operator_name_raw",
        "parsed_key": "operator_name_normalised",
        "source_label": "Ragione sociale",
        "normalised_source_label": "ragione_sociale",
        "ordinal_position": 1,
        "observed_datatype": "text",
        "observed_cardinality": "one",
        "structural_locator": "cosenza_combined_v2:operator_name",
    },
    {
        "key": "registered_office_raw",
        "source_label": "Sede legale",
        "normalised_source_label": "sede_legale",
        "ordinal_position": 2,
        "observed_datatype": "text",
        "observed_cardinality": "one",
        "structural_locator": "cosenza_combined_v2:registered_office",
    },
    {
        "key": "secondary_office_raw",
        "source_label": "Sede secondaria",
        "normalised_source_label": "sede_secondaria",
        "ordinal_position": 3,
        "observed_datatype": "text",
        "observed_cardinality": "zero_or_one",
        "structural_locator": "cosenza_combined_v2:secondary_office",
    },
    {
        "key": "identifier_field_raw",
        "json_key": "identifiers_json",
        "source_label": "Codice fiscale/Partita IVA",
        "normalised_source_label": "codice_fiscale_partita_iva",
        "ordinal_position": 4,
        "observed_datatype": "text",
        "observed_cardinality": "one_or_more",
        "structural_locator": "cosenza_combined_v2:identifier",
    },
    {
        "key": "requested_activities_raw",
        "json_key": "requested_activities_json",
        "source_label": "Attività per cui è richiesta l’iscrizione",
        "normalised_source_label": "attivita_richiesta_iscrizione",
        "ordinal_position": 5,
        "observed_datatype": "text",
        "observed_cardinality": "one_or_more",
        "structural_locator": "cosenza_combined_v2:requested_activities",
    },
    {
        "key": "application_date_field_raw",
        "json_key": "application_dates_json",
        "source_label": "Data di presentazione dell’istanza",
        "normalised_source_label": "data_presentazione_istanza",
        "ordinal_position": 6,
        "observed_datatype": "date_or_date_list",
        "observed_cardinality": "one_or_more",
        "structural_locator": "cosenza_combined_v2:application_dates",
    },
    {
        "key": "outcome_raw",
        "json_key": "outcome_json",
        "source_label": "Esito",
        "normalised_source_label": "esito",
        "ordinal_position": 7,
        "observed_datatype": "text",
        "observed_cardinality": "one",
        "structural_locator": "cosenza_combined_v2:outcome",
    },
]

REQUIRED_RECORD_COLUMNS = {
    "row_ordinal",
    "operator_name_raw",
    "operator_name_normalised",
    "registered_office_raw",
    "secondary_office_raw",
    "identifier_field_raw",
    "identifiers_json",
    "requested_activities_raw",
    "requested_activities_json",
    "application_date_field_raw",
    "application_dates_json",
    "outcome_raw",
    "outcome_json",
    "source_status",
    "observed_listing_date",
    "observed_expiry_date",
    "record_hash",
    "mention_key",
    "raw_block",
}


def _read_records(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or set(reader.fieldnames) != REQUIRED_RECORD_COLUMNS:
            raise ValueError(f"Unexpected Cosenza v2 records schema in {path}: {reader.fieldnames}")
        return list(reader)


def _parsed_value(row: dict[str, str], definition: dict[str, Any]) -> Any:
    if "json_key" in definition:
        return json.loads(row[str(definition["json_key"])])
    if definition.get("parsed_key"):
        return {"normalised": row[str(definition["parsed_key"])]}
    return None


def persist_records_v2(
    conn,
    capture_manifest: dict[str, Any],
    parse_manifest: dict[str, Any],
    parse_label: str,
    records_path: Path,
    authority_csv: Path,
    series_csv: Path,
) -> dict[str, Any]:
    parse_input = _parse_input(parse_manifest, parse_label)
    if parse_input["pdf_sha256"] != capture_manifest["sha256"]:
        raise ValueError("Parser v2 input PDF hash does not match capture manifest sha256")
    if parse_manifest.get("schema_fingerprint") != capture_manifest["schema_fingerprint"]:
        raise ValueError("Parser v2 schema fingerprint does not match capture manifest")

    records = _read_records(records_path)
    if int(parse_input["record_count"]) != len(records):
        raise ValueError("Parser v2 manifest record count does not match records CSV")

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
        field_ids = {
            str(definition["key"]): _ensure_field_definition(
                cur, schema_version_id, definition
            )
            for definition in FIELD_DEFINITIONS
        }

        for row in records:
            parsed_record_id = _ensure_parsed_record(
                cur, parse_run_id, schema_version_id, row
            )
            for definition in FIELD_DEFINITIONS:
                key = str(definition["key"])
                _ensure_field_value(
                    cur,
                    parsed_record_id,
                    field_ids[key],
                    schema_version_id,
                    row[key],
                    _parsed_value(row, definition),
                    str(definition["structural_locator"]).split(":", 1)[1],
                )
            _ensure_entity_mention(cur, parsed_record_id)

    return {
        "reference_date": capture_manifest["reference_date"],
        "parse_run_id": str(parse_run_id),
        "parse_run_code": parse_run_code,
        "record_count": len(records),
        "field_value_count": len(records) * len(FIELD_DEFINITIONS),
        "entity_mention_count": len(records),
        "source_field_count": len(FIELD_DEFINITIONS),
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
        result = persist_records_v2(
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
