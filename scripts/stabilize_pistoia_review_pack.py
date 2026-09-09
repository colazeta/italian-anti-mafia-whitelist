from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from white_list_archive.geocoding.review_sample import _allocate, review_stratum


def _key(row: dict[str, str]) -> str:
    return hashlib.sha256((row.get("source_address") or "").strip().encode("utf-8")).hexdigest()


def _fingerprint(rows: list[dict[str, str]]) -> str:
    material = "\n".join(
        "\x1f".join(
            [
                row.get("source_address", ""),
                row.get("review_stratum", ""),
                row.get("sampling_weight", ""),
                row.get("capture_sha256s", ""),
            ]
        )
        for row in rows
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild the Pistoia review sample from source-address identity, independent of transient database UUIDs."
    )
    parser.add_argument("--pack-dir", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=150)
    args = parser.parse_args()

    pack = args.pack_dir
    with (pack / "validation" / "address_results.csv").open(encoding="utf-8", newline="") as handle:
        results = list(csv.DictReader(handle))
    with (pack / "source-occurrences.csv").open(encoding="utf-8", newline="") as handle:
        occurrence_rows = list(csv.DictReader(handle))

    occurrences: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in occurrence_rows:
        occurrences[row["source_address"]].append(row)

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in results:
        grouped[review_stratum(row)].append(row)
    sizes = {stratum: len(rows) for stratum, rows in grouped.items()}
    allocation = _allocate(sizes, args.sample_size)

    sample: list[dict[str, str]] = []
    for stratum in sorted(grouped):
        ordered = sorted(grouped[stratum], key=_key)
        n = allocation.get(stratum, 0)
        if not n:
            continue
        weight = len(ordered) / n
        for row in ordered[:n]:
            evidence = occurrences.get(row["source_address"], [])
            if not evidence:
                raise RuntimeError(f"Missing source evidence for {row['source_address']!r}")
            item = dict(row)
            item.update(
                {
                    "review_stratum": stratum,
                    "stratum_population": str(len(ordered)),
                    "stratum_sample": str(n),
                    "sampling_weight": f"{weight:.6f}",
                    "manual_address_correct": "",
                    "manual_location_correct": "",
                    "manual_precision_acceptable": "",
                    "manual_review_notes": "",
                    "source_occurrence_count": str(len(evidence)),
                    "source_keys": " | ".join(sorted({x["source_key"] for x in evidence})),
                    "population_scopes": " | ".join(sorted({x["population_scope"] for x in evidence})),
                    "record_locators": " | ".join(x["record_locator"] for x in evidence),
                    "entity_names": " | ".join(x["entity_name"] for x in evidence),
                    "address_fields": " | ".join(x["address_field"] for x in evidence),
                    "source_page_urls": " | ".join(sorted({x["source_page_url"] for x in evidence})),
                    "resource_urls": " | ".join(sorted({x["resource_url"] for x in evidence})),
                    "capture_sha256s": " | ".join(sorted({x["capture_sha256"] for x in evidence})),
                }
            )
            sample.append(item)
    sample.sort(key=lambda row: (row["review_stratum"], _key(row)))

    output = pack / "pistoia-review-sample.csv"
    fields = list(sample[0]) if sample else []
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sample)

    manifest_path = pack / "pistoia-review-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["review"] = {
        "review_rows": len(sample),
        "rows_with_source_evidence": len(sample),
        "sample_sha256": _fingerprint(sample),
        "sample_identity_basis": "sha256(source_address)+review_stratum+sampling_weight+source_capture_sha256",
        "database_uuid_independent": True,
        "strata": {
            key: {"population": sizes[key], "sample": allocation.get(key, 0)}
            for key in sorted(sizes)
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest["review"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
