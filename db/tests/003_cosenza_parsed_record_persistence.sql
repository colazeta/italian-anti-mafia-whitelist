\set ON_ERROR_STOP on

DO $$
DECLARE
    parse_run_count integer;
    parsed_record_count integer;
    field_value_count integer;
    entity_mention_count integer;
    field_definition_count integer;
    mart_count integer;
    raw_count integer;
    unresolved_identifier_count integer;
    canonical_entity_count integer;
BEGIN
    SELECT count(*) INTO parse_run_count
      FROM source.parse_run run
      JOIN source.content_object co USING(content_object_id)
     WHERE co.sha256 IN (
        repeat('a',64),
        repeat('b',64)
     )
       AND run.status_code='succeeded'
       AND run.parse_run_code IS NOT NULL;
    IF parse_run_count <> 2 THEN
        RAISE EXCEPTION 'Expected two synthetic succeeded parse runs after repeated imports, got %', parse_run_count;
    END IF;

    SELECT count(*) INTO parsed_record_count
      FROM source.parsed_record pr
      JOIN source.parse_run run USING(parse_run_id)
      JOIN source.content_object co USING(content_object_id)
     WHERE co.sha256 IN (repeat('a',64), repeat('b',64));
    IF parsed_record_count <> 5 THEN
        RAISE EXCEPTION 'Expected five synthetic parsed records, got %', parsed_record_count;
    END IF;

    SELECT count(*) INTO raw_count
      FROM source.parsed_record pr
      JOIN source.parse_run run USING(parse_run_id)
      JOIN source.content_object co USING(content_object_id)
     WHERE co.sha256 IN (repeat('a',64), repeat('b',64))
       AND pr.raw_record_text IS NOT NULL
       AND btrim(pr.raw_record_text) <> '';
    IF raw_count <> 5 THEN
        RAISE EXCEPTION 'Expected raw source blocks on all five parsed records, got %', raw_count;
    END IF;

    SELECT count(*) INTO field_value_count
      FROM source.source_field_value sfv
      JOIN source.parsed_record pr USING(parsed_record_id)
      JOIN source.parse_run run USING(parse_run_id)
      JOIN source.content_object co USING(content_object_id)
     WHERE co.sha256 IN (repeat('a',64), repeat('b',64));
    IF field_value_count <> 10 THEN
        RAISE EXCEPTION 'Expected ten source field values, got %', field_value_count;
    END IF;

    SELECT count(*) INTO unresolved_identifier_count
      FROM source.source_field_value sfv
      JOIN source.source_field_definition fd USING(field_definition_id)
      JOIN source.parsed_record pr USING(parsed_record_id)
      JOIN source.parse_run run USING(parse_run_id)
      JOIN source.content_object co USING(content_object_id)
     WHERE co.sha256 IN (repeat('a',64), repeat('b',64))
       AND fd.structural_locator='cosenza_combined_v1:identifier'
       AND sfv.parsed_value_json ->> 'scheme_code'='UNRESOLVED_CF_OR_VAT';
    IF unresolved_identifier_count <> 5 THEN
        RAISE EXCEPTION 'Expected five unresolved CF/PIVA source identifiers, got %', unresolved_identifier_count;
    END IF;

    SELECT count(*) INTO entity_mention_count
      FROM source.entity_mention em
      JOIN source.parsed_record pr USING(parsed_record_id)
      JOIN source.parse_run run USING(parse_run_id)
      JOIN source.content_object co USING(content_object_id)
     WHERE co.sha256 IN (repeat('a',64), repeat('b',64))
       AND em.mention_role_code='unknown';
    IF entity_mention_count <> 5 THEN
        RAISE EXCEPTION 'Expected five unresolved entity mentions, got %', entity_mention_count;
    END IF;

    SELECT count(*) INTO field_definition_count
      FROM source.source_field_definition fd
      JOIN source.source_schema_version sv USING(schema_version_id)
      JOIN source.source_schema ss USING(source_schema_id)
      JOIN source.source_series series USING(series_id)
     WHERE series.series_code='cosenza-combined'
       AND sv.structural_fingerprint='test-cosenza-combined-schema-v1'
       AND fd.structural_locator IN (
          'cosenza_combined_v1:operator_name',
          'cosenza_combined_v1:identifier'
       );
    IF field_definition_count <> 2 THEN
        RAISE EXCEPTION 'Expected exactly two parser-v1 source field definitions, got %', field_definition_count;
    END IF;

    SELECT count(*) INTO mart_count
      FROM mart.cosenza_source_mentions
     WHERE edition_code IN ('2099-01-01','2099-02-01');
    IF mart_count <> 5 THEN
        RAISE EXCEPTION 'Expected five readable source-mention mart rows, got %', mart_count;
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM mart.cosenza_source_mentions
         WHERE edition_code='2099-02-01'
           AND operator_name_raw='TEST GAMMA SRL'
           AND identifier_raw='23456789012'
           AND identifier_scheme_parsed='UNRESOLVED_CF_OR_VAT'
    ) THEN
        RAISE EXCEPTION 'Expected TEST GAMMA source mention in readable mart';
    END IF;

    -- Parsing a source mention must not silently create a canonical LegalEntity.
    SELECT count(*) INTO canonical_entity_count FROM core.legal_entity;
    IF canonical_entity_count <> 0 THEN
        RAISE EXCEPTION 'Parsed source persistence unexpectedly created % canonical legal entities', canonical_entity_count;
    END IF;
END;
$$;

-- Parsed records are immutable: corrections require a new parse run.
DO $$
DECLARE
    target_id uuid;
BEGIN
    SELECT pr.parsed_record_id INTO target_id
      FROM source.parsed_record pr
      JOIN source.parse_run run USING(parse_run_id)
      JOIN source.content_object co USING(content_object_id)
     WHERE co.sha256=repeat('a',64)
     ORDER BY pr.record_locator
     LIMIT 1;

    BEGIN
        UPDATE source.parsed_record
           SET record_hash=repeat('f',64)
         WHERE parsed_record_id=target_id;
        RAISE EXCEPTION 'Expected parsed-record immutability trigger to reject update';
    EXCEPTION WHEN SQLSTATE '55000' THEN
        NULL;
    END;
END;
$$;
