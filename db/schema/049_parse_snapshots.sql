-- Generic private persistence for full parser observation snapshots.
--
-- A parse run is an interpretation of immutable bytes. It is deliberately not a
-- SourceEdition and does not become one merely because a parser/configuration was
-- rerun. One parse run may be associated with multiple captures of the same
-- ContentObject, while a later parser/configuration revision creates another
-- parse run over those unchanged bytes.

CREATE TABLE source.parse_snapshot (
    parse_run_id       uuid PRIMARY KEY REFERENCES source.parse_run(parse_run_id),
    snapshot_sha256    text NOT NULL,
    record_count       integer NOT NULL,
    records_json       jsonb NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT parse_snapshot_sha256_format
        CHECK (snapshot_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT parse_snapshot_record_count_nonnegative
        CHECK (record_count >= 0),
    CONSTRAINT parse_snapshot_records_array
        CHECK (jsonb_typeof(records_json) = 'array')
);

COMMENT ON TABLE source.parse_snapshot IS
'Immutable private snapshot of the complete parser records for one parse_run. It supplements field-level source persistence and is not a public release or administrative publication.';

COMMENT ON COLUMN source.parse_snapshot.snapshot_sha256 IS
'SHA-256 of canonical UTF-8 JSON for records_json; identifies the exact interpretation output, not the source bytes.';

CREATE TABLE source.capture_parse_run (
    capture_id    uuid NOT NULL REFERENCES source.source_capture(capture_id),
    parse_run_id  uuid NOT NULL REFERENCES source.parse_run(parse_run_id),
    linked_at     timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (capture_id, parse_run_id)
);

COMMENT ON TABLE source.capture_parse_run IS
'Append-only association between an acquisition/check and an interpretation of the exact ContentObject acquired. Repeated unchanged captures may point to the same parse run.';

CREATE INDEX capture_parse_run_parse_idx
    ON source.capture_parse_run(parse_run_id, capture_id);

CREATE OR REPLACE FUNCTION source.enforce_capture_parse_content_identity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    capture_content uuid;
    parse_content uuid;
BEGIN
    SELECT content_object_id INTO capture_content
      FROM source.source_capture
     WHERE capture_id = NEW.capture_id;

    SELECT content_object_id INTO parse_content
      FROM source.parse_run
     WHERE parse_run_id = NEW.parse_run_id;

    IF capture_content IS NULL OR parse_content IS NULL THEN
        RAISE EXCEPTION 'capture/parse association requires both sides to identify a ContentObject'
            USING ERRCODE = '23514';
    END IF;

    IF capture_content IS DISTINCT FROM parse_content THEN
        RAISE EXCEPTION 'capture and parse run refer to different ContentObjects'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER capture_parse_content_identity_guard
BEFORE INSERT OR UPDATE ON source.capture_parse_run
FOR EACH ROW EXECUTE FUNCTION source.enforce_capture_parse_content_identity();

CREATE OR REPLACE FUNCTION source.reject_parse_snapshot_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'parse_snapshot rows are immutable; create a new parse run for another interpretation'
        USING ERRCODE = '55000';
END;
$$;

CREATE TRIGGER parse_snapshot_immutable
BEFORE UPDATE OR DELETE ON source.parse_snapshot
FOR EACH ROW EXECUTE FUNCTION source.reject_parse_snapshot_mutation();

CREATE OR REPLACE FUNCTION source.reject_capture_parse_run_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'capture_parse_run rows are append-only; add another interpretation link instead'
        USING ERRCODE = '55000';
END;
$$;

CREATE TRIGGER capture_parse_run_immutable
BEFORE UPDATE OR DELETE ON source.capture_parse_run
FOR EACH ROW EXECUTE FUNCTION source.reject_capture_parse_run_mutation();
