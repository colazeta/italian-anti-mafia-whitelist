from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
LEGACY_HELPER = HERE.with_name("lucca-finalize.py")

spec = importlib.util.spec_from_file_location("lucca_finalize_base", LEGACY_HELPER)
if spec is None or spec.loader is None:
    raise RuntimeError("Unable to load Lucca base finalizer")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def update_coverage() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if "prefectures" not in data or not isinstance(data["prefectures"], list):
        raise RuntimeError("national_coverage.json schema drift: top-level prefectures list missing")
    rows = [item for item in data["prefectures"] if item.get("authority_key") == "lucca"]
    if len(rows) != 1:
        raise RuntimeError(f"Lucca national coverage row cardinality drift: {len(rows)}")
    item = rows[0]
    item.update(
        {
            "official_landing_page": base.LANDING,
            "source_verified": True,
            "current_edition_identified": True,
            "capture_implemented": True,
            "parser_implemented": True,
            "parser_validated": True,
            "company_observations_loaded": True,
            "observation_layer": "public_source_observations",
            "canonical_integration_validated": False,
            "public_export_enabled": True,
            "durable_evidence_verified": False,
            "population_scopes_complete": True,
            "latest_source_reference_date": "2026-09-11",
            "last_successful_investigation_on": "2026-09-19",
            "coverage_status": "VALIDATED",
            "terminal_reason": None,
            "unresolved_issue": [
                "Canonical hosted-database integration and independent durable-evidence verification remain separate infrastructure gates; the 15 September landing update timestamp is publication-surface provenance and is not promoted to a company decision or legal-effect date."
            ],
            "actionable_issue": False,
            "completion_evidence": [
                "docs/sources/lucca-operational-check-2026-09-19.md",
                "src/white_list_archive/parsers/lucca_tables.py",
                "tests/test_lucca_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [base.LISTED_SHA, base.APPLICANTS_SHA],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                "docs/sources/lucca-operational-check-2026-09-19.md",
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


base.update_coverage = update_coverage
_base_cleanup = base.remove_transactional_files


def remove_transactional_files() -> None:
    _base_cleanup()
    HERE.unlink(missing_ok=True)


base.remove_transactional_files = remove_transactional_files
base.main()
