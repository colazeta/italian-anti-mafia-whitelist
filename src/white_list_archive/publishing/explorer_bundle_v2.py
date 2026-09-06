from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_records(path: Path, edition: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = list(read_csv(path))
    for row in rows:
        row["edition"] = edition
        row["row_ordinal"] = int(str(row["row_ordinal"]))
        for source_key in (
            "identifiers_json",
            "requested_activities_json",
            "application_dates_json",
            "outcome_json",
        ):
            parsed_key = source_key.replace("_json", "_parsed")
            try:
                row[parsed_key] = json.loads(str(row[source_key]))
            except (TypeError, json.JSONDecodeError):
                row[parsed_key] = None
    return rows


def _record_key(row: dict[str, object]) -> tuple[str, str]:
    return (
        str(row["identifier_field_raw"]).replace("\n", ""),
        str(row["operator_name_normalised"]),
    )


def classify_changes(
    before: list[dict[str, object]], after: list[dict[str, object]]
) -> None:
    before_by_key = {_record_key(row): row for row in before}
    after_by_key = {_record_key(row): row for row in after}

    for rows, other, side in (
        (before, after_by_key, "before"),
        (after, before_by_key, "after"),
    ):
        for row in rows:
            counterpart = other.get(_record_key(row))
            if counterpart is None:
                row["change"] = "disappeared" if side == "before" else "added"
            elif row["source_status"] != counterpart["source_status"]:
                row["change"] = "status_changed"
                row["transition"] = (
                    f"{row['source_status']}->{counterpart['source_status']}"
                    if side == "before"
                    else f"{counterpart['source_status']}->{row['source_status']}"
                )
            elif row["record_hash"] != counterpart["record_hash"]:
                row["change"] = "content_changed"
            else:
                row["change"] = "unchanged"


def _mask(value: str) -> str:
    value = str(value)
    visible_positions = {0, 1, 2, max(0, len(value) - 2), max(0, len(value) - 1)}
    return "".join(
        char if char in "\n " or index in visible_positions else "•"
        for index, char in enumerate(value)
    )


def sanitize_records(records: list[dict[str, object]]) -> None:
    for row in records:
        row["identifier_field_raw"] = _mask(str(row.get("identifier_field_raw", "")))
        identifiers = row.get("identifiers_parsed") or []
        if isinstance(identifiers, list):
            for identifier in identifiers:
                if isinstance(identifier, dict) and "raw_value" in identifier:
                    identifier["raw_value"] = _mask(str(identifier["raw_value"]))
        row["raw_block"] = "[omitted in sanitized preview]"


def _load_optional_json(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def build_payload(args: argparse.Namespace) -> dict[str, object]:
    before = load_records(args.before_records, args.before_date)
    after = load_records(args.after_records, args.after_date)
    classify_changes(before, after)

    internal = args.mode == "internal"
    if internal and not args.acknowledge_internal_row_data:
        raise SystemExit("--mode internal requires --acknowledge-internal-row-data")
    if not internal:
        sanitize_records(before + after)

    authorities = read_csv(args.authorities)
    verified = {
        row["authority_key"]: row for row in read_csv(args.verified_pages)
    }
    source_series = read_csv(args.source_series)
    series_counts = Counter(row["authority_key"] for row in source_series)
    historical = read_csv(args.cosenza_history)

    authorities_payload = [
        {
            "key": authority["authority_key"],
            "name": authority["jurisdiction_name"],
            "region": authority["region"],
            "office_type": authority["office_type"],
            "verified": authority["authority_key"] in verified,
            "landing_url": verified.get(authority["authority_key"], {}).get(
                "landing_url"
            ),
            "series_count": series_counts.get(authority["authority_key"], 0),
        }
        for authority in authorities
    ]

    diff = json.loads(args.diff.read_text(encoding="utf-8"))
    parse_manifest = json.loads(args.parse_manifest.read_text(encoding="utf-8"))
    capture_before = json.loads(args.capture_before.read_text(encoding="utf-8"))
    capture_after = json.loads(args.capture_after.read_text(encoding="utf-8"))
    model_population = _load_optional_json(args.model_population)
    semantic_pipeline = _load_optional_json(args.semantic_pipeline)

    snapshots = []
    for reference_date, rows in ((args.before_date, before), (args.after_date, after)):
        snapshots.append(
            {
                "date": reference_date,
                "count": len(rows),
                "status_counts": dict(
                    Counter(str(row["source_status"]) for row in rows)
                ),
                "listing_dates": sum(bool(row["observed_listing_date"]) for row in rows),
                "expiry_dates": sum(bool(row["observed_expiry_date"]) for row in rows),
            }
        )

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat(),
            "classification": (
                "INTERNAL ROW-LEVEL PREVIEW · PARSER V2"
                if internal
                else "SANITIZED PREVIEW · PARSER V2"
            ),
            "source_observation_only": True,
        },
        "national": {
            "authority_count": len(authorities),
            "verified_page_count": len(verified),
            "source_series_count": len(source_series),
            "cosenza_historical_editions": len(historical),
            "authorities": authorities_payload,
        },
        "model_population": model_population,
        "semantic_pipeline": semantic_pipeline,
        "cosenza": {
            "total_records": len(before) + len(after),
            "snapshots": snapshots,
            "diff": diff,
            "records": before + after,
            "parser_qa": {
                "v1_counts": {"2026-06-28": 1325, "2026-08-03": 1332},
                "v2_counts": {
                    args.before_date: len(before),
                    args.after_date: len(after),
                },
                "v1_false_negative_rows_per_snapshot": 3,
                "v1_false_positive_rows_per_snapshot": 1,
                "net_correction_per_snapshot": 2,
            },
            "provenance": {
                "parser_name": parse_manifest["parser_name"],
                "parser_version": parse_manifest["parser_version"],
                "processing_revision": parse_manifest["processing_revision"],
                "configuration_hash": parse_manifest["configuration_hash"],
                "schema_fingerprint": parse_manifest["schema_fingerprint"],
                "editions": [
                    {
                        "reference_date": capture_before["reference_date"],
                        "content_sha256": capture_before["sha256"],
                        "page_count": capture_before["page_count"],
                    },
                    {
                        "reference_date": capture_after["reference_date"],
                        "content_sha256": capture_after["sha256"],
                        "page_count": capture_after["page_count"],
                    },
                ],
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, default=Path("explorer/v2.html"))
    parser.add_argument("--before-records", type=Path, required=True)
    parser.add_argument("--after-records", type=Path, required=True)
    parser.add_argument("--before-date", default="2026-06-28")
    parser.add_argument("--after-date", default="2026-08-03")
    parser.add_argument("--diff", type=Path, required=True)
    parser.add_argument("--parse-manifest", type=Path, required=True)
    parser.add_argument("--model-population", type=Path)
    parser.add_argument("--semantic-pipeline", type=Path)
    parser.add_argument(
        "--capture-before",
        type=Path,
        default=Path("data/captures/cosenza/combined_2026-06-28.json"),
    )
    parser.add_argument(
        "--capture-after",
        type=Path,
        default=Path("data/captures/cosenza/combined_2026-08-03.json"),
    )
    parser.add_argument(
        "--authorities",
        type=Path,
        default=Path("data/source_registry/territorial_authorities.csv"),
    )
    parser.add_argument(
        "--verified-pages",
        type=Path,
        default=Path("data/source_registry/verified_primary_pages.csv"),
    )
    parser.add_argument(
        "--source-series",
        type=Path,
        default=Path("data/source_registry/source_series_inventory.csv"),
    )
    parser.add_argument(
        "--cosenza-history",
        type=Path,
        default=Path("data/source_registry/cosenza_historical_editions.csv"),
    )
    parser.add_argument("--mode", choices=["sanitized", "internal"], default="sanitized")
    parser.add_argument("--acknowledge-internal-row-data", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = build_payload(args)
    template = args.template.read_text(encoding="utf-8")
    marker = "__DATA_PAYLOAD__"
    if marker not in template:
        raise SystemExit(f"Explorer v2 template missing marker {marker}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        template.replace(
            marker,
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "records": payload["cosenza"]["total_records"],
                "mode": args.mode,
                "model_population": bool(payload.get("model_population")),
                "semantic_pipeline": bool(payload.get("semantic_pipeline")),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
