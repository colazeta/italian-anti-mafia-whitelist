\set ON_ERROR_STOP on

DO $$
DECLARE
    v2_runs integer;
    parsed_records integer;
    field_values integer;
    field_definitions integer;
    view_rows integer;
    june_rows integer;
    august_rows integer;
    listing_dates integer;
    expiry_dates integer;
    recovered_rows integer;
    false_alias_rows integer;
    smic_multivalue_rows integer;
    canonical_entities integer;
BEGIN
    SELECT count(*) INTO v2_runs
    FROM source.parse_run pr
    JOIN provenance.processing_activity pa USING(processing_activity_id)
    WHERE pa.software_name='white_list_archive.parsers.cosenza_combined_v2'
      AND pr.status_code='succeeded';
    IF v2_runs <> 2 THEN
        RAISE EXCEPTION 'Expected two successful Cosenza v2 ParseRuns, got %', v2_runs;
    END IF;

    SELECT count(*) INTO parsed_records
    FROM source.parsed_record pr
    JOIN source.parse_run run USING(parse_run_id)
    JOIN provenance.processing_activity pa USING(processing_activity_id)
    WHERE pa.software_name='white_list_archive.parsers.cosenza_combined_v2';
    IF parsed_records <> 2661 THEN
        RAISE EXCEPTION 'Expected 2661 Cosenza v2 ParsedRecords, got %', parsed_records;
    END IF;

    SELECT count(*) INTO field_values
    FROM source.source_field_value sfv
    JOIN source.parsed_record pr USING(parsed_record_id)
    JOIN source.parse_run run USING(parse_run_id)
    JOIN provenance.processing_activity pa USING(processing_activity_id)
    WHERE pa.software_name='white_list_archive.parsers.cosenza_combined_v2';
    IF field_values <> 18627 THEN
        RAISE EXCEPTION 'Expected 18627 Cosenza v2 SourceFieldValues, got %', field_values;
    END IF;

    SELECT count(*) INTO field_definitions
    FROM source.source_field_definition fd
    WHERE fd.structural_locator LIKE 'cosenza_combined_v2:%';
    IF field_definitions <> 7 THEN
        RAISE EXCEPTION 'Expected seven Cosenza v2 source field definitions, got %', field_definitions;
    END IF;

    SELECT count(*) INTO view_rows FROM mart.cosenza_source_observations_v2;
    IF view_rows <> 2661 THEN
        RAISE EXCEPTION 'Expected 2661 rows in v2 source-observation mart, got %', view_rows;
    END IF;

    SELECT count(*) INTO june_rows
    FROM mart.cosenza_source_observations_v2
    WHERE edition_code='2026-06-28';
    SELECT count(*) INTO august_rows
    FROM mart.cosenza_source_observations_v2
    WHERE edition_code='2026-08-03';
    IF june_rows <> 1327 OR august_rows <> 1334 THEN
        RAISE EXCEPTION 'Expected v2 edition counts 1327/1334, got %/%', june_rows, august_rows;
    END IF;

    SELECT count(*) INTO listing_dates
    FROM mart.cosenza_source_observations_v2
    WHERE observed_listing_date IS NOT NULL;
    SELECT count(*) INTO expiry_dates
    FROM mart.cosenza_source_observations_v2
    WHERE observed_expiry_date IS NOT NULL;
    IF listing_dates <> 913 OR expiry_dates <> 428 THEN
        RAISE EXCEPTION 'Expected 913 observed listing dates and 428 observed expiry dates, got %/%', listing_dates, expiry_dates;
    END IF;

    SELECT count(*) INTO recovered_rows
    FROM mart.cosenza_source_observations_v2
    WHERE operator_name_raw IN ('GENISE FORTUNATO','NICASTRO GIUSEPPE','ANDREOLI ELIO');
    IF recovered_rows <> 6 THEN
        RAISE EXCEPTION 'Expected the three v1 false-negative companies in both snapshots, got % rows', recovered_rows;
    END IF;

    SELECT count(*) INTO false_alias_rows
    FROM mart.cosenza_source_observations_v2
    WHERE operator_name_raw='ABBREVIATAMENTE SMIC S.R.L.';
    IF false_alias_rows <> 0 THEN
        RAISE EXCEPTION 'SMIC continuation alias was incorrectly emitted as a standalone v2 record';
    END IF;

    SELECT count(*) INTO smic_multivalue_rows
    FROM mart.cosenza_source_observations_v2
    WHERE operator_name_raw LIKE 'SOCIETA'' MINERALI INDUSTRIALI CALABRIA S.R.L.%'
      AND identifier_field_raw LIKE '%10460290157%'
      AND identifier_field_raw LIKE '%01122910803%';
    IF smic_multivalue_rows <> 2 THEN
        RAISE EXCEPTION 'Expected the SMIC principal row to retain both source identifiers in both snapshots, got %', smic_multivalue_rows;
    END IF;

    SELECT count(*) INTO canonical_entities FROM core.legal_entity;
    IF canonical_entities <> 0 THEN
        RAISE EXCEPTION 'Parser v2 must not create canonical LegalEntity rows; got %', canonical_entities;
    END IF;
END;
$$;
