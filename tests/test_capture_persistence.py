from __future__ import annotations

import json
from pathlib import Path

from white_list_archive.persistence.capture_manifest import load_context

ROOT = Path(__file__).resolve().parents[1]


def test_capture_operational_schema_patch_is_applied():
    apply_sql = (ROOT / "db/apply.sql").read_text(encoding="utf-8")
    assert "045_capture_operational_metadata.sql" in apply_sql
    ddl = (ROOT / "db/schema/045_capture_operational_metadata.sql").read_text(encoding="utf-8")
    for required in [
        "registry.content_storage_status",
        "authority_code",
        "series_code",
        "edition_code",
        "storage_status_code",
        "resolved_url",
        "etag",
        "last_modified",
        "ALTER COLUMN effective_period DROP NOT NULL",
        "DROP CONSTRAINT white_list_register_effective_valid",
        "effective_period IS NULL",
    ]:
        assert required in ddl


def test_cosenza_manifest_resolves_against_research_registry_without_guessing_source_identity():
    manifest = json.loads(
        (ROOT / "data/captures/cosenza/combined_2026-06-28.json").read_text(encoding="utf-8")
    )
    context = load_context(
        manifest,
        ROOT / "data/source_registry/territorial_authorities.csv",
        ROOT / "data/source_registry/source_series_inventory.csv",
    )
    assert context.authority_key == "cosenza"
    assert context.authority_name == "Prefettura - Ufficio Territoriale del Governo di Cosenza"
    assert context.authority_type_code == "prefecture_utg"
    assert context.source_series_key == "cosenza-combined"
    assert context.regime_code == "WL-REGIME-L190-2012"
    assert context.population_types == ("listed", "applicant")


def test_stable_codes_are_internal_project_keys_not_source_identifiers():
    ddl = (ROOT / "db/schema/045_capture_operational_metadata.sql").read_text(encoding="utf-8")
    assert "not an administrative identifier" in ddl
    assert "Stable internal project code" in ddl
