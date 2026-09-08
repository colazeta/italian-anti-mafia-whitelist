from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from white_list_archive.parsers.cosenza_combined_v2 import (
    PARSER_NAME,
    PARSER_VERSION,
    parse_pdf,
)


def _json_value(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return fallback


def _display_list(values: Any) -> str:
    if not isinstance(values, list):
        return ""
    out: list[str] = []
    for value in values:
        if isinstance(value, str):
            text = value
        elif isinstance(value, dict):
            text = str(
                value.get("raw_value")
                or value.get("value")
                or value.get("label")
                or value.get("date")
                or ""
            )
        else:
            text = str(value)
        if text.strip():
            out.append(text.strip())
    return " · ".join(out)


def build_registry(
    records: list[dict[str, Any]],
    *,
    reference_date: str,
    authority_key: str,
    authority_name: str,
    source_page_url: str,
    resource_url: str,
    capture_sha256: str,
) -> dict[str, Any]:
    public_records: list[dict[str, Any]] = []
    for record in records:
        identifiers = _json_value(record.get("identifiers_json"), [])
        activities = _json_value(record.get("requested_activities_json"), [])
        application_dates = _json_value(record.get("application_dates_json"), [])
        outcome = _json_value(record.get("outcome_json"), {})
        row_ordinal = int(record["row_ordinal"])
        public_records.append(
            {
                "record_locator": f"{authority_key}:{reference_date}:{row_ordinal}",
                "authority_key": authority_key,
                "authority_name": authority_name,
                "reference_date": reference_date,
                "source_row_ordinal": row_ordinal,
                "name": str(record.get("operator_name_raw") or ""),
                "registered_office": str(record.get("registered_office_raw") or ""),
                "secondary_office": str(record.get("secondary_office_raw") or ""),
                "identifier_field_raw": str(record.get("identifier_field_raw") or ""),
                "identifiers": identifiers,
                "requested_activities_raw": str(record.get("requested_activities_raw") or ""),
                "requested_activities": activities,
                "application_date_field_raw": str(record.get("application_date_field_raw") or ""),
                "application_dates": application_dates,
                "source_status": str(record.get("source_status") or "other_or_unknown"),
                "outcome_raw": str(record.get("outcome_raw") or ""),
                "outcome": outcome,
                "observed_listing_date": str(record.get("observed_listing_date") or ""),
                "observed_expiry_date": str(record.get("observed_expiry_date") or ""),
                "source_page_url": source_page_url,
                "resource_url": resource_url,
            }
        )

    status_counts = dict(Counter(r["source_status"] for r in public_records))
    return {
        "meta": {
            "contract_version": 2,
            "unit": "source observation in latest approved edition",
            "authority_key": authority_key,
            "authority_name": authority_name,
            "reference_date": reference_date,
            "source_page_url": source_page_url,
            "resource_url": resource_url,
            "capture_sha256": capture_sha256,
            "parser_name": PARSER_NAME,
            "parser_version": PARSER_VERSION,
            "record_count": len(public_records),
            "status_counts": status_counts,
            "interpretation": (
                "Rows reproduce observations in the approved official source edition. "
                "They are not asserted to be deduplicated canonical legal entities."
            ),
        },
        "records": public_records,
    }


def write_registry_csv(registry: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "record_locator",
        "authority_name",
        "reference_date",
        "source_row_ordinal",
        "name",
        "registered_office",
        "secondary_office",
        "identifiers",
        "requested_activities",
        "application_dates",
        "source_status",
        "outcome_raw",
        "observed_listing_date",
        "observed_expiry_date",
        "source_page_url",
        "resource_url",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in registry["records"]:
            writer.writerow(
                {
                    "record_locator": record["record_locator"],
                    "authority_name": record["authority_name"],
                    "reference_date": record["reference_date"],
                    "source_row_ordinal": record["source_row_ordinal"],
                    "name": record["name"],
                    "registered_office": record["registered_office"],
                    "secondary_office": record["secondary_office"],
                    "identifiers": _display_list(record["identifiers"]),
                    "requested_activities": _display_list(record["requested_activities"]),
                    "application_dates": _display_list(record["application_dates"]),
                    "source_status": record["source_status"],
                    "outcome_raw": record["outcome_raw"],
                    "observed_listing_date": record["observed_listing_date"],
                    "observed_expiry_date": record["observed_expiry_date"],
                    "source_page_url": record["source_page_url"],
                    "resource_url": record["resource_url"],
                }
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a public, source-backed registry export from an approved Cosenza PDF"
    )
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--site-config", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    args = parser.parse_args(argv)

    site = json.loads(args.site_config.read_text(encoding="utf-8"))
    cosenza = site["cosenza"]
    expected_sha = str(cosenza["capture_sha256"])
    actual_sha = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    if actual_sha != expected_sha:
        raise SystemExit(
            f"Approved Cosenza capture SHA mismatch: expected {expected_sha}, got {actual_sha}"
        )

    records = parse_pdf(args.pdf)
    expected_rows = int(cosenza["source_rows"])
    if len(records) != expected_rows:
        raise SystemExit(
            f"Cosenza public registry row-count mismatch: expected {expected_rows}, got {len(records)}"
        )

    registry = build_registry(
        records,
        reference_date=str(cosenza["latest_reference_date"]),
        authority_key="cosenza",
        authority_name="Prefettura di Cosenza",
        source_page_url=str(cosenza["latest_source_page"]),
        resource_url=str(cosenza["latest_resource_url"]),
        capture_sha256=expected_sha,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(registry, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    write_registry_csv(registry, args.output_csv)
    print(
        json.dumps(
            {
                "records": len(records),
                "status_counts": registry["meta"]["status_counts"],
                "sha256": expected_sha,
                "json": str(args.output_json),
                "csv": str(args.output_csv),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
