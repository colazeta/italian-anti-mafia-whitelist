from __future__ import annotations

import json
from pathlib import Path

from white_list_archive.persistence.capture_manifest import (
    _edition_code_for_manifest,
    load_context,
)

ROOT = Path(__file__).resolve().parents[1]


def test_capture_operational_schema_patch_is_applied():
    apply_sql = (ROOT / "db/apply.sql").read_text(encoding="utf-8")
    assert "045_capture_operational_metadata.sql" in apply_sql
    assert "047_temporal_capture_identity.sql" in apply_sql
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
    temporal = (ROOT / "db/schema/047_temporal_capture_identity.sql").read_text(encoding="utf-8")
    for required in [
        "declared_reference_date",
        "not SourceEdition identity",
        "source_capture_provenance_immutable",
        "create a new capture/check instead",
        "must not be silently promoted to edition identity",
    ]:
        assert required in temporal


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


def test_archive_first_capture_does_not_turn_reference_date_into_edition_identity():
    code, legacy = _edition_code_for_manifest(
        {
            "capture_id": "9c21f13c-62f1-487d-a479-999e5cbbfd32",
            "reference_date": "2026-09-22",
        }
    )
    assert code is None
    assert legacy is False


def test_explicit_edition_label_is_kept_separate_from_declared_reference_date():
    code, legacy = _edition_code_for_manifest(
        {
            "capture_id": "9c21f13c-62f1-487d-a479-999e5cbbfd32",
            "edition_code": "edition-2026-09-current",
            "reference_date": "2026-09-22",
        }
    )
    assert code == "edition-2026-09-current"
    assert legacy is False


def test_legacy_cosenza_reference_date_identity_remains_compatible():
    manifest = json.loads(
        (ROOT / "data/captures/cosenza/combined_2026-08-03.json").read_text(encoding="utf-8")
    )
    code, legacy = _edition_code_for_manifest(manifest)
    assert code == "2026-08-03"
    assert legacy is True
