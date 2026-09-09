\set ON_ERROR_STOP on

DO $$
DECLARE
    activity uuid;
    test_address_id uuid;
    ann_id uuid;
    run_id uuid;
    n integer;
BEGIN
    INSERT INTO provenance.processing_activity(
        activity_type_code,software_name,software_version,
        configuration_hash,started_at,completed_at
    ) VALUES (
        'geocode','fallback-db-test','1',repeat('a',64),
        CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
    ) RETURNING processing_activity_id INTO activity;

    INSERT INTO core.address(full_address,processing_activity_id)
    VALUES ('COSENZA Via Fallback Test 1',activity)
    RETURNING core.address.address_id INTO test_address_id;

    INSERT INTO geo.address_country_assessment(
        address_id,derived_country_code,classification_status_code,route_code,
        derivation_reason,reference_scheme,reference_version,processing_activity_id
    ) VALUES (
        test_address_id,'IT','derived_italian','italian_anncsu','db-test',
        'TEST','1',activity
    );

    INSERT INTO geo.address_geocode_result(
        address_id,provider_name,provider_endpoint,provider_version,
        candidate_rank,match_status_code,query_text,processing_activity_id
    ) VALUES (
        test_address_id,'anncsu','https://anncsu.example.test','ann-v1',1,
        'not_found','COSENZA Via Fallback Test 1',activity
    ) RETURNING address_geocode_result_id INTO ann_id;

    INSERT INTO geo.fallback_geocode_run(
        processing_activity_id,provider_name,provider_endpoint,provider_version,
        configuration_hash,eligible_address_count,selected_address_count,
        status_code,started_at,completed_at
    ) VALUES (
        activity,'nominatim','https://fallback.example.test','fallback-v1',repeat('b',64),
        1,1,'succeeded',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
    ) RETURNING fallback_geocode_run_id INTO run_id;

    INSERT INTO geo.fallback_geocode_run_item(
        fallback_geocode_run_id,address_id,eligibility_reason_code,source_route_code,
        country_filter_code,upstream_geocode_result_id,upstream_provider_version,
        cache_disposition_code,result_status_code,candidate_count,query_text
    ) VALUES (
        run_id,test_address_id,'anncsu_not_found','italian_anncsu','IT',ann_id,'ann-v1',
        'queried','candidate',1,'COSENZA Via Fallback Test 1'
    );

    INSERT INTO geo.address_geocode_result(
        address_id,provider_name,provider_endpoint,provider_version,
        candidate_rank,match_status_code,precision_code,latitude,longitude,
        query_text,matched_address,normalised_country_code,
        routing_stage_code,routing_reason_code,upstream_geocode_result_id,
        fallback_geocode_run_id,processing_activity_id
    ) VALUES (
        test_address_id,'nominatim','https://fallback.example.test','fallback-v1',1,
        'candidate','address',39.30,16.25,'COSENZA Via Fallback Test 1',
        'Via Fallback Test 1, Cosenza','IT','fallback','anncsu_not_found',ann_id,
        run_id,activity
    );

    SELECT count(*) INTO n
    FROM mart.address_normalisation m
    WHERE m.address_id=test_address_id
      AND m.provider_name='nominatim'
      AND m.routing_stage_code='fallback'
      AND m.routing_reason_code='anncsu_not_found'
      AND m.upstream_geocode_result_id=ann_id;
    IF n <> 1 THEN
        RAISE EXCEPTION 'Fallback provenance not exposed through mart.address_normalisation';
    END IF;

    SELECT count(*) INTO n
    FROM geo.fallback_geocode_run_item i
    WHERE i.fallback_geocode_run_id=run_id
      AND i.candidate_count=1
      AND i.country_filter_code='IT';
    IF n <> 1 THEN
        RAISE EXCEPTION 'Fallback run item did not persist eligibility/provider provenance';
    END IF;

    DELETE FROM geo.address_geocode_result g WHERE g.address_id=test_address_id;
    DELETE FROM geo.fallback_geocode_run_item i WHERE i.fallback_geocode_run_id=run_id;
    DELETE FROM geo.fallback_geocode_run r WHERE r.fallback_geocode_run_id=run_id;
    DELETE FROM geo.address_country_assessment ca WHERE ca.address_id=test_address_id;
    DELETE FROM core.address a WHERE a.address_id=test_address_id;
    DELETE FROM provenance.processing_activity p WHERE p.processing_activity_id=activity;
END;
$$;
