\set ON_ERROR_STOP on

DO $$
DECLARE
    resource uuid;
    content_a uuid;
    content_b uuid;
    count_same_time integer;
    count_reappearance integer;
BEGIN
    INSERT INTO source.source_resource(canonical_locator, web_url, resource_type_code)
    VALUES ('https://example.invalid/lane-a-temporal-capture-test', NULL, 'other')
    RETURNING resource_id INTO resource;

    INSERT INTO source.content_object(sha256, mime_type, file_size, storage_uri, storage_status_code)
    VALUES (repeat('a',64), 'application/octet-stream', 1, 'test://lane-a/a', 'ephemeral')
    RETURNING content_object_id INTO content_a;

    INSERT INTO source.content_object(sha256, mime_type, file_size, storage_uri, storage_status_code)
    VALUES (repeat('b',64), 'application/octet-stream', 1, 'test://lane-a/b', 'ephemeral')
    RETURNING content_object_id INTO content_b;

    INSERT INTO source.source_capture(
        capture_id, resource_id, content_object_id, captured_at, http_status,
        origin_type_code, authority_rank_code, declared_reference_date
    ) VALUES
      ('11111111-1111-4111-8111-111111111111', resource, content_a,
       '2026-09-22T12:00:00+00:00', 200, 'official_current', 'primary_official', '2026-09-22'),
      ('22222222-2222-4222-8222-222222222222', resource, content_b,
       '2026-09-22T12:00:00+00:00', 200, 'official_current', 'primary_official', NULL),
      ('33333333-3333-4333-8333-333333333333', resource, content_a,
       '2026-09-22T13:00:00+00:00', 200, 'official_current', 'primary_official', '2026-09-22');

    SELECT count(*) INTO count_same_time
      FROM source.source_capture
     WHERE resource_id=resource
       AND captured_at='2026-09-22T12:00:00+00:00';
    IF count_same_time <> 2 THEN
        RAISE EXCEPTION 'Equal-time byte-distinct captures collided: %', count_same_time;
    END IF;

    SELECT count(*) INTO count_reappearance
      FROM source.source_capture
     WHERE resource_id=resource
       AND content_object_id=content_a;
    IF count_reappearance <> 2 THEN
        RAISE EXCEPTION 'Reappearance of unchanged bytes did not retain a separate capture: %', count_reappearance;
    END IF;

    IF (SELECT declared_reference_date FROM source.source_capture
         WHERE capture_id='22222222-2222-4222-8222-222222222222') IS NOT NULL THEN
        RAISE EXCEPTION 'Unknown declared reference date was not preserved as unknown';
    END IF;

    BEGIN
        UPDATE source.source_capture
           SET declared_reference_date='2026-09-21'
         WHERE capture_id='11111111-1111-4111-8111-111111111111';
        RAISE EXCEPTION 'Source capture provenance mutation unexpectedly succeeded';
    EXCEPTION WHEN SQLSTATE '55000' THEN
        NULL;
    END;
END;
$$;
