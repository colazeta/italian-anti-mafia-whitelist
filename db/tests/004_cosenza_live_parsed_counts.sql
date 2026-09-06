\set ON_ERROR_STOP on

DO $$
DECLARE
    june_records integer;
    august_records integer;
    field_values integer;
    mentions integer;
    parse_runs integer;
    field_definitions integer;
    canonical_entities integer;
BEGIN
    SELECT count(*) INTO june_records
      FROM mart.cosenza_source_mentions
     WHERE edition_code='2026-06-28';
    IF june_records <> 1325 THEN
        RAISE EXCEPTION 'Expected 1325 parsed Cosenza source mentions for 2026-06-28, got %', june_records;
    END IF;

    SELECT count(*) INTO august_records
      FROM mart.cosenza_source_mentions
     WHERE edition_code='2026-08-03';
    IF august_records <> 1332 THEN
        RAISE EXCEPTION 'Expected 1332 parsed Cosenza source mentions for 2026-08-03, got %', august_records;
    END IF;

    SELECT count(*) INTO parse_runs
      FROM source.parse_run run
      JOIN source.content_object co USING(content_object_id)
     WHERE co.sha256 IN (
        '565a71d89c4d684b68303949974a6c63410b9432eefe9f3773ac540a4318a07d',
        '0d1ebcdaec25ea5a9f9dc859e2c68bea3ac72ceb988fed4eed4f8ba2ce338202'
     )
       AND run.status_code='succeeded';
    IF parse_runs <> 2 THEN
        RAISE EXCEPTION 'Expected two successful real Cosenza parse runs, got %', parse_runs;
    END IF;

    SELECT count(*) INTO field_values
      FROM source.source_field_value sfv
      JOIN source.parsed_record pr USING(parsed_record_id)
      JOIN source.parse_run run USING(parse_run_id)
      JOIN source.content_object co USING(content_object_id)
     WHERE co.sha256 IN (
        '565a71d89c4d684b68303949974a6c63410b9432eefe9f3773ac540a4318a07d',
        '0d1ebcdaec25ea5a9f9dc859e2c68bea3ac72ceb988fed4eed4f8ba2ce338202'
     );
    IF field_values <> 5314 THEN
        RAISE EXCEPTION 'Expected 5314 persisted raw/parsed source field values, got %', field_values;
    END IF;

    SELECT count(*) INTO mentions
      FROM source.entity_mention em
      JOIN source.parsed_record pr USING(parsed_record_id)
      JOIN source.parse_run run USING(parse_run_id)
      JOIN source.content_object co USING(content_object_id)
     WHERE co.sha256 IN (
        '565a71d89c4d684b68303949974a6c63410b9432eefe9f3773ac540a4318a07d',
        '0d1ebcdaec25ea5a9f9dc859e2c68bea3ac72ceb988fed4eed4f8ba2ce338202'
     )
       AND em.mention_role_code='unknown';
    IF mentions <> 2657 THEN
        RAISE EXCEPTION 'Expected 2657 unresolved source entity mentions, got %', mentions;
    END IF;

    SELECT count(*) INTO field_definitions
      FROM source.source_field_definition fd
      JOIN source.source_schema_version sv USING(schema_version_id)
     WHERE sv.structural_fingerprint='fbb124c5a43d26bef93316844b3021096060f7ed9d2cc0f8f6081f6df935dc97'
       AND fd.structural_locator IN (
          'cosenza_combined_v1:operator_name',
          'cosenza_combined_v1:identifier'
       );
    IF field_definitions <> 2 THEN
        RAISE EXCEPTION 'Expected exactly two persisted parser-v1 field definitions, got %', field_definitions;
    END IF;

    -- Row-level source ingestion does not resolve or create canonical entities.
    SELECT count(*) INTO canonical_entities FROM core.legal_entity;
    IF canonical_entities <> 0 THEN
        RAISE EXCEPTION 'Real source parsing unexpectedly created % canonical legal entities', canonical_entities;
    END IF;
END;
$$;
