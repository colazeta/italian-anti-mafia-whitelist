from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_records(path: Path, edition: str) -> list[dict[str, object]]:
    rows = read_csv(path)
    for row in rows:
        row["edition"] = edition
        row["row_ordinal"] = int(row["row_ordinal"])
    return rows


def classify_changes(before: list[dict[str, object]], after: list[dict[str, object]]) -> None:
    def key(r):
        return (r["identifier_raw"], r["operator_name_normalised"])

    before_by_key = {key(r): r for r in before}
    after_by_key = {key(r): r for r in after}

    for row in before:
        other = after_by_key.get(key(row))
        if other is None:
            row["change"] = "disappeared"
        elif row["source_status"] != other["source_status"]:
            row["change"] = "status_changed"
            row["transition"] = f"{row['source_status']}->{other['source_status']}"
        elif row["record_hash"] != other["record_hash"]:
            row["change"] = "content_changed"
        else:
            row["change"] = "unchanged"

    for row in after:
        other = before_by_key.get(key(row))
        if other is None:
            row["change"] = "added"
        elif row["source_status"] != other["source_status"]:
            row["change"] = "status_changed"
            row["transition"] = f"{other['source_status']}->{row['source_status']}"
        elif row["record_hash"] != other["record_hash"]:
            row["change"] = "content_changed"
        else:
            row["change"] = "unchanged"


def mask_identifier(value: str) -> str:
    if len(value) <= 5:
        return "•" * len(value)
    return value[:3] + "•" * (len(value) - 5) + value[-2:]


def build_payload(args) -> dict[str, object]:
    before = load_records(args.before_records, args.before_date)
    after = load_records(args.after_records, args.after_date)
    classify_changes(before, after)

    internal = args.mode == "internal"
    if internal and not args.acknowledge_internal_row_data:
        raise SystemExit("--mode internal requires --acknowledge-internal-row-data")

    records = before + after
    if not internal:
        for row in records:
            row["identifier_raw"] = mask_identifier(str(row["identifier_raw"]))
            row["raw_block"] = "[omitted in sanitized preview]"

    authorities = read_csv(args.authorities)
    verified = {row["authority_key"]: row for row in read_csv(args.verified_pages)}
    source_series = read_csv(args.source_series)
    series_counts = Counter(row["authority_key"] for row in source_series)
    authorities_payload = [
        {
            "key": authority["authority_key"],
            "name": authority["jurisdiction_name"],
            "region": authority["region"],
            "office_type": authority["office_type"],
            "verified": authority["authority_key"] in verified,
            "landing_url": verified.get(authority["authority_key"], {}).get("landing_url"),
            "series_count": series_counts.get(authority["authority_key"], 0),
        }
        for authority in authorities
    ]

    historical = read_csv(args.cosenza_history)
    diff = json.loads(args.diff.read_text(encoding="utf-8"))
    parse_manifest = json.loads(args.parse_manifest.read_text(encoding="utf-8"))
    capture_before = json.loads(args.capture_before.read_text(encoding="utf-8"))
    capture_after = json.loads(args.capture_after.read_text(encoding="utf-8"))

    snapshots = []
    for reference_date, rows in [(args.before_date, before), (args.after_date, after)]:
        snapshots.append(
            {
                "date": reference_date,
                "count": len(rows),
                "status_counts": dict(Counter(row["source_status"] for row in rows)),
            }
        )

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "classification": "INTERNAL ROW-LEVEL PREVIEW" if internal else "SANITIZED PREVIEW",
            "source_observation_only": True,
        },
        "national": {
            "authority_count": len(authorities),
            "verified_page_count": len(verified),
            "source_series_count": len(source_series),
            "cosenza_historical_editions": len(historical),
            "authorities": authorities_payload,
        },
        "cosenza": {
            "total_records": len(records),
            "parse_run_count": 2,
            "snapshots": snapshots,
            "diff": diff,
            "records": records,
            "provenance": {
                "parser_name": parse_manifest["parser_name"],
                "parser_version": parse_manifest["parser_version"],
                "processing_revision": parse_manifest["processing_revision"],
                "configuration_hash": parse_manifest["configuration_hash"],
                "schema_fingerprint": capture_before["schema_fingerprint"],
                "editions": [
                    {
                        "reference_date": capture_before["reference_date"],
                        "content_sha256": capture_before["sha256"],
                        "text_sha256": capture_before["text_sha256"],
                        "page_count": capture_before["page_count"],
                    },
                    {
                        "reference_date": capture_after["reference_date"],
                        "content_sha256": capture_after["sha256"],
                        "text_sha256": capture_after["text_sha256"],
                        "page_count": capture_after["page_count"],
                    },
                ],
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, default=Path("explorer/index.html"))
    parser.add_argument("--before-records", type=Path, required=True)
    parser.add_argument("--after-records", type=Path, required=True)
    parser.add_argument("--before-date", default="2026-06-28")
    parser.add_argument("--after-date", default="2026-08-03")
    parser.add_argument("--diff", type=Path, required=True)
    parser.add_argument("--parse-manifest", type=Path, required=True)
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
        raise SystemExit(f"Explorer template missing marker {marker}")

    html = template.replace(
        marker,
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "mode": args.mode,
                "records": payload["cosenza"]["total_records"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
