from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

TARGET_POPULATIONS = ("listed", "applicant")
ALLOWED_SCOPES = {"listed", "applicant", "listed_and_applicant"}
UNRESOLVED_REGISTER = "UNRESOLVED_REGISTER"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_coverage(
    verified_pages: list[dict[str, str]],
    source_series: list[dict[str, str]],
) -> dict[str, Any]:
    verified_authorities = {row["authority_key"] for row in verified_pages}
    by_authority_regime: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)

    for row in source_series:
        scope = row["population_scope"]
        if scope not in ALLOWED_SCOPES:
            raise ValueError(
                f"Unsupported population_scope {scope!r} for {row['source_series_key']}"
            )
        if row["authority_key"] not in verified_authorities:
            raise ValueError(
                f"Source series {row['source_series_key']} belongs to an authority without a verified primary page"
            )
        by_authority_regime[(row["authority_key"], row["regime_code"])].append(row)

    scopes: dict[str, list[str]] = defaultdict(list)
    for authority, regime in by_authority_regime:
        scopes[authority].append(regime)
    for authority in verified_authorities:
        if authority not in scopes:
            scopes[authority] = [UNRESOLVED_REGISTER]

    rows: list[dict[str, Any]] = []
    scope_summaries: list[dict[str, Any]] = []

    for authority in sorted(scopes):
        for regime in sorted(set(scopes[authority])):
            series = by_authority_regime.get((authority, regime), [])
            statuses: dict[str, str] = {}
            for target in TARGET_POPULATIONS:
                combined = sorted(
                    row["source_series_key"]
                    for row in series
                    if row["population_scope"] == "listed_and_applicant"
                )
                direct = sorted(
                    row["source_series_key"]
                    for row in series
                    if row["population_scope"] == target
                )
                if combined:
                    status = "COVERED_COMBINED_SERIES"
                    covering = combined
                    note = "A combined source series explicitly covers both logical populations."
                elif direct:
                    status = "COVERED_SEPARATE_SERIES"
                    covering = direct
                    note = f"A source series explicitly covers the {target} population."
                else:
                    status = "UNRESOLVED_REQUIRES_REVIEW"
                    covering = []
                    if regime == UNRESOLVED_REGISTER:
                        note = (
                            "Primary White List page is verified, but source-series/register discovery "
                            "has not yet accounted for this logical population."
                        )
                    else:
                        note = (
                            f"No {target} source series is yet inventoried for this register/regime. "
                            "Absence from the registry is not evidence that the population is not published."
                        )
                statuses[target] = status
                rows.append(
                    {
                        "authority_key": authority,
                        "regime_code": regime,
                        "population_target": target,
                        "coverage_status": status,
                        "covering_series_keys": covering,
                        "note": note,
                    }
                )

            complete = all(statuses[target].startswith("COVERED_") for target in TARGET_POPULATIONS)
            scope_summaries.append(
                {
                    "authority_key": authority,
                    "regime_code": regime,
                    "listed_status": statuses["listed"],
                    "applicant_status": statuses["applicant"],
                    "source_population_complete": complete,
                }
            )

    complete_scopes = sum(bool(row["source_population_complete"]) for row in scope_summaries)
    return {
        "required_populations": list(TARGET_POPULATIONS),
        "verified_authority_count": len(verified_authorities),
        "register_scope_count": len(scope_summaries),
        "complete_register_scope_count": complete_scopes,
        "incomplete_register_scope_count": len(scope_summaries) - complete_scopes,
        "rows": rows,
        "scopes": scope_summaries,
    }


def _write_csv(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "authority_key",
        "regime_code",
        "population_target",
        "coverage_status",
        "covering_series_keys",
        "note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in report["rows"]:
            value = dict(row)
            value["covering_series_keys"] = ";".join(value["covering_series_keys"])
            writer.writerow(value)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the mandatory listed/applicant source-population coverage ledger. "
            "A register scope is complete only when both populations are accounted for."
        )
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
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-csv", type=Path)
    args = parser.parse_args()

    report = build_coverage(_read_csv(args.verified_pages), _read_csv(args.source_series))
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    if args.output_csv:
        _write_csv(args.output_csv, report)
    print(json.dumps({k: v for k, v in report.items() if k.endswith("count")}, indent=2))


if __name__ == "__main__":
    main()
