BEGIN;

DO $$
DECLARE
    activity_id uuid;
    address_id_v uuid;
    got record;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM registry.geocode_precision WHERE code='civic_access'
    ) THEN
        RAISE EXCEPTION 'civic_access precision lookup is missing';
    END IF;

    INSERT INTO provenance.processing_activity(
        activity_type_code, software_name, software_version,
        configuration_hash, started_at, completed_at
    ) VALUES (
        'geocode', 'anncsu-enrichment-test', '1', repeat('c', 64),
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
    ) RETURNING processing_activity_id INTO activity_id;

    INSERT INTO core.address(full_address, country_code, processing_activity_id)
    VALUES ('ACRI Via Aldo Moro 496', 'IT', activity_id)
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
        normalised_locality,
        normalised_admin_unit_l1,
        normalised_country_name,
        normalised_country_code,
        provider_attribution,
        provider_licence,
        provider_payload,
        processing_activity_id
    ) VALUES (
        address_id_v,
        'anncsu',
        'https://anncsu.example.test/INDIR_CALA',
        '2026-08-03',
        '2026-08-03T00:00:00Z',
        'access:12345',
        1,
        'candidate',
        'civic_access',
        39.4991531,
        16.3827486,
        'ACRI Via Aldo Moro 496',
        'VIA ALDO MORO 496, Acri, Italia',
        'VIA ALDO MORO',
        '496',
        'Acri',
        'Calabria',
        'Italia',
        'IT',
        'ANNCSU — Istat e Agenzia delle Entrate',
        'CC-BY 4.0',
        '{"coordinate_derivation":"provider_civic_access","anncsu_metodo":"4"}'::jsonb,
        activity_id
    );

    SELECT * INTO got
    FROM mart.address_normalisation
    WHERE address_id=address_id_v;

    IF got.match_status_code <> 'candidate' OR got.coordinate_precision <> 'civic_access' THEN
        RAISE EXCEPTION 'ANNCSU candidate/precision not exposed correctly';
    END IF;
    IF got.latitude IS NULL OR got.longitude IS NULL THEN
        RAISE EXCEPTION 'ANNCSU candidate coordinates missing from normalisation view';
    END IF;
    IF got.house_number <> '496' OR got.locality <> 'Acri' THEN
        RAISE EXCEPTION 'ANNCSU structured normalisation fields missing';
    END IF;

    IF EXISTS (
        SELECT 1 FROM mart.address_geography
        WHERE address_id=address_id_v AND latitude IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'ANNCSU candidate leaked into accepted geography';
    END IF;
END $$;

ROLLBACK;
