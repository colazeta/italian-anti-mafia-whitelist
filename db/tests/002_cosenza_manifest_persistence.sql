\set ON_ERROR_STOP on

DO $$
DECLARE
    authority_count integer;
    register_count integer;
    series_count integer;
    edition_count integer;
    resource_count integer;
    content_count integer;
    capture_count integer;
    link_count integer;
    schema_count integer;
    schema_version_count integer;
    population_count integer;
    ephemeral_count integer;
    metadata_count integer;
BEGIN
    SELECT count(*) INTO authority_count
      FROM core.public_authority
     WHERE authority_code='cosenza';
    IF authority_count <> 1 THEN
        RAISE EXCEPTION 'Expected one Cosenza authority, got %', authority_count;
    END IF;

    SELECT count(*) INTO register_count
      FROM whitelist.white_list_register
     WHERE register_code='WL-REGISTER-COSENZA-ORDINARY';
    IF register_count <> 1 THEN
        RAISE EXCEPTION 'Expected one Cosenza ordinary register, got %', register_count;
    END IF;

    SELECT count(*) INTO series_count
      FROM source.source_series
     WHERE series_code='cosenza-combined';
    IF series_count <> 1 THEN
        RAISE EXCEPTION 'Expected one Cosenza combined source series, got %', series_count;
    END IF;

    SELECT count(*) INTO edition_count
      FROM source.source_edition e
      JOIN source.source_series s USING(series_id)
     WHERE s.series_code='cosenza-combined'
       AND e.edition_code IN ('2026-06-28','2026-08-03');
    IF edition_count <> 2 THEN
        RAISE EXCEPTION 'Expected two Cosenza editions, got %', edition_count;
    END IF;

    SELECT count(*) INTO resource_count
      FROM source.source_resource
     WHERE canonical_locator LIKE 'https://prefettura.interno.gov.it/sites/default/files/34/2026-%/00elenco-imprese-iscritte-e-richiedenti%';
    IF resource_count <> 2 THEN
        RAISE EXCEPTION 'Expected two captured source resources, got %', resource_count;
    END IF;

    SELECT count(*) INTO content_count
      FROM source.content_object
     WHERE sha256 IN (
        '565a71d89c4d684b68303949974a6c63410b9432eefe9f3773ac540a4318a07d',
        '0d1ebcdaec25ea5a9f9dc859e2c68bea3ac72ceb988fed4eed4f8ba2ce338202'
     );
    IF content_count <> 2 THEN
        RAISE EXCEPTION 'Expected two content objects, got %', content_count;
    END IF;

    SELECT count(*) INTO ephemeral_count
      FROM source.content_object
     WHERE sha256 IN (
        '565a71d89c4d684b68303949974a6c63410b9432eefe9f3773ac540a4318a07d',
        '0d1ebcdaec25ea5a9f9dc859e2c68bea3ac72ceb988fed4eed4f8ba2ce338202'
     )
       AND storage_status_code='ephemeral'
       AND storage_uri LIKE 'github-actions://%';
    IF ephemeral_count <> 2 THEN
        RAISE EXCEPTION 'Expected two explicitly ephemeral content objects, got %', ephemeral_count;
    END IF;

    SELECT count(*) INTO capture_count
      FROM source.source_capture c
      JOIN source.content_object co USING(content_object_id)
     WHERE co.sha256 IN (
        '565a71d89c4d684b68303949974a6c63410b9432eefe9f3773ac540a4318a07d',
        '0d1ebcdaec25ea5a9f9dc859e2c68bea3ac72ceb988fed4eed4f8ba2ce338202'
     );
    IF capture_count <> 2 THEN
        RAISE EXCEPTION 'Expected two source captures after repeated idempotent imports, got %', capture_count;
    END IF;

    SELECT count(*) INTO metadata_count
      FROM source.source_capture c
      JOIN source.content_object co USING(content_object_id)
     WHERE co.sha256 IN (
        '565a71d89c4d684b68303949974a6c63410b9432eefe9f3773ac540a4318a07d',
        '0d1ebcdaec25ea5a9f9dc859e2c68bea3ac72ceb988fed4eed4f8ba2ce338202'
     )
       AND c.http_status=200
       AND c.resolved_url IS NOT NULL
       AND c.etag IS NOT NULL
       AND c.last_modified IS NOT NULL
       AND c.origin_type_code='official_current'
       AND c.authority_rank_code='primary_official';
    IF metadata_count <> 2 THEN
        RAISE EXCEPTION 'Expected complete HTTP/evidence metadata on both captures, got %', metadata_count;
    END IF;

    SELECT count(*) INTO link_count
      FROM source.capture_edition ce
      JOIN source.source_capture c USING(capture_id)
      JOIN source.content_object co USING(content_object_id)
     WHERE co.sha256 IN (
        '565a71d89c4d684b68303949974a6c63410b9432eefe9f3773ac540a4318a07d',
        '0d1ebcdaec25ea5a9f9dc859e2c68bea3ac72ceb988fed4eed4f8ba2ce338202'
     )
       AND ce.relation_type_code='is_representation_of'
       AND ce.attribution_status_code='explicit';
    IF link_count <> 2 THEN
        RAISE EXCEPTION 'Expected two explicit capture-edition links, got %', link_count;
    END IF;

    SELECT count(*) INTO schema_count
      FROM source.source_schema ss
      JOIN source.source_series s USING(series_id)
     WHERE s.series_code='cosenza-combined'
       AND ss.schema_name='Cosenza combined White List PDF layout';
    IF schema_count <> 1 THEN
        RAISE EXCEPTION 'Expected one Cosenza source schema, got %', schema_count;
    END IF;

    SELECT count(*) INTO schema_version_count
      FROM source.source_schema_version sv
      JOIN source.source_schema ss USING(source_schema_id)
      JOIN source.source_series s USING(series_id)
     WHERE s.series_code='cosenza-combined'
       AND sv.structural_fingerprint='fbb124c5a43d26bef93316844b3021096060f7ed9d2cc0f8f6081f6df935dc97';
    IF schema_version_count <> 1 THEN
        RAISE EXCEPTION 'Expected one shared source schema version, got %', schema_version_count;
    END IF;

    SELECT count(*) INTO population_count
      FROM source.edition_population_scope eps
      JOIN source.source_edition e USING(edition_id)
      JOIN source.source_series s USING(series_id)
     WHERE s.series_code='cosenza-combined'
       AND e.edition_code IN ('2026-06-28','2026-08-03')
       AND eps.population_type_code IN ('listed','applicant');
    IF population_count <> 4 THEN
        RAISE EXCEPTION 'Expected listed+applicant scopes on both editions, got %', population_count;
    END IF;
END;
$$;

-- The exact start of the Cosenza administrative register has not yet been
-- established from evidence, so the importer must not invent it.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM whitelist.white_list_register
        WHERE register_code='WL-REGISTER-COSENZA-ORDINARY'
          AND effective_period IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'Cosenza register effective period was invented instead of remaining unknown';
    END IF;
END;
$$;
