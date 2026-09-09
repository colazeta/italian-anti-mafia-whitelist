CREATE TABLE geo.fallback_geocode_run (
    fallback_geocode_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    processing_activity_id uuid NOT NULL REFERENCES provenance.processing_activity(processing_activity_id),
    provider_name text NOT NULL,
    provider_endpoint text NOT NULL,
    provider_version text NULL,
    provider_data_updated timestamptz NULL,
    configuration_hash char(64) NOT NULL,
    eligible_address_count integer NOT NULL DEFAULT 0,
    selected_address_count integer NOT NULL DEFAULT 0,
    expired_ineligible_count integer NOT NULL DEFAULT 0,
    reused_current_count integer NOT NULL DEFAULT 0,
    network_query_count integer NOT NULL DEFAULT 0,
    candidate_address_count integer NOT NULL DEFAULT 0,
    candidate_row_count integer NOT NULL DEFAULT 0,
    not_found_count integer NOT NULL DEFAULT 0,
    error_count integer NOT NULL DEFAULT 0,
    status_code text NOT NULL DEFAULT 'running',
    started_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at timestamptz NULL,
    error_text text NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fallback_run_provider_not_blank CHECK (btrim(provider_name) <> '' AND btrim(provider_endpoint) <> ''),
    CONSTRAINT fallback_run_hash_format CHECK (configuration_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT fallback_run_counts_nonnegative CHECK (
        eligible_address_count >= 0 AND selected_address_count >= 0 AND expired_ineligible_count >= 0
        AND reused_current_count >= 0 AND network_query_count >= 0
        AND candidate_address_count >= 0 AND candidate_row_count >= 0
        AND not_found_count >= 0 AND error_count >= 0
    ),
    CONSTRAINT fallback_run_status_allowed CHECK (status_code IN ('running','succeeded','failed'))
);

CREATE TABLE geo.fallback_geocode_run_item (
    fallback_geocode_run_item_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fallback_geocode_run_id uuid NOT NULL REFERENCES geo.fallback_geocode_run(fallback_geocode_run_id) ON DELETE CASCADE,
    address_id uuid NOT NULL REFERENCES core.address(address_id),
    eligibility_reason_code text NOT NULL,
    source_route_code text NOT NULL,
    source_country_code char(2) NULL,
    country_filter_code char(2) NULL,
    upstream_geocode_result_id uuid NULL REFERENCES geo.address_geocode_result(address_geocode_result_id),
    upstream_provider_version text NULL,
    cache_disposition_code text NOT NULL,
    result_status_code text NULL,
    candidate_count integer NOT NULL DEFAULT 0,
    query_text text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fallback_item_reason_allowed CHECK (
        eligibility_reason_code IN ('source_foreign','country_unresolved','anncsu_not_found')
    ),
    CONSTRAINT fallback_item_route_allowed CHECK (
        source_route_code IN ('foreign_fallback','unresolved_fallback','italian_anncsu')
    ),
    CONSTRAINT fallback_item_reason_route_consistency CHECK (
        (eligibility_reason_code = 'source_foreign' AND source_route_code = 'foreign_fallback')
        OR (eligibility_reason_code = 'country_unresolved' AND source_route_code = 'unresolved_fallback')
        OR (eligibility_reason_code = 'anncsu_not_found' AND source_route_code = 'italian_anncsu' AND upstream_geocode_result_id IS NOT NULL)
    ),
    CONSTRAINT fallback_item_country_upper CHECK (
        (source_country_code IS NULL OR source_country_code = upper(source_country_code))
        AND (country_filter_code IS NULL OR country_filter_code = upper(country_filter_code))
    ),
    CONSTRAINT fallback_item_cache_allowed CHECK (cache_disposition_code IN ('queried','reused_current')),
    CONSTRAINT fallback_item_status_allowed CHECK (
        result_status_code IS NULL OR result_status_code IN ('candidate','not_found','error')
    ),
    CONSTRAINT fallback_item_candidate_nonnegative CHECK (candidate_count >= 0),
    CONSTRAINT fallback_item_query_not_blank CHECK (btrim(query_text) <> ''),
    CONSTRAINT fallback_item_one_per_run UNIQUE (fallback_geocode_run_id, address_id)
);

ALTER TABLE geo.address_geocode_result
    ADD COLUMN routing_stage_code text NULL,
    ADD COLUMN routing_reason_code text NULL,
    ADD COLUMN upstream_geocode_result_id uuid NULL REFERENCES geo.address_geocode_result(address_geocode_result_id),
    ADD COLUMN fallback_geocode_run_id uuid NULL REFERENCES geo.fallback_geocode_run(fallback_geocode_run_id);

ALTER TABLE geo.address_geocode_result
    ADD CONSTRAINT geocode_routing_stage_allowed CHECK (
        routing_stage_code IS NULL OR routing_stage_code IN ('fallback')
    ),
    ADD CONSTRAINT geocode_routing_reason_allowed CHECK (
        routing_reason_code IS NULL OR routing_reason_code IN ('source_foreign','country_unresolved','anncsu_not_found')
    ),
    ADD CONSTRAINT geocode_fallback_metadata_consistency CHECK (
        (routing_stage_code IS NULL AND routing_reason_code IS NULL AND fallback_geocode_run_id IS NULL)
        OR (routing_stage_code = 'fallback' AND routing_reason_code IS NOT NULL AND fallback_geocode_run_id IS NOT NULL)
    ),
    ADD CONSTRAINT geocode_upstream_reason_consistency CHECK (
        routing_reason_code <> 'anncsu_not_found' OR upstream_geocode_result_id IS NOT NULL
    );

CREATE INDEX fallback_geocode_run_provider_idx
    ON geo.fallback_geocode_run (provider_name, provider_endpoint, started_at DESC);
CREATE INDEX fallback_geocode_item_address_idx
    ON geo.fallback_geocode_run_item (address_id, created_at DESC);
CREATE INDEX fallback_geocode_item_reason_idx
    ON geo.fallback_geocode_run_item (eligibility_reason_code, cache_disposition_code);
CREATE INDEX address_geocode_fallback_stage_idx
    ON geo.address_geocode_result (routing_stage_code, routing_reason_code)
    WHERE routing_stage_code = 'fallback';

COMMENT ON TABLE geo.fallback_geocode_run IS
    'Operational provenance for managed/self-hosted fallback geocoding runs. Public OSMF Nominatim is not permitted by the fallback runner.';
COMMENT ON TABLE geo.fallback_geocode_run_item IS
    'Per-address eligibility, upstream ANNCSU dependency, country filter and cache disposition for each fallback geocoding run.';
COMMENT ON COLUMN geo.fallback_geocode_run.expired_ineligible_count IS
    'Previously current fallback results closed at run start because the address no longer met the explicit fallback eligibility contract.';
COMMENT ON COLUMN geo.address_geocode_result.routing_reason_code IS
    'Why the fallback provider was eligible: source-explicit foreign country, unresolved country routing, or an ANNCSU not_found outcome.';
COMMENT ON COLUMN geo.address_geocode_result.upstream_geocode_result_id IS
    'For anncsu_not_found fallback, the exact upstream ANNCSU terminal result that made the address eligible.';
