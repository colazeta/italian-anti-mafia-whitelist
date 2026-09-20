#!/usr/bin/env python3
"""Build a deterministic White List performance-pilot eligibility matrix.

This script is deliberately repository-only: it reads the source registry and
the small manual pilot configuration, and writes no canonical or database data.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "research" / "white_list_performance_pilot" / "outputs" / "eligibility_baseline.csv"

TERRITORIAL = ROOT / "data" / "source_registry" / "territorial_authorities.csv"
SERIES = ROOT / "data" / "source_registry" / "source_series_inventory.csv"
PROFILES = ROOT / "data" / "source_registry" / "pilot_source_profiles.csv"
PILOT = ROOT / "research" / "white_list_performance_pilot" / "config" / "pilot_authorities.csv"

OUTPUT_FIELDS = [
    "authority_key",
    "pilot_stage",
    "pilot_role",
    "canonical_ingestion_ready",
    "longitudinal_ingestion_ready",
    "source_series_count",
    "has_listed_population",
    "has_applicant_population",
    "source_population_complete",
    "application_date_signal",
    "outcome_signal",
    "longitudinal_signal",
    "processing_time_status",
    "flow_metrics_status",
    "primary_blocker",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def yes(value: str | None) -> bool:
    return (value or "").strip().lower() == "yes"


def build_rows() -> list[dict[str, str]]:
    authorities = read_csv(TERRITORIAL)
    series = read_csv(SERIES)
    profiles = {row["authority_key"]: row for row in read_csv(PROFILES)}
    pilot = {row["authority_key"]: row for row in read_csv(PILOT)}

    by_authority: dict[str, list[dict[str, str]]] = {}
    for row in series:
        by_authority.setdefault(row["authority_key"], []).append(row)

    output: list[dict[str, str]] = []
    for authority in sorted(authorities, key=lambda row: row["authority_key"]):
        key = authority["authority_key"]
        source_rows = by_authority.get(key, [])
        scopes = {row.get("population_scope", "") for row in source_rows}

        has_listed = bool({"listed", "listed_and_applicant"} & scopes)
        has_applicant = bool({"applicant", "listed_and_applicant"} & scopes)
        source_complete = has_listed and has_applicant

        manual = pilot.get(key, {})
        profile = profiles.get(key, {})

        canonical_ready = yes(manual.get("canonical_ingestion_ready"))
        longitudinal_ready = yes(manual.get("longitudinal_ingestion_ready"))
        application_signal = manual.get("application_date_signal") or "unknown"
        outcome_signal = manual.get("outcome_signal") or "unknown"
        longitudinal_signal = (
            manual.get("longitudinal_signal")
            or profile.get("historical_snapshot_signal")
            or "unknown"
        )

        if not canonical_ready:
            processing_status = "blocked_canonical_ingestion"
        elif application_signal != "yes" or outcome_signal != "yes":
            processing_status = "blocked_field_support"
        else:
            processing_status = "ready_for_spell_validation"

        if not source_complete:
            flow_status = "blocked_population_coverage"
        elif not canonical_ready:
            flow_status = "blocked_canonical_ingestion"
        elif not longitudinal_ready:
            flow_status = "blocked_longitudinal_ingestion"
        elif application_signal != "yes" or outcome_signal != "yes":
            flow_status = "blocked_field_support"
        else:
            flow_status = "ready_for_flow_validation"

        blockers = []
        if not source_complete:
            blockers.append("population_coverage")
        if not canonical_ready:
            blockers.append("canonical_ingestion")
        if canonical_ready and not longitudinal_ready:
            blockers.append("longitudinal_ingestion")
        if application_signal != "yes":
            blockers.append("application_date_support")
        if outcome_signal != "yes":
            blockers.append("outcome_support")

        output.append(
            {
                "authority_key": key,
                "pilot_stage": manual.get("pilot_stage") or "expansion_pool",
                "pilot_role": manual.get("pilot_role") or "unassessed",
                "canonical_ingestion_ready": "yes" if canonical_ready else "no",
                "longitudinal_ingestion_ready": "yes" if longitudinal_ready else "no",
                "source_series_count": str(len(source_rows)),
                "has_listed_population": "yes" if has_listed else "no",
                "has_applicant_population": "yes" if has_applicant else "no",
                "source_population_complete": "yes" if source_complete else "no",
                "application_date_signal": application_signal,
                "outcome_signal": outcome_signal,
                "longitudinal_signal": longitudinal_signal,
                "processing_time_status": processing_status,
                "flow_metrics_status": flow_status,
                "primary_blocker": ";".join(blockers) if blockers else "none",
            }
        )
    return output


def write_rows(rows: list[dict[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def render_rows(rows: list[dict[str, str]]) -> str:
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the generated content differs from the existing output.",
    )
    args = parser.parse_args()

    rows = build_rows()

    if args.check:
        if not args.output.exists():
            raise SystemExit(f"Missing baseline: {args.output}")
        expected = render_rows(rows)
        actual = args.output.read_text(encoding="utf-8")
        if actual != expected:
            raise SystemExit("Eligibility baseline is stale; regenerate it.")
        return 0

    write_rows(rows, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
