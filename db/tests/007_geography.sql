BEGIN;

DO $$
DECLARE
    activity_id uuid;
    address_id_v uuid;
    unit_id uuid;
    got record;
BEGIN
    INSERT INTO provenance.processing_activity(
        activity_type_code, software_name, software_version,
        configuration_hash, started_at, completed_at
    ) VALUES (
        'geocode', 'geography-test', '1', repeat('a', 64),
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
    ) RETURNING processing_activity_id INTO activity_id;

    INSERT INTO core.address(full_address, country_code, processing_activity_id)
    VALUES ('Via Roma 1, Lamezia Terme, Italia', 'IT', activity_id)
    RETURNING address_id INTO address_id_v;

    BEGIN
        INSERT INTO geo.address_geocode_result(
            address_id, provider_name, candidate_rank, match_status_code,
            precision_code, processing_activity_id
        ) VALUES (
            address_id_v, 'test-provider', 1, 'accepted', 'rooftop', activity_id
        );
        RAISE EXCEPTION 'accepted geocode without coordinates should have failed';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;

    INSERT INTO geo.address_geocode_result(
        address_id, provider_name, provider_version, candidate_rank,
        match_status_code, precision_code, latitude, longitude,
        confidence, matched_address, processing_activity_id
    ) VALUES (
        address_id_v, 'test-provider', '1', 1,
        'accepted', 'rooftop', 38.9659, 16.3093,
        0.99, 'Via Roma 1, Lamezia Terme', activity_id
    );

    INSERT INTO geo.geographic_unit(
        scheme_code, scheme_version, unit_level_code, unit_code,
        unit_name, effective_period
    ) VALUES
        ('ISTAT_ADMIN','2026-02-21','municipality','079160','Lamezia Terme',daterange('2026-01-01',NULL,'[)')),
        ('ISTAT_ADMIN','2026-02-21','province','079','Catanzaro',daterange('2026-01-01',NULL,'[)')),
        ('ISTAT_ADMIN','2026-02-21','region','18','Calabria',daterange('2026-01-01',NULL,'[)')),
        ('NUTS','2024','nuts1','ITF','Sud',daterange('2024-01-01',NULL,'[)')),
        ('NUTS','2024','nuts2','ITF6','Calabria',daterange('2024-01-01',NULL,'[)')),
        ('NUTS','2024','nuts3','ITF63','Catanzaro',daterange('2024-01-01',NULL,'[)'));

    FOR unit_id IN
        SELECT geographic_unit_id FROM geo.geographic_unit
        WHERE unit_code IN ('079160','079','18','ITF','ITF6','ITF63')
    LOOP
        INSERT INTO geo.address_geographic_unit(
            address_id, geographic_unit_id, assignment_method_code,
            confidence, processing_activity_id
        ) VALUES (address_id_v, unit_id, 'official_crosswalk', 1.0, activity_id);
    END LOOP;

    SELECT * INTO got FROM mart.address_geography WHERE address_id = address_id_v;
    IF got.latitude IS DISTINCT FROM 38.9659 OR got.longitude IS DISTINCT FROM 16.3093 THEN
        RAISE EXCEPTION 'accepted geocode missing from mart.address_geography';
    END IF;
    IF got.municipality_code <> '079160' OR got.region_name <> 'Calabria' THEN
        RAISE EXCEPTION 'ISTAT administrative geography missing from mart.address_geography';
    END IF;
    IF got.nuts1_code <> 'ITF' OR got.nuts2_code <> 'ITF6' OR got.nuts3_code <> 'ITF63' THEN
        RAISE EXCEPTION 'NUTS geography missing from mart.address_geography';
    END IF;
END $$;

ROLLBACK;
