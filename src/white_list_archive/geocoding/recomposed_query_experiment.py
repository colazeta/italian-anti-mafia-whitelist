from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from .nominatim import NominatimClient
from .structured_query import MunicipalityPrefixMatcher


def _stable_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fold(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char)).casefold()
    return " ".join(re.findall(r"[^\W_]+", text, re.UNICODE))


def _select_addresses(dsn: str) -> list[str]:
    if psycopg is None:
        raise RuntimeError("Install the project with the database extra") from _IMPORT_ERROR
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT btrim(full_address) FROM core.address "
            "WHERE btrim(full_address) <> '' ORDER BY 1"
        )
        return [str(row[0]) for row in cur.fetchall()]


def run_experiment(
    *,
    dsn: str,
    istat_csv: Path,
    endpoint: str,
    output_dir: Path,
    sample_size: int = 200,
    search_limit: int = 3,
    allow_public_nominatim: bool = False,
) -> dict[str, Any]:
    addresses = _select_addresses(dsn)
    matcher = MunicipalityPrefixMatcher.from_istat_csv(istat_csv)
    parsed = [(address, matcher.split(address)) for address in addresses]
    eligible = [
        (address, result.query)
        for address, result in parsed
        if result.status == "structured" and result.query is not None
    ]
    sample_size = min(sample_size, len(eligible))
    sample = sorted(eligible, key=lambda item: _stable_key(item[0]))[:sample_size]

    client = NominatimClient(endpoint, allow_public_service=allow_public_nominatim)
    status = client.status()
    rows: list[dict[str, Any]] = []
    errors = Counter()
    for source_address, split in sample:
        assert split is not None
        query_text = f"{split.street}, {split.city}"
        candidates = []
        error = None
        try:
            candidates = client.search(
                query_text,
                limit=search_limit,
                language="it",
                countrycodes="it",
            )
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            errors[type(exc).__name__] += 1
        top = candidates[0] if candidates else None
        rows.append(
            {
                "source_address": source_address,
                "municipality_code": split.municipality_code,
                "city_query": split.city,
                "street_query": split.street,
                "recomposed_query": query_text,
                "error": error,
                "matched": bool(candidates),
                "candidate_count": len(candidates),
                "precision": top.precision_code if top else None,
                "matched_address": top.matched_address if top else None,
                "street_name": top.street_name if top else None,
                "house_number": top.house_number if top else None,
                "postal_code": top.postal_code if top else None,
                "locality": top.locality if top else None,
                "admin_unit_l2": top.admin_unit_l2 if top else None,
                "admin_unit_l1": top.admin_unit_l1 if top else None,
                "country_code": top.country_code if top else None,
                "latitude": top.latitude if top else None,
                "longitude": top.longitude if top else None,
                "requested_city_matches_locality": bool(
                    top and top.locality and _fold(top.locality) == _fold(split.city)
                ),
            }
        )

    matched = [row for row in rows if row["matched"]]
    precision_counts = Counter((row["precision"] or "unknown") for row in matched)
    city_consistent = sum(bool(row["requested_city_matches_locality"]) for row in matched)
    summary = {
        "provider": status.provider_name,
        "endpoint": status.endpoint,
        "provider_version": status.software_version,
        "provider_data_updated": status.data_updated.isoformat() if status.data_updated else None,
        "population_addresses": len(addresses),
        "structured_query_eligible": len(eligible),
        "paired_baseline_compatible_sample_rule": "deterministic SHA-256 order among exact-Istat-prefix eligible addresses",
        "sample_size": len(rows),
        "network_search_requests": len(rows),
        "match_count": len(matched),
        "match_rate_pct": round(100 * len(matched) / len(rows), 2),
        "precision_counts": dict(sorted(precision_counts.items())),
        "address_level": precision_counts.get("address", 0),
        "house_number_present": sum(bool(row["house_number"]) for row in matched),
        "single_candidate": sum(int(row["candidate_count"]) == 1 for row in matched),
        "multiple_candidates": sum(int(row["candidate_count"]) > 1 for row in matched),
        "requested_city_matches_locality": city_consistent,
        "requested_city_matches_locality_rate_pct": round(100 * city_consistent / len(matched), 2) if matched else None,
        "provider_errors": dict(errors),
        "query_strategy": "free-form q='<street>, <official Istat city>' + hard countrycodes=it",
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if rows:
        with (output_dir / "results.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Test comma-delimited recomposed free-form Nominatim queries.")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--istat-csv", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--search-limit", type=int, default=3)
    parser.add_argument("--allow-public-nominatim", action="store_true")
    args = parser.parse_args()
    result = run_experiment(
        dsn=args.dsn,
        istat_csv=args.istat_csv,
        endpoint=args.endpoint,
        output_dir=args.output_dir,
        sample_size=args.sample_size,
        search_limit=args.search_limit,
        allow_public_nominatim=args.allow_public_nominatim,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
