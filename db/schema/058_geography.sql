CREATE TABLE geo.geographic_unit (
    geographic_unit_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_code               text NOT NULL,
    scheme_version            text NOT NULL,
    unit_level_code           text NOT NULL REFERENCES registry.geographic_unit_level(code),
    unit_code                 text NOT NULL,
    unit_name                 text NOT NULL,
    parent_geographic_unit_id uuid NULL REFERENCES geo.geographic_unit(geographic_unit_id),
    effective_period          daterange NOT NULL,
    created_at                timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT geographic_unit_scheme_not_blank CHECK (btrim(scheme_code) <> ''),
    CONSTRAINT geographic_unit_version_not_blank CHECK (btrim(scheme_version) <> ''),
    CONSTRAINT geographic_unit_code_not_blank CHECK (btrim(unit_code) <> ''),
    CONSTRAINT geographic_unit_name_not_blank CHECK (btrim(unit_name) <> ''),
    CONSTRAINT geographic_unit_effective_valid CHECK (NOT isempty(effective_period) AND lower(effective_period) IS NOT NULL),
    CONSTRAINT geographic_unit_identity_unique UNIQUE (scheme_code, scheme_version, unit_level_code, unit_code)
);

CREATE INDEX geographic_unit_parent_idx ON geo.geographic_unit (parent_geographic_unit_id);
CREATE INDEX geographic_unit_lookup_idx ON geo.geographic_unit (scheme_code, scheme_version, unit_level_code, unit_code);
CREATE INDEX geographic_unit_effective_gist ON geo.geographic_unit USING gist (effective_period);

COMMENT ON TABLE geo.geographic_unit IS
    'Versioned administrative/statistical geography unit. Supports ISTAT administrative units and NUTS versions without conflating the two schemes.';

CREATE TABLE geo.address_geocode_result (
    address_geocode_result_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    address_id                uuid NOT NULL REFERENCES core.address(address_id),
    provider_name             text NOT NULL,
    provider_version          text NULL,
    provider_result_id        text NULL,
    candidate_rank            integer NOT NULL DEFAULT 1,
    match_status_code         text NOT NULL REFERENCES registry.geocode_match_status(code),
    precision_code            text NULL REFERENCES registry.geocode_precision(code),
    latitude                  double precision NULL,
    longitude                 double precision NULL,
    confidence                numeric(6,5) NULL,
    matched_address           text NULL,
    processing_activity_id    uuid NOT NULL REFERENCES provenance.processing_activity(processing_activity_id),
    system_period             tstzrange NOT NULL DEFAULT tstzrange(CURRENT_TIMESTAMP, NULL, '[)'),
    created_at                timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT geocode_provider_not_blank CHECK (btrim(provider_name) <> ''),
    CONSTRAINT geocode_candidate_positive CHECK (candidate_rank >= 1),
    CONSTRAINT geocode_latitude_range CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CONSTRAINT geocode_longitude_range CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    CONSTRAINT geocode_confidence_range CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    CONSTRAINT geocode_system_valid CHECK (NOT isempty(system_period) AND lower(system_period) IS NOT NULL),
    CONSTRAINT geocode_coordinate_pair CHECK ((latitude IS NULL) = (longitude IS NULL)),
    CONSTRAINT geocode_accepted_has_coordinates CHECK (match_status_code <> 'accepted' OR latitude IS NOT NULL),
    CONSTRAINT geocode_result_identity_unique UNIQUE (address_id, provider_name, provider_version, candidate_rank, processing_activity_id)
);

CREATE INDEX address_geocode_address_idx ON geo.address_geocode_result (address_id);
CREATE INDEX address_geocode_status_idx ON geo.address_geocode_result (match_status_code);
CREATE INDEX address_geocode_system_gist ON geo.address_geocode_result USING gist (system_period);
CREATE UNIQUE INDEX address_one_current_accepted_geocode
    ON geo.address_geocode_result (address_id)
    WHERE match_status_code = 'accepted' AND upper_inf(system_period);

COMMENT ON TABLE geo.address_geocode_result IS
    'Provider-specific geocoding candidates/results. Coordinates are derived enrichment, never a rewrite of the original source address.';

CREATE TABLE geo.address_geographic_unit (
    address_geographic_unit_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    address_id                 uuid NOT NULL REFERENCES core.address(address_id),
    geographic_unit_id         uuid NOT NULL REFERENCES geo.geographic_unit(geographic_unit_id),
    geocode_result_id          uuid NULL REFERENCES geo.address_geocode_result(address_geocode_result_id),
    assignment_method_code     text NOT NULL REFERENCES registry.geographic_assignment_method(code),
    confidence                 numeric(6,5) NULL,
    processing_activity_id     uuid NOT NULL REFERENCES provenance.processing_activity(processing_activity_id),
    system_period              tstzrange NOT NULL DEFAULT tstzrange(CURRENT_TIMESTAMP, NULL, '[)'),
    created_at                 timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT address_geographic_confidence_range CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    CONSTRAINT address_geographic_system_valid CHECK (NOT isempty(system_period) AND lower(system_period) IS NOT NULL)
);

CREATE INDEX address_geographic_address_idx ON geo.address_geographic_unit (address_id);
CREATE INDEX address_geographic_unit_idx ON geo.address_geographic_unit (geographic_unit_id);
CREATE INDEX address_geographic_system_gist ON geo.address_geographic_unit USING gist (system_period);

COMMENT ON TABLE geo.address_geographic_unit IS
    'Provenance-aware assignment of a canonical address to administrative/statistical units such as municipality, province, region and NUTS levels.';
