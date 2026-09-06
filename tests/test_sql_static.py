from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def schema_text() -> str:
    return "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((ROOT / "db/schema").glob("*.sql"))
    )


def test_apply_order_respects_dependencies_and_is_atomic():
    text = (ROOT / "db/apply.sql").read_text(encoding="utf-8")
    ordered = [
        "001_extensions.sql",
        "010_registry.sql",
        "015_provenance_base.sql",
        "020_core.sql",
        "030_whitelist.sql",
        "040_source.sql",
        "050_mapping_provenance.sql",
        "060_derived_governance.sql",
        "070_views.sql",
    ]
    positions = [text.index(name) for name in ordered]
    assert positions == sorted(positions)
    assert "BEGIN;" in text and text.rstrip().endswith("COMMIT;")
    for p in (ROOT / "db/schema").glob("*.sql"):
        body = p.read_text(encoding="utf-8").strip().upper()
        assert not body.startswith("BEGIN;")
        assert not body.endswith("COMMIT;")


def test_no_postgresql_enum_types_are_used():
    ddl = schema_text().upper()
    assert "CREATE TYPE" not in ddl
    assert " AS ENUM" not in ddl


def test_open_system_ranges_are_truly_unbounded():
    ddl = schema_text()
    assert "'infinity'::timestamptz" not in ddl
    assert "tstzrange(CURRENT_TIMESTAMP, NULL, '[)')" in ddl
    tests = (ROOT / "db/tests/001_constraints.sql").read_text(encoding="utf-8")
    assert "upper_inf(r)" in tests


def test_tri_temporal_constraints_include_system_time_and_unknown_wildcard():
    ddl = (ROOT / "db/schema/030_whitelist.sql").read_text(encoding="utf-8")
    for name in [
        "relationship_state_tri_temporal_no_overlap",
        "relationship_sector_state_tri_temporal_no_overlap",
        "procedure_version_tri_temporal_no_overlap",
    ]:
        assert name in ddl
    assert "system_period WITH &&" in ddl
    assert "COALESCE(effective_period, daterange(NULL, NULL, '()'))" in ddl
    assert "current_known_effect_no_overlap" not in ddl


def test_content_object_is_sha256_addressed_and_raw_values_are_immutable():
    ddl = (ROOT / "db/schema/040_source.sql").read_text(encoding="utf-8")
    assert "^[0-9a-f]{64}$" in ddl
    assert "content_object_identity_immutable" in ddl
    assert "source_field_value_immutable" in ddl


def test_source_field_values_are_schema_consistent():
    ddl = (ROOT / "db/schema/040_source.sql").read_text(encoding="utf-8")
    assert "source_field_value_record_schema_fk" in ddl
    assert "source_field_value_field_schema_fk" in ddl
    assert "schema_version_id      uuid NOT NULL" in ddl


def test_taxonomy_and_relationship_sector_guards_exist():
    ddl = (ROOT / "db/schema/030_whitelist.sql").read_text(encoding="utf-8")
    assert "sector_scheme_version_no_overlap" in ddl
    assert "sector_membership_period_guard" in ddl
    assert "relationship_sector_membership_guard" in ddl


def test_processing_lineage_is_attached_to_canonical_versions():
    core = (ROOT / "db/schema/020_core.sql").read_text(encoding="utf-8")
    wl = (ROOT / "db/schema/030_whitelist.sql").read_text(encoding="utf-8")
    assert core.count("processing_activity_id") >= 5
    assert wl.count("processing_activity_id") >= 3


def test_derived_events_have_explicit_input_links():
    ddl = (ROOT / "db/schema/060_derived_governance.sql").read_text(encoding="utf-8")
    assert "derived_event_relationship_state_input" in ddl
    assert "derived_event_sector_state_input" in ddl
    assert "derived_event_procedure_version_input" in ddl


def test_dissemination_is_profile_scoped():
    ddl = (ROOT / "db/schema/060_derived_governance.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE governance.dissemination_profile" in ddl
    assert "PRIMARY KEY (dissemination_profile_id, canonical_field_id)" in ddl


def test_source_series_type_does_not_encode_population_or_sector_scope():
    seed = (ROOT / "db/seeds/010_lookup_values.sql").read_text(encoding="utf-8")
    section = seed.split("INSERT INTO registry.source_series_type(code,label) VALUES", 1)[1].split("ON CONFLICT DO NOTHING;", 1)[0]
    assert "listed_entities" not in section
    assert "applicants" not in section
    assert "sector_specific" not in section
    assert "'list'" in section


def test_sector_preferred_label_has_one_source_of_truth():
    ddl = (ROOT / "db/schema/030_whitelist.sql").read_text(encoding="utf-8")
    sector_table = ddl.split("CREATE TABLE whitelist.sector_concept (", 1)[1].split(");", 1)[0]
    assert "preferred_label" not in sector_table
    assert "sector_preferred_label_no_overlap" in ddl


def test_procedure_mentions_cannot_cross_source_records():
    sql = (ROOT / "db/schema/040_source.sql").read_text()
    assert "UNIQUE (entity_mention_id, parsed_record_id)" in sql
    assert "FOREIGN KEY (entity_mention_id, parsed_record_id)" in sql
    assert "REFERENCES source.entity_mention(entity_mention_id, parsed_record_id)" in sql
