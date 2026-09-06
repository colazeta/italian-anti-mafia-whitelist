from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_required_schema_files_exist():
    required = [
        "db/schema/001_extensions.sql",
        "db/schema/010_registry.sql",
        "db/schema/015_provenance_base.sql",
        "db/schema/020_core.sql",
        "db/schema/030_whitelist.sql",
        "db/schema/040_source.sql",
        "db/schema/050_mapping_provenance.sql",
        "db/schema/060_derived_governance.sql",
        "db/schema/070_views.sql",
    ]
    for rel in required:
        assert (ROOT / rel).is_file(), rel


def test_audited_design_elements_are_present():
    source_sql = read("db/schema/040_source.sql")
    whitelist_sql = read("db/schema/030_whitelist.sql")
    provenance_sql = read("db/schema/050_mapping_provenance.sql")

    assert "CREATE TABLE source.parse_run" in source_sql
    assert "UNIQUE (parse_run_id, record_locator)" in source_sql
    assert "record_observation" not in source_sql
    assert "edition_resource" not in source_sql

    assert "system_period" in whitelist_sql
    assert "EXCLUDE USING gist" in whitelist_sql
    assert "sector_listing_status_code" in whitelist_sql

    assert "entity_resolution_one_current_accepted" in provenance_sql
    assert "entity_resolution_accepted_system_no_overlap" in provenance_sql
    assert "procedure_resolution_one_current_accepted" in provenance_sql
    assert "procedure_resolution_accepted_system_no_overlap" in provenance_sql
    assert "CREATE TABLE provenance.evidence_item" in provenance_sql


def test_requested_sector_is_not_a_relationship_sector_status():
    seeds = read("db/seeds/010_lookup_values.sql")
    marker = "INSERT INTO registry.sector_listing_status(code,label) VALUES"
    section = seeds.split(marker, 1)[1].split("ON CONFLICT DO NOTHING;", 1)[0]
    assert "requested" not in section


def test_current_sector_scheme_uses_verified_effective_date():
    seed = read("db/seeds/020_regime_and_sector_2020.sql")
    assert "2020-06-07" in seed
    for roman in ("'I'", "'II'", "'III'", "'IV'", "'V'", "'VI'", "'VII'", "'VIII'", "'IX'", "'X'"):
        assert roman in seed


def test_raw_data_is_gitignored():
    ignore = read(".gitignore")
    assert "/data/raw/" in ignore


def test_source_resource_supports_non_web_provenance():
    ddl = read("db/schema/040_source.sql")
    assert "canonical_locator" in ddl
    assert "web_url" in ddl
    assert "canonical_url" not in ddl


def test_canonical_dictionary_covers_temporal_and_provenance_fields():
    seed = read("db/seeds/030_canonical_fields.sql")
    for field in [
        "relationship_state.system_period",
        "procedure.system_period",
        "source.capture",
        "source.origin_type",
        "provenance.processing_activity",
    ]:
        assert field in seed
