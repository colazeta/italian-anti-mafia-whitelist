\set ON_ERROR_STOP on

DO $$
DECLARE
    activity uuid;
    run_id uuid;
    n integer;
BEGIN
    INSERT INTO provenance.processing_activity(
        activity_type_code,software_name,software_version,
        configuration_hash,started_at,completed_at
    ) VALUES (
        'anncsu_orchestrate','db-test','1',repeat('a',64),
        CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
    ) RETURNING processing_activity_id INTO activity;

    INSERT INTO geo.anncsu_orchestration_run(
        processing_activity_id,map_version,plan_sha256,
        istat_reference_version,istat_sha256,refresh_provider_inputs,
        total_canonical_addresses,italian_route_addresses,
        assignable_addresses,unassigned_addresses,status_code,
        started_at,completed_at
    ) VALUES (
        activity,'test-map',repeat('b',64),'test-istat',repeat('c',64),false,
        2,2,2,0,'succeeded',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
    ) RETURNING anncsu_orchestration_run_id INTO run_id;

    INSERT INTO geo.anncsu_region_run(
        anncsu_orchestration_run_id,region_name,dataset_code,
        provider_version,provider_endpoint,zip_sha256,csv_sha256,
        cache_status,planned_address_count,processed_address_count,
        candidate_count,not_found_count,skipped_existing_count,status_code
    ) VALUES (
        run_id,'Calabria','INDIR_CALA','2026-08-03',
        'https://example.test/getds.php?INDIR_CALA',repeat('d',64),repeat('e',64),
        'reused',2,1,1,0,1,'succeeded'
    );

    SELECT count(*) INTO n
    FROM geo.anncsu_region_run
    WHERE anncsu_orchestration_run_id=run_id
      AND candidate_count+not_found_count=processed_address_count
      AND processed_address_count+skipped_existing_count=planned_address_count;
    IF n <> 1 THEN RAISE EXCEPTION 'ANNCSU region accounting row did not reconcile'; END IF;

    DELETE FROM geo.anncsu_region_run WHERE anncsu_orchestration_run_id=run_id;
    DELETE FROM geo.anncsu_orchestration_run WHERE anncsu_orchestration_run_id=run_id;
    DELETE FROM provenance.processing_activity WHERE processing_activity_id=activity;
END;
$$;
