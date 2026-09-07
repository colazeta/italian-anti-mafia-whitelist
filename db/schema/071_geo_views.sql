CREATE OR REPLACE VIEW mart.address_geography AS
WITH current_geocode AS (
    SELECT DISTINCT ON (g.address_id)
        g.address_id,
        g.latitude,
        g.longitude,
        g.precision_code,
        g.provider_name,
        g.provider_version,
        g.confidence AS geocode_confidence,
        g.matched_address
    FROM geo.address_geocode_result g
    WHERE g.match_status_code = 'accepted'
      AND upper_inf(g.system_period)
    ORDER BY g.address_id, lower(g.system_period) DESC, g.address_geocode_result_id
),
units AS (
    SELECT
        agu.address_id,
        MAX(gu.unit_code) FILTER (WHERE gu.unit_level_code = 'municipality') AS municipality_code,
        MAX(gu.unit_name) FILTER (WHERE gu.unit_level_code = 'municipality') AS municipality_name,
        MAX(gu.scheme_version) FILTER (WHERE gu.unit_level_code = 'municipality') AS municipality_scheme_version,
        MAX(gu.unit_code) FILTER (WHERE gu.unit_level_code IN ('province','metropolitan_city','autonomous_province')) AS province_level_code,
        MAX(gu.unit_name) FILTER (WHERE gu.unit_level_code IN ('province','metropolitan_city','autonomous_province')) AS province_level_name,
        MAX(gu.unit_level_code) FILTER (WHERE gu.unit_level_code IN ('province','metropolitan_city','autonomous_province')) AS province_level_type,
        MAX(gu.scheme_version) FILTER (WHERE gu.unit_level_code IN ('province','metropolitan_city','autonomous_province')) AS province_scheme_version,
        MAX(gu.unit_code) FILTER (WHERE gu.unit_level_code = 'region') AS region_code,
        MAX(gu.unit_name) FILTER (WHERE gu.unit_level_code = 'region') AS region_name,
        MAX(gu.scheme_version) FILTER (WHERE gu.unit_level_code = 'region') AS region_scheme_version,
        MAX(gu.unit_code) FILTER (WHERE gu.unit_level_code = 'nuts1') AS nuts1_code,
        MAX(gu.unit_name) FILTER (WHERE gu.unit_level_code = 'nuts1') AS nuts1_name,
        MAX(gu.scheme_version) FILTER (WHERE gu.unit_level_code = 'nuts1') AS nuts1_version,
        MAX(gu.unit_code) FILTER (WHERE gu.unit_level_code = 'nuts2') AS nuts2_code,
        MAX(gu.unit_name) FILTER (WHERE gu.unit_level_code = 'nuts2') AS nuts2_name,
        MAX(gu.scheme_version) FILTER (WHERE gu.unit_level_code = 'nuts2') AS nuts2_version,
        MAX(gu.unit_code) FILTER (WHERE gu.unit_level_code = 'nuts3') AS nuts3_code,
        MAX(gu.unit_name) FILTER (WHERE gu.unit_level_code = 'nuts3') AS nuts3_name,
        MAX(gu.scheme_version) FILTER (WHERE gu.unit_level_code = 'nuts3') AS nuts3_version
    FROM geo.address_geographic_unit agu
    JOIN geo.geographic_unit gu ON gu.geographic_unit_id = agu.geographic_unit_id
    WHERE upper_inf(agu.system_period)
      AND gu.effective_period @> CURRENT_DATE
    GROUP BY agu.address_id
)
SELECT
    a.address_id,
    a.full_address,
    a.street_name,
    a.locator_designator,
    a.postal_code,
    a.locality AS source_locality,
    a.admin_unit_l2 AS source_admin_unit_l2,
    a.admin_unit_l1 AS source_admin_unit_l1,
    a.country_code,
    cg.latitude,
    cg.longitude,
    cg.precision_code AS coordinate_precision,
    cg.provider_name AS geocode_provider,
    cg.provider_version AS geocode_provider_version,
    cg.geocode_confidence,
    cg.matched_address,
    u.municipality_code,
    u.municipality_name,
    u.municipality_scheme_version,
    u.province_level_code,
    u.province_level_name,
    u.province_level_type,
    u.province_scheme_version,
    u.region_code,
    u.region_name,
    u.region_scheme_version,
    u.nuts1_code,
    u.nuts1_name,
    u.nuts1_version,
    u.nuts2_code,
    u.nuts2_name,
    u.nuts2_version,
    u.nuts3_code,
    u.nuts3_name,
    u.nuts3_version
FROM core.address a
LEFT JOIN current_geocode cg ON cg.address_id = a.address_id
LEFT JOIN units u ON u.address_id = a.address_id;

COMMENT ON VIEW mart.address_geography IS
    'Wide statistical geography surface: source address plus accepted coordinates and versioned municipality/province-level/region/NUTS assignments. Geography enrichment remains derived and provenance-aware.';
