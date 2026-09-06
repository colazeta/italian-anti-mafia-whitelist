CREATE OR REPLACE VIEW mart.current_entity_name AS
SELECT DISTINCT ON (n.legal_entity_id)
    n.legal_entity_id,
    n.entity_name_id,
    n.name,
    n.normalised_name,
    n.language_code
FROM core.entity_name n
WHERE n.name_type_code = 'legal_name'
  AND upper_inf(n.system_period)
  AND n.observation_period @> CURRENT_TIMESTAMP
  AND (n.effective_period IS NULL OR n.effective_period @> CURRENT_DATE)
ORDER BY n.legal_entity_id,
         CASE n.language_code WHEN 'it' THEN 0 WHEN 'en' THEN 1 ELSE 2 END,
         lower(n.system_period) DESC,
         lower(n.observation_period) DESC,
         n.name;

CREATE OR REPLACE VIEW mart.current_relationship_state AS
SELECT DISTINCT ON (s.relationship_id)
    s.*
FROM whitelist.relationship_state_version s
WHERE upper_inf(s.system_period)
  AND s.observation_period @> CURRENT_TIMESTAMP
  AND (s.effective_period IS NULL OR s.effective_period @> CURRENT_DATE)
ORDER BY s.relationship_id, lower(s.system_period) DESC, s.relationship_state_version_id;

CREATE OR REPLACE VIEW mart.current_relationship_sector AS
SELECT
    rs.relationship_sector_id,
    rs.relationship_id,
    rs.sector_concept_id,
    ssv.scheme_membership_id,
    ssv.sector_listing_status_code
FROM whitelist.relationship_sector rs
JOIN LATERAL (
    SELECT s.*
    FROM whitelist.relationship_sector_state_version s
    WHERE s.relationship_sector_id = rs.relationship_sector_id
      AND upper_inf(s.system_period)
      AND s.observation_period @> CURRENT_TIMESTAMP
      AND (s.effective_period IS NULL OR s.effective_period @> CURRENT_DATE)
    ORDER BY lower(s.system_period) DESC, s.relationship_sector_state_version_id
    LIMIT 1
) ssv ON true
WHERE ssv.sector_listing_status_code = 'listed';

CREATE OR REPLACE VIEW mart.current_whitelist AS
SELECT
    r.relationship_id,
    e.legal_entity_id,
    n.name AS legal_name,
    reg.register_id,
    reg.register_code,
    reg.official_name AS register_name,
    a.public_authority_id,
    a.preferred_name AS authority_name,
    regime.regime_id,
    regime.regime_code,
    state.administrative_disposition_code,
    state.legal_effect_status_code,
    state.nominal_valid_from,
    state.nominal_valid_until,
    sec.sector_concept_id,
    sec.concept_code AS sector_concept_code,
    COALESCE(sector_label.label, membership.legal_label) AS sector_label,
    membership.notation AS sector_notation,
    scheme.version_code AS sector_scheme_version
FROM whitelist.white_list_relationship r
JOIN core.legal_entity e ON e.legal_entity_id = r.legal_entity_id
LEFT JOIN mart.current_entity_name n ON n.legal_entity_id = e.legal_entity_id
JOIN whitelist.white_list_register reg ON reg.register_id = r.register_id
JOIN core.public_authority a ON a.public_authority_id = reg.public_authority_id
JOIN whitelist.white_list_regime regime ON regime.regime_id = reg.regime_id
JOIN mart.current_relationship_state state ON state.relationship_id = r.relationship_id
LEFT JOIN mart.current_relationship_sector crs ON crs.relationship_id = r.relationship_id
LEFT JOIN whitelist.sector_concept sec ON sec.sector_concept_id = crs.sector_concept_id
LEFT JOIN LATERAL (
    SELECT scl.label
    FROM whitelist.sector_concept_label scl
    WHERE scl.sector_concept_id = sec.sector_concept_id
      AND scl.label_type_code = 'preferred'
      AND scl.language_code = 'it'
      AND (scl.effective_period IS NULL OR scl.effective_period @> CURRENT_DATE)
    ORDER BY lower(scl.effective_period) DESC NULLS LAST, scl.label
    LIMIT 1
) sector_label ON true
LEFT JOIN whitelist.sector_scheme_membership membership ON membership.scheme_membership_id = crs.scheme_membership_id
LEFT JOIN whitelist.sector_scheme_version scheme ON scheme.scheme_version_id = membership.scheme_version_id;

CREATE OR REPLACE VIEW mart.source_schema_registry AS
SELECT
    ss.source_schema_id,
    ss.schema_name,
    ssv.schema_version_id,
    ssv.structural_fingerprint,
    ssv.first_observed_at,
    ssv.last_observed_at,
    fd.field_definition_id,
    fd.ordinal_position,
    fd.source_label,
    fd.normalised_source_label,
    fd.observed_datatype,
    fd.observed_cardinality,
    series.series_id,
    series.series_name,
    series.publisher_authority_id
FROM source.source_schema ss
JOIN source.source_schema_version ssv ON ssv.source_schema_id = ss.source_schema_id
JOIN source.source_field_definition fd ON fd.schema_version_id = ssv.schema_version_id
LEFT JOIN source.source_series series ON series.series_id = ss.series_id;
