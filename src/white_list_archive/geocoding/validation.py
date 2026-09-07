from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


MATCHED_STATUSES = {"accepted", "candidate"}
FIELD_NAMES = (
    "normalised_address",
    "street_name",
    "house_number",
    "postal_code",
    "locality",
    "admin_unit_l2",
    "admin_unit_l1",
    "country_code",
    "latitude",
    "longitude",
)


@dataclass(frozen=True)
class ValidationRow:
    address_id: str
    source_address: str
    match_status: str
    candidate_count: int
    provider_name: str | None
    provider_endpoint: str | None
    provider_version: str | None
    provider_data_updated: str | None
    query_text: str | None
    normalised_address: str | None
    street_name: str | None
    house_number: str | None
    postal_code: str | None
    locality: str | None
    admin_unit_l2: str | None
    admin_unit_l1: str | None
    country_name: str | None
    country_code: str | None
    latitude: float | None
    longitude: float | None
    precision_code: str | None

    @property
    def matched(self) -> bool:
        return self.match_status in MATCHED_STATUSES

    @property
    def stratum(self) -> str:
        if self.match_status == "unprocessed":
            return "unprocessed"
        if self.match_status == "error":
            return "error"
        if self.match_status == "not_found":
            return "not_found"
        if self.country_code and self.country_code.upper() != "IT":
            return "foreign_matched"
        if self.precision_code == "address":
            return "matched_address"
        if self.precision_code == "street":
            return "matched_street"
        return "matched_coarse"


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(100.0 * numerator / denominator, 2)


def _stable_key(row: ValidationRow) -> str:
    payload = f"{row.address_id}\0{row.source_address}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _allocate_stratified_sample(stratum_sizes: dict[str, int], sample_size: int) -> dict[str, int]:
    if sample_size < 1:
        raise ValueError("sample_size must be >= 1")
    total = sum(stratum_sizes.values())
    if total == 0:
        return {}
    target = min(sample_size, total)
    nonempty = {key: value for key, value in stratum_sizes.items() if value > 0}

    # Give every observed stratum a small floor, then allocate the remainder
    # proportionally. This preserves failure/coarse strata without turning the
    # sample into an unweighted convenience sample.
    allocation = {key: min(value, 5) for key, value in nonempty.items()}
    seeded = sum(allocation.values())
    if seeded > target:
        allocation = {key: 0 for key in nonempty}
        for key in sorted(nonempty, key=lambda item: (-nonempty[item], item))[:target]:
            allocation[key] = 1
        return allocation

    remaining = target - seeded
    while remaining > 0:
        capacities = {key: nonempty[key] - allocation[key] for key in nonempty}
        available = {key: cap for key, cap in capacities.items() if cap > 0}
        if not available:
            break
        weight_total = sum(nonempty[key] for key in available)
        ideal = {key: remaining * nonempty[key] / weight_total for key in available}
        additions = {key: min(available[key], int(ideal[key])) for key in available}
        added = sum(additions.values())
        for key, value in additions.items():
            allocation[key] += value
        remaining -= added
        if remaining <= 0:
            break
        order = sorted(
            available,
            key=lambda key: (-(ideal[key] - int(ideal[key])), -nonempty[key], key),
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


def build_manual_sample(rows: list[ValidationRow], sample_size: int = 150) -> list[dict[str, Any]]:
    grouped: dict[str, list[ValidationRow]] = defaultdict(list)
    for row in rows:
        grouped[row.stratum].append(row)
    sizes = {key: len(value) for key, value in grouped.items()}
    allocation = _allocate_stratified_sample(sizes, sample_size)

    output: list[dict[str, Any]] = []
    for stratum in sorted(grouped):
        ordered = sorted(grouped[stratum], key=_stable_key)
        n = allocation.get(stratum, 0)
        if n == 0:
            continue
        weight = len(ordered) / n
        for row in ordered[:n]:
            item = row.__dict__.copy()
            item.update(
                {
                    "review_stratum": stratum,
                    "stratum_population": len(ordered),
                    "stratum_sample": n,
                    "sampling_weight": round(weight, 6),
                    "manual_address_correct": "",
                    "manual_location_correct": "",
                    "manual_precision_acceptable": "",
                    "manual_review_notes": "",
                }
            )
            output.append(item)
    return sorted(output, key=lambda item: (item["review_stratum"], _stable_key(ValidationRow(**{k: item[k] for k in ValidationRow.__dataclass_fields__}))))


def summarize(rows: list[ValidationRow]) -> dict[str, Any]:
    total = len(rows)
    status_counts = Counter(row.match_status for row in rows)
    matched = [row for row in rows if row.matched]
    matched_count = len(matched)
    precision_counts = Counter((row.precision_code or "unknown") for row in matched)
    candidate_multiplicity = Counter(
        "multiple_candidates" if row.candidate_count > 1 else "single_candidate"
        for row in matched
    )
    country_counts = Counter((row.country_code or "UNKNOWN") for row in matched)
    field_completeness: dict[str, dict[str, Any]] = {}
    for field in FIELD_NAMES:
        present = sum(getattr(row, field) not in (None, "") for row in matched)
        field_completeness[field] = {
            "present": present,
            "matched_addresses": matched_count,
            "rate_pct": _pct(present, matched_count),
        }

    distinct_source_queries = len({row.source_address.strip() for row in rows})
    duplicate_source_address_ids = total - distinct_source_queries
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "total_canonical_addresses": total,
        "distinct_source_address_strings": distinct_source_queries,
        "duplicate_source_address_ids": duplicate_source_address_ids,
        "addresses_with_provider_match": matched_count,
        "match_rate_pct": _pct(matched_count, total),
        "not_found": status_counts.get("not_found", 0),
        "not_found_rate_pct": _pct(status_counts.get("not_found", 0), total),
        "errors": status_counts.get("error", 0),
        "error_rate_pct": _pct(status_counts.get("error", 0), total),
        "unprocessed": status_counts.get("unprocessed", 0),
        "status_counts": dict(sorted(status_counts.items())),
        "precision_counts": dict(sorted(precision_counts.items())),
        "candidate_multiplicity": dict(sorted(candidate_multiplicity.items())),
        "ambiguous_match_rate_pct": _pct(candidate_multiplicity.get("multiple_candidates", 0), matched_count),
        "country_counts": dict(sorted(country_counts.items())),
        "field_completeness": field_completeness,
        "review_strata": dict(sorted(Counter(row.stratum for row in rows).items())),
    }


