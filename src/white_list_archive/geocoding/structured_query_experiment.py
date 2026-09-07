from __future__ import annotations

import argparse
import csv
import hashlib
import json
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

from .nominatim import NominatimClient, parse_geocodejson
from .structured_query import MunicipalityPrefixMatcher, StructuredAddressQuery

PRECISION_RANK = {
    "unknown": 0,
    "admin": 1,
    "locality": 2,
    "postal_code": 2,
    "street": 3,
    "address": 4,
}


def _stable_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _top(candidates):
    return candidates[0] if candidates else None


def _summary_for(candidates) -> dict[str, Any]:
    top = _top(candidates)
    return {
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
    }


def _structured_search(client: NominatimClient, query: StructuredAddressQuery, limit: int):
    params = {
        "street": query.street,
        "city": query.city,
        "countrycodes": "it",
        "format": "geocodejson",
        "addressdetails": 1,
        "limit": limit,
        "dedupe": 1,
        "accept-language": "it",
    }
    return parse_geocodejson(client._request_json("/search", params))


def _select_source_addresses(dsn: str) -> list[str]:
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
    addresses = _select_source_addresses(dsn)
    matcher = MunicipalityPrefixMatcher.from_istat_csv(istat_csv)
    parsed = [(address, matcher.split(address)) for address in addresses]
    parse_counts = Counter(result.status for _, result in parsed)
    eligible = [
        (address, result.query)
        for address, result in parsed
        if result.status == "structured" and result.query is not None
    ]
    if not eligible:
        raise RuntimeError("No Cosenza addresses were eligible for structured-query testing")
    sample_size = min(sample_size, len(eligible))
    sample = sorted(eligible, key=lambda item: _stable_key(item[0]))[:sample_size]

    client = NominatimClient(
        endpoint,
        allow_public_service=allow_public_nominatim,
    )
    provider_status = client.status()
    rows: list[dict[str, Any]] = []
    error_counts = Counter()
    for source_address, structured_query in sample:
        assert structured_query is not None
        raw_candidates = []
        structured_candidates = []
        raw_error = None
        structured_error = None
        try:
            raw_candidates = client.search(source_address, limit=search_limit, language="it")
        except Exception as exc:  # noqa: BLE001
            raw_error = f"{type(exc).__name__}: {exc}"
            error_counts["raw"] += 1
        try:
            structured_candidates = _structured_search(client, structured_query, search_limit)
        except Exception as exc:  # noqa: BLE001
            structured_error = f"{type(exc).__name__}: {exc}"
            error_counts["structured"] += 1

        raw = _summary_for(raw_candidates)
        structured = _summary_for(structured_candidates)
        raw_rank = PRECISION_RANK.get(raw["precision"] or "unknown", 0)
        structured_rank = PRECISION_RANK.get(structured["precision"] or "unknown", 0)
        rows.append(
            {
                "source_address": source_address,
                "municipality_code": structured_query.municipality_code,
                "city_query": structured_query.city,
                "street_query": structured_query.street,
                "province_plate": structured_query.province_plate,
                "raw_error": raw_error,
                "structured_error": structured_error,
                **{f"raw_{key}": value for key, value in raw.items()},
                **{f"structured_{key}": value for key, value in structured.items()},
                "precision_delta": structured_rank - raw_rank,
            }
        )

    raw_matched = sum(bool(row["raw_matched"]) for row in rows)
    structured_matched = sum(bool(row["structured_matched"]) for row in rows)
    raw_only = sum(bool(row["raw_matched"]) and not bool(row["structured_matched"]) for row in rows)
    structured_only = sum(bool(row["structured_matched"]) and not bool(row["raw_matched"]) for row in rows)
    both = sum(bool(row["structured_matched"]) and bool(row["raw_matched"]) for row in rows)
    neither = len(rows) - raw_only - structured_only - both
    precision_better = sum(int(row["precision_delta"]) > 0 for row in rows)
    precision_worse = sum(int(row["precision_delta"]) < 0 for row in rows)
    address_level_raw = sum(row["raw_precision"] == "address" for row in rows)
    address_level_structured = sum(row["structured_precision"] == "address" for row in rows)
    house_raw = sum(bool(row["raw_house_number"]) for row in rows)
    house_structured = sum(bool(row["structured_house_number"]) for row in rows)

    summary = {
        "provider": provider_status.provider_name,
        "endpoint": provider_status.endpoint,
        "provider_version": provider_status.software_version,
        "provider_data_updated": provider_status.data_updated.isoformat() if provider_status.data_updated else None,
        "population_addresses": len(addresses),
        "parser_status_counts": dict(sorted(parse_counts.items())),
        "structured_query_eligible": len(eligible),
        "structured_query_eligibility_rate_pct": round(100 * len(eligible) / len(addresses), 2),
        "paired_sample_size": len(rows),
        "network_search_requests": len(rows) * 2,
        "raw_match_count": raw_matched,
        "raw_match_rate_pct": round(100 * raw_matched / len(rows), 2),
        "structured_match_count": structured_matched,
        "structured_match_rate_pct": round(100 * structured_matched / len(rows), 2),
        "absolute_match_rate_gain_pp": round(100 * (structured_matched - raw_matched) / len(rows), 2),
        "raw_only": raw_only,
        "structured_only": structured_only,
        "both": both,
        "neither": neither,
        "structured_precision_better": precision_better,
        "structured_precision_worse": precision_worse,
        "raw_address_level": address_level_raw,
        "structured_address_level": address_level_structured,
        "raw_house_number_present": house_raw,
        "structured_house_number_present": house_structured,
        "provider_errors": dict(error_counts),
        "sampling": "deterministic SHA-256 order among exact-Istat-prefix eligible addresses",
        "query_strategy": {
            "raw": "original source address as q; no country filter",
            "structured": "exact Istat municipality prefix -> city + untouched remainder as street; countrycodes=it",
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if rows:
        with (output_dir / "paired_results.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare raw and structured Nominatim queries on a paired address sample.")
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
