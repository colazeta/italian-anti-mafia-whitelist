from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

MATCHED = {"accepted", "candidate"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _stable_key(row: dict[str, str]) -> str:
    payload = f"{row.get('address_id','')}\0{row.get('source_address','')}".encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()


def review_stratum(row: dict[str, str]) -> str:
    status = (row.get("match_status") or "").strip()
    if status not in MATCHED:
        return status or "unprocessed"
    country = (row.get("country_code") or "").strip().upper()
    if country and country != "IT":
        return "foreign_matched"
    latitude = (row.get("latitude") or "").strip()
    longitude = (row.get("longitude") or "").strip()
    precision = (row.get("precision_code") or "").strip()
    if not latitude or not longitude:
        return "matched_without_coordinates"
    if precision == "civic_access":
        return "matched_civic_access"
    if precision == "address":
        return "matched_address"
    if precision == "street":
        return "matched_street"
    return "matched_coarse"


def _allocate(sizes: dict[str, int], target: int) -> dict[str, int]:
    if target < 1:
        raise ValueError("sample_size must be >= 1")
    total = sum(sizes.values())
    if not total:
        return {}
    target = min(target, total)
    nonempty = {key: value for key, value in sizes.items() if value > 0}

    allocation = {key: min(value, 5) for key, value in nonempty.items()}
    seeded = sum(allocation.values())
    if seeded > target:
        allocation = {key: 0 for key in nonempty}
        for key in sorted(nonempty, key=lambda k: (nonempty[k], k))[:target]:
            allocation[key] = 1
        return allocation

    remaining = target - seeded
    while remaining:
        available = {
            key: nonempty[key] - allocation[key]
            for key in nonempty
            if allocation[key] < nonempty[key]
        }
        if not available:
            break
        weight_total = sum(nonempty[key] for key in available)
        ideal = {key: remaining * nonempty[key] / weight_total for key in available}
        additions = {
            key: min(available[key], int(ideal[key])) for key in available
        }
        added = sum(additions.values())
        for key, value in additions.items():
            allocation[key] += value
        remaining -= added
        if remaining <= 0:
            break
        order = sorted(
            available,
            key=lambda key: (
                -(ideal[key] - int(ideal[key])),
                -nonempty[key],
                key,
            ),
        )
        progressed = False
        for key in order:
            if remaining <= 0:
                break
            if allocation[key] < nonempty[key]:
                allocation[key] += 1
                remaining -= 1
                progressed = True
        if not progressed:
            break
    return allocation


def build_review_sample(
    rows: list[dict[str, str]],
    *,
    sample_size: int = 150,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[review_stratum(row)].append(row)
    sizes = {key: len(value) for key, value in grouped.items()}
    allocation = _allocate(sizes, sample_size)

    output: list[dict[str, Any]] = []
    for stratum in sorted(grouped):
        ordered = sorted(grouped[stratum], key=_stable_key)
        n = allocation.get(stratum, 0)
        if not n:
            continue
        weight = len(ordered) / n
        for row in ordered[:n]:
            item: dict[str, Any] = dict(row)
            item.update(
                {
                    "review_stratum": stratum,
                    "stratum_population": len(ordered),
                    "stratum_sample": n,
                    "sampling_weight": round(weight, 6),
                }
            )
            output.append(item)
    return sorted(
        output,
        key=lambda row: (row["review_stratum"], _stable_key(row)),
    )


def write_review_sample(
    address_results: Path,
    output: Path,
    *,
    sample_size: int = 150,
) -> dict[str, Any]:
    rows = _read_csv(address_results)
    sample = build_review_sample(rows, sample_size=sample_size)
    output.parent.mkdir(parents=True, exist_ok=True)
    base_fields = list(rows[0]) if rows else []
    fields = base_fields + [
        "review_stratum",
        "stratum_population",
        "stratum_sample",
        "sampling_weight",
    ]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sample)
    strata: dict[str, dict[str, int]] = {}
    for row in sample:
        key = str(row["review_stratum"])
        strata[key] = {
            "population": int(row["stratum_population"]),
            "sample": int(row["stratum_sample"]),
        }
    return {
        "address_results": str(address_results),
        "output": str(output),
        "population_rows": len(rows),
        "sample_rows": len(sample),
        "strata": dict(sorted(strata.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build a deterministic precision-aware manual-review sample from "
            "geocoding validation results."
        )
    )
    parser.add_argument("--address-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=150)
    args = parser.parse_args()
    result = write_review_sample(
        args.address_results,
        args.output,
        sample_size=args.sample_size,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