def _fetch_rows(
    conn,
    *,
    provider_name: str | None = None,
    provider_endpoint: str | None = None,
) -> list[ValidationRow]:
    filters = ["upper_inf(g.system_period)"]
    params: list[Any] = []
    if provider_name:
        filters.append("g.provider_name = %s")
        params.append(provider_name)
    if provider_endpoint:
        filters.append("g.provider_endpoint = %s")
        params.append(provider_endpoint.rstrip("/"))
    where = " AND ".join(filters)

    sql = f"""
        WITH eligible AS (
            SELECT g.*
            FROM geo.address_geocode_result g
            WHERE {where}
        ),
        counts AS (
            SELECT address_id,
                   count(*) FILTER (WHERE match_status_code IN ('accepted','candidate')) AS candidate_count
            FROM eligible
            GROUP BY address_id
        ),
        best AS (
            SELECT DISTINCT ON (g.address_id)
                g.address_id,
                g.match_status_code,
                g.provider_name,
                g.provider_endpoint,
                g.provider_version,
                g.provider_data_updated,
                g.query_text,
                g.matched_address,
                g.normalised_street_name,
                g.normalised_house_number,
                g.normalised_postal_code,
                g.normalised_locality,
                g.normalised_admin_unit_l2,
                g.normalised_admin_unit_l1,
                g.normalised_country_name,
                g.normalised_country_code,
                g.latitude,
                g.longitude,
                g.precision_code,
                g.candidate_rank,
                lower(g.system_period) AS observed_at
            FROM eligible g
            ORDER BY
                g.address_id,
                CASE g.match_status_code
                    WHEN 'accepted' THEN 0
                    WHEN 'candidate' THEN 1
                    WHEN 'not_found' THEN 2
                    WHEN 'error' THEN 3
                    ELSE 4
                END,
                g.candidate_rank,
                lower(g.system_period) DESC,
                g.address_geocode_result_id
        )
        SELECT
            a.address_id::text,
            a.full_address,
            COALESCE(b.match_status_code, 'unprocessed') AS match_status,
            COALESCE(c.candidate_count, 0) AS candidate_count,
            b.provider_name,
            b.provider_endpoint,
            b.provider_version,
            b.provider_data_updated::text,
            b.query_text,
            b.matched_address,
            b.normalised_street_name,
            b.normalised_house_number,
            b.normalised_postal_code,
            b.normalised_locality,
            b.normalised_admin_unit_l2,
            b.normalised_admin_unit_l1,
            b.normalised_country_name,
            b.normalised_country_code,
            b.latitude,
            b.longitude,
            b.precision_code
        FROM core.address a
        LEFT JOIN best b ON b.address_id = a.address_id
        LEFT JOIN counts c ON c.address_id = a.address_id
        ORDER BY a.full_address, a.address_id
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [ValidationRow(*row) for row in cur.fetchall()]


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_report(path: Path, summary: dict[str, Any], sample_size: int) -> None:
    lines = [
        "# Cosenza address geocoding validation",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        "## Coverage",
        "",
        f"- Canonical addresses: **{summary['total_canonical_addresses']}**",
        f"- Distinct source address strings: **{summary['distinct_source_address_strings']}**",
        f"- Provider match: **{summary['addresses_with_provider_match']} ({summary['match_rate_pct']}%)**",
        f"- Not found: **{summary['not_found']} ({summary['not_found_rate_pct']}%)**",
        f"- Provider/runtime errors: **{summary['errors']} ({summary['error_rate_pct']}%)**",
        f"- Unprocessed: **{summary['unprocessed']}**",
        "",
        "## Precision of matched results",
        "",
    ]
    for key, value in summary["precision_counts"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Candidate multiplicity", ""])
    for key, value in summary["candidate_multiplicity"].items():
        lines.append(f"- `{key}`: {value}")
    lines.append(f"- Ambiguous match rate among matched addresses: **{summary['ambiguous_match_rate_pct']}%**")
    lines.extend(["", "## Field completeness among matched addresses", ""])
    for key, value in summary["field_completeness"].items():
        lines.append(f"- `{key}`: {value['present']} / {value['matched_addresses']} ({value['rate_pct']}%)")
    lines.extend(["", "## Manual validation", ""])
    lines.append(
        f"`manual_review_sample.csv` contains a deterministic stratified sample of up to **{sample_size}** addresses. "
        "Each row includes its stratum population, stratum sample size and sampling weight so reviewed results can later be aggregated without treating the balanced sample as a simple random sample."
    )
    lines.append("")
    lines.append("No geocoding result is promoted to geographic truth by this report; it is a measurement artifact.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_validation_pack(
    *,
    dsn: str,
    output_dir: Path,
    provider_name: str | None = None,
    provider_endpoint: str | None = None,
    sample_size: int = 150,
) -> dict[str, Any]:
    if psycopg is None:
        raise RuntimeError("psycopg is required; install the project with the database extra") from _IMPORT_ERROR
    output_dir.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(dsn) as conn:
        rows = _fetch_rows(
            conn,
            provider_name=provider_name,
            provider_endpoint=provider_endpoint,
        )
    summary = summarize(rows)
    summary.update(
        {
            "provider_filter": provider_name,
            "provider_endpoint_filter": provider_endpoint.rstrip("/") if provider_endpoint else None,
            "manual_sample_requested": sample_size,
        }
    )
    sample = build_manual_sample(rows, sample_size=sample_size)
    summary["manual_sample_rows"] = len(sample)

    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    all_fields = list(ValidationRow.__dataclass_fields__)
    _write_csv(
        output_dir / "address_results.csv",
        (row.__dict__ for row in rows),
        all_fields,
    )
    sample_fields = all_fields + [
        "review_stratum",
        "stratum_population",
        "stratum_sample",
        "sampling_weight",
        "manual_address_correct",
        "manual_location_correct",
        "manual_precision_acceptable",
        "manual_review_notes",
    ]
    _write_csv(output_dir / "manual_review_sample.csv", sample, sample_fields)
    _write_report(output_dir / "README.md", summary, sample_size)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a reproducible geocoding validation pack.")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--provider-name")
    parser.add_argument("--provider-endpoint")
    parser.add_argument("--sample-size", type=int, default=150)
    args = parser.parse_args()
    summary = build_validation_pack(
        dsn=args.dsn,
        output_dir=args.output_dir,
        provider_name=args.provider_name,
        provider_endpoint=args.provider_endpoint,
        sample_size=args.sample_size,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
