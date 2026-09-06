\set ON_ERROR_STOP on
BEGIN;
\ir schema/001_extensions.sql
\ir schema/010_registry.sql
\ir schema/015_provenance_base.sql
\ir schema/020_core.sql
\ir schema/030_whitelist.sql
\ir schema/040_source.sql
\ir schema/045_capture_operational_metadata.sql
\ir schema/046_parse_operational_metadata.sql
\ir schema/050_mapping_provenance.sql
\ir schema/055_semantic_projection.sql
\ir schema/060_derived_governance.sql
\ir schema/070_views.sql
\ir seeds/010_lookup_values.sql
\ir seeds/020_regime_and_sector_2020.sql
\ir seeds/030_canonical_fields.sql
\ir seeds/040_governance.sql
COMMIT;
