ALTER TABLE geo.address_geocode_result
    ADD COLUMN provider_endpoint text NULL,
    ADD COLUMN provider_data_updated timestamptz NULL,
    ADD COLUMN query_text text NULL,
    ADD COLUMN normalised_street_name text NULL,
    ADD COLUMN normalised_house_number text NULL,
    ADD COLUMN normalised_postal_code text NULL,
    ADD COLUMN normalised_locality text NULL,
    ADD COLUMN normalised_admin_unit_l2 text NULL,
    ADD COLUMN normalised_admin_unit_l1 text NULL,
    ADD COLUMN normalised_country_name text NULL,
    ADD COLUMN normalised_country_code char(2) NULL,
    ADD COLUMN provider_attribution text NULL,
    ADD COLUMN provider_licence text NULL,
    ADD COLUMN provider_payload jsonb NULL;

ALTER TABLE geo.address_geocode_result
    ADD CONSTRAINT geocode_provider_endpoint_not_blank
        CHECK (provider_endpoint IS NULL OR btrim(provider_endpoint) <> ''),
    ADD CONSTRAINT geocode_query_not_blank
        CHECK (query_text IS NULL OR btrim(query_text) <> ''),
    ADD CONSTRAINT geocode_normalised_country_upper
        CHECK (
            normalised_country_code IS NULL
            OR normalised_country_code = upper(normalised_country_code)
        );

CREATE INDEX address_geocode_provider_endpoint_idx
    ON geo.address_geocode_result (provider_name, provider_endpoint);

COMMENT ON COLUMN geo.address_geocode_result.query_text IS
    'Exact address query sent to the provider. The canonical/source-supported address remains unchanged.';
COMMENT ON COLUMN geo.address_geocode_result.normalised_street_name IS
    'Provider-normalised street/road name, stored as derived enrichment rather than a rewrite of core.address.';
COMMENT ON COLUMN geo.address_geocode_result.normalised_house_number IS
    'Provider-normalised house/civic number, stored as derived enrichment.';
COMMENT ON COLUMN geo.address_geocode_result.provider_payload IS
    'Original provider candidate payload retained for audit and provider-specific metadata not promoted to standard columns.';
COMMENT ON COLUMN geo.address_geocode_result.provider_endpoint IS
    'Base endpoint used for the provider call. Allows a public, managed or self-hosted implementation to be swapped without changing the data model.';

CREATE TABLE geo.address_country_assessment (
    address_country_assessment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    address_id                    uuid NOT NULL REFERENCES core.address(address_id),
    source_country_code           char(2) NULL,
    derived_country_code          char(2) NULL,
    classification_status_code    text NOT NULL,
    route_code                    text NOT NULL,
    derivation_reason             text NOT NULL,
    reference_scheme              text NULL,
    reference_version             text NULL,
    processing_activity_id        uuid NOT NULL REFERENCES provenance.processing_activity(processing_activity_id),
    system_period                 tstzrange NOT NULL DEFAULT tstzrange(CURRENT_TIMESTAMP, NULL, '[)'),
    created_at                    timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT address_country_source_upper CHECK (
        source_country_code IS NULL OR source_country_code = upper(source_country_code)
    ),
    CONSTRAINT address_country_derived_upper CHECK (
        derived_country_code IS NULL OR derived_country_code = upper(derived_country_code)
    ),
    CONSTRAINT address_country_classification_allowed CHECK (
        classification_status_code IN ('source_explicit','derived_italian','unresolved')
    ),
    CONSTRAINT address_country_route_allowed CHECK (
        route_code IN ('italian_anncsu','foreign_fallback','unresolved_fallback')
    ),
    CONSTRAINT address_country_reason_not_blank CHECK (btrim(derivation_reason) <> ''),
    CONSTRAINT address_country_system_valid CHECK (
        NOT isempty(system_period) AND lower(system_period) IS NOT NULL
    ),
    CONSTRAINT address_country_source_derived_separate CHECK (
        NOT (source_country_code IS NOT NULL AND derived_country_code IS NOT NULL)
    ),
    CONSTRAINT address_country_route_consistency CHECK (
        (route_code = 'italian_anncsu' AND COALESCE(source_country_code, derived_country_code) = 'IT')
        OR (route_code = 'foreign_fallback' AND source_country_code IS NOT NULL AND source_country_code <> 'IT' AND derived_country_code IS NULL)
        OR (route_code = 'unresolved_fallback' AND source_country_code IS NULL AND derived_country_code IS NULL)
    )
);

CREATE INDEX address_country_assessment_address_idx
    ON geo.address_country_assessment (address_id);
CREATE INDEX address_country_assessment_route_idx
    ON geo.address_country_assessment (route_code);
CREATE INDEX address_country_assessment_system_gist
    ON geo.address_country_assessment USING gist (system_period);
CREATE UNIQUE INDEX address_one_current_country_assessment
    ON geo.address_country_assessment (address_id)
    WHERE upper_inf(system_period);

COMMENT ON TABLE geo.address_country_assessment IS
    'Versioned country/routing assessment for canonical addresses. Source-explicit country evidence is kept separate from derived country classification; unresolved addresses never inherit Italy from the publishing authority.';
COMMENT ON COLUMN geo.address_country_assessment.source_country_code IS
    'Country explicitly supported by the source address representation or a dedicated source field; never filled from authority location.';
COMMENT ON COLUMN geo.address_country_assessment.derived_country_code IS
    'Country derived from a versioned reference/matching rule, currently exact Istat municipality-prefix evidence for Italy.';
COMMENT ON COLUMN geo.address_country_assessment.route_code IS
    'Provider routing decision: official Italian ANNCSU, foreign fallback, or unresolved fallback.';
