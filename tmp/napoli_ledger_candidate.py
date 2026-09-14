from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data/monitoring/national_coverage.json"

LISTED_SHA256 = "93a8635c0bd9b00587f9cc60c52752061bd239a7c16cb34b64a11e495a0ab4be"
APPLICANT_SHA256 = "053be2500b07a7da536c344aede12084dde9b7cf28b4717af99764cbd05e7e6b"


def main() -> int:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    rows = [row for row in ledger.get("prefectures", []) if row.get("authority_key") == "napoli"]
    if len(rows) != 1:
        raise RuntimeError(f"Expected exactly one Napoli coverage row, found {len(rows)}")
    row = rows[0]

    expected_prestate = {
        "source_verified": True,
        "current_edition_identified": None,
        "capture_implemented": False,
        "parser_implemented": False,
        "parser_validated": False,
        "company_observations_loaded": False,
        "observation_layer": None,
        "canonical_integration_validated": False,
        "public_export_enabled": False,
        "durable_evidence_verified": False,
        "population_scopes_complete": True,
        "coverage_status": "SOURCE_IDENTIFIED",
    }
    observed_prestate = {key: row.get(key) for key in expected_prestate}
    if observed_prestate != expected_prestate:
        raise RuntimeError(
            "Napoli coverage pre-state drift: "
            f"expected={expected_prestate!r} observed={observed_prestate!r}"
        )
    if row.get("known_content_sha256") not in ([], None):
        raise RuntimeError("Napoli coverage row unexpectedly already has content hashes")
    if row.get("completion_evidence") not in ([], None):
        raise RuntimeError("Napoli coverage row unexpectedly already has completion evidence")

    row.update(
        current_edition_identified=True,
        capture_implemented=True,
        parser_implemented=True,
        parser_validated=True,
        company_observations_loaded=True,
        observation_layer="public_source_observations",
        canonical_integration_validated=False,
        public_export_enabled=True,
        durable_evidence_verified=False,
        population_scopes_complete=True,
        latest_source_reference_date="2026-09-11",
        last_successful_investigation_on="2026-09-14",
        unresolved_issue=[
            "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."
        ],
        actionable_issue=False,
        coverage_status="VALIDATED",
        terminal_reason=None,
        completion_evidence=[
            "docs/sources/napoli-operational-check-2026-09-13.md",
            "src/white_list_archive/parsers/napoli_tables.py",
            "tests/test_napoli_parser_semantics.py",
            "data/publication/multi_prefecture_pilot.json",
        ],
        known_content_sha256=[LISTED_SHA256, APPLICANT_SHA256],
        evidence=[
            "data/source_registry/verified_primary_pages.csv",
            "data/source_registry/source_series_inventory.csv",
            "data/publication/multi_prefecture_pilot.json",
            "docs/sources/napoli-operational-check-2026-09-13.md",
        ],
        last_completed_coverage_stage="VALIDATED",
    )

    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "authority_key": "napoli",
                "public_export_enabled": row["public_export_enabled"],
                "coverage_status": row["coverage_status"],
                "known_content_sha256": row["known_content_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
