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
