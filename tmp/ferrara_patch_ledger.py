from __future__ import annotations

import json
from pathlib import Path

LEDGER_PATH = Path("data/monitoring/national_coverage.json")

EXPECTED_KEYS = {
    "authority_key",
    "prefecture",
    "region",
    "national_index_key",
    "official_landing_page",
    "source_verified",
    "current_edition_identified",
    "historical_editions_identified",
    "capture_implemented",
    "parser_implemented",
    "parser_validated",
    "company_observations_loaded",
    "observation_layer",
    "canonical_integration_validated",
    "public_export_enabled",
    "durable_evidence_verified",
    "population_scopes_complete",
    "latest_source_reference_date",
    "latest_archived_edition",
    "archived_evidence_storage_status",
    "last_successful_source_check_at",
    "last_attempted_source_check_at",
    "last_content_change_at",
    "last_successful_investigation_on",
    "monitoring_status",
    "unresolved_issue",
    "actionable_issue",
    "coverage_status",
    "terminal_reason",
    "completion_evidence",
    "known_content_sha256",
    "evidence",
}


def main() -> None:
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    rows = [row for row in ledger["prefectures"] if row.get("authority_key") == "ferrara"]
    if len(rows) != 1:
        raise SystemExit(f"Expected exactly one Ferrara ledger row, found {len(rows)}")
    row = rows[0]
    if set(row) != EXPECTED_KEYS:
        raise SystemExit(f"Ferrara ledger schema drift: {sorted(set(row) ^ EXPECTED_KEYS)}")

    expected_pre = {
        "source_verified": False,
        "current_edition_identified": None,
        "capture_implemented": False,
        "parser_implemented": False,
        "parser_validated": False,
        "company_observations_loaded": False,
        "observation_layer": None,
        "canonical_integration_validated": False,
        "public_export_enabled": False,
        "durable_evidence_verified": False,
        "population_scopes_complete": False,
        "latest_source_reference_date": None,
        "last_successful_source_check_at": None,
        "last_attempted_source_check_at": None,
        "last_content_change_at": None,
        "last_successful_investigation_on": None,
        "monitoring_status": "NEVER_CHECKED",
        "unresolved_issue": [],
        "actionable_issue": False,
        "coverage_status": "SOURCE_IDENTIFIED",
        "terminal_reason": None,
        "completion_evidence": [],
        "known_content_sha256": [],
        "evidence": ["https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/34252484175"],
    }
    for key, value in expected_pre.items():
        if row.get(key) != value:
            raise SystemExit(f"Ferrara ledger pre-state drift for {key}: {row.get(key)!r}")

    row.update(
        source_verified=True,
        current_edition_identified=True,
        capture_implemented=True,
        parser_implemented=True,
        parser_validated=True,
        company_observations_loaded=True,
        observation_layer="public_source_observations",
        canonical_integration_validated=False,
        public_export_enabled=True,
        population_scopes_complete=True,
        latest_source_reference_date=None,
        last_successful_investigation_on="2026-09-20",
        monitoring_status="NEVER_CHECKED",
        unresolved_issue=[
            "The official current Ferrara pages expose page-update metadata but no single positive source-reference date for all three physical publications; latest_source_reference_date therefore remains unset rather than inferred.",
            "Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure.",
        ],
        actionable_issue=False,
        coverage_status="VALIDATED",
        terminal_reason=None,
        completion_evidence=[
            "docs/sources/ferrara-operational-check-2026-09-20.md",
            "src/white_list_archive/parsers/ferrara_tables.py",
            "tests/test_ferrara_parser_semantics.py",
            "tests/test_ferrara_public_bundle.py",
            "data/publication/multi_prefecture_pilot.json",
        ],
        known_content_sha256=[
            "0d631e678b7f85bb84d265b09b8de6fcffa09cc4a49b84be37c6c1d7b9dcd6d9",
            "c7437cdeebd1a64d4a6de8bbe5e8c108a688269409b7c772e8a6c87162e588e7",
            "4fdf292b1538892c7b5ff79d3c0c14e0ed3b5830effb791316b0fddb8c90ae01",
            "97d9af0d587af0b7d93d31df33bd612440bf5be5b48b57872d436e2afeb164ec",
            "99f519101dccff84dddd9753f0d6fa27170c33b1982858afe9fdf9ebbc63c57e",
            "07c27b38e48a879aa0d1efff4710bf7dbbf1bb323e59f62eb0b0b796a75a46d8",
            "9cea950d37f653d0356edb9a46a7f43665a382e771c969bc93f7027f95fecf9e",
            "ac7dd77f1c4633c27a62c0ad7e074f507a10b091a327c2fc1072cfb52fd45664",
            "0657c7e0f0b9fb8ad7f0b341682716d695132e61131adc92407627a5cae82bae",
        ],
        evidence=[
            "data/source_registry/verified_primary_pages.csv",
            "data/source_registry/source_series_inventory.csv",
            "data/publication/multi_prefecture_pilot.json",
            "docs/sources/ferrara-operational-check-2026-09-20.md",
        ],
        last_completed_coverage_stage="VALIDATED",
    )

    LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
