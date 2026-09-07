BEGIN;

DO $$
DECLARE
    activity_id uuid;
    address_id_v uuid;
    got record;
BEGIN
    INSERT INTO provenance.processing_activity(
        activity_type_code, software_name, software_version,
        configuration_hash, started_at, completed_at
    ) VALUES (
        'geocode', 'address-normalisation-test', '1', repeat('b', 64),
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
    ) RETURNING processing_activity_id INTO activity_id;

    INSERT INTO core.address(full_address, processing_activity_id)
    VALUES ('RENDE(CS), VIALE ORSO MARIO CORBINO 33', activity_id)
    RETURNING address_id INTO address_id_v;

    INSERT INTO geo.address_geocode_result(
        address_id,
        provider_name,
        provider_endpoint,
        provider_version,
        provider_data_updated,
        provider_result_id,
        candidate_rank,
        match_status_code,
        precision_code,
        latitude,
        longitude,
        query_text,
        matched_address,
        normalised_street_name,
        normalised_house_number,
        normalised_postal_code,
        normalised_locality,
        normalised_admin_unit_l2,
        normalised_admin_unit_l1,
        normalised_country_name,
        normalised_country_code,
        provider_attribution,
        provider_licence,
        provider_payload,
        processing_activity_id
    ) VALUES (
        address_id_v,
        'nominatim',
        'https://geocoder.example.test/nominatim',
        '5.3.2',
        '2026-09-07T00:00:00Z',
        'osm:way:12345',
        1,
        'candidate',
        'address',
        39.331,
        16.184,
        'RENDE(CS), VIALE ORSO MARIO CORBINO 33',
        '33, Viale Orso Mario Corbino, Rende, Calabria, Italia',
        'Viale Orso Mario Corbino',
        '33',
        '87036',
        'Rende',
        'Cosenza',
        'Calabria',
        'Italia',
        'IT',
        'Data © OpenStreetMap contributors',
        'ODbL',
        '{"type":"Feature"}'::jsonb,
        activity_id
    );

    SELECT * INTO got
    FROM mart.address_normalisation
    WHERE address_id = address_id_v;

    IF got.source_address <> 'RENDE(CS), VIALE ORSO MARIO CORBINO 33' THEN
        RAISE EXCEPTION 'source address was not preserved';
    END IF;
    IF got.normalised_address <> '33, Viale Orso Mario Corbino, Rende, Calabria, Italia' THEN
        RAISE EXCEPTION 'normalised address missing from mart.address_normalisation';
    END IF;
    IF got.street_name <> 'Viale Orso Mario Corbino' OR got.house_number <> '33' THEN
        RAISE EXCEPTION 'structured normalised address fields missing';
    END IF;
    IF got.locality <> 'Rende' OR got.admin_unit_l1 <> 'Calabria' OR got.country_code <> 'IT' THEN
        RAISE EXCEPTION 'provider-neutral locality/admin/country fields missing';
    END IF;
    IF got.match_status_code <> 'candidate' THEN
        RAISE EXCEPTION 'normalisation view must expose a candidate without falsely accepting geography';
    END IF;

    IF EXISTS (
        SELECT 1 FROM mart.address_geography
        WHERE address_id = address_id_v AND latitude IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'candidate coordinates leaked into accepted geography view';
    END IF;
END $$;

ROLLBACK;
