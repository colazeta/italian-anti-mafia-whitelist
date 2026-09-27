-- Extend parser interpretation provenance to source bundles without changing
-- established parse_run or capture identities.
--
-- source.parse_run.content_object_id remains the compatibility/primary anchor.
-- The complete immutable input set lives in source.parse_run_input. Existing
-- scalar parse runs are migrated explicitly as input_label='primary'.

CREATE TABLE source.parse_run_input (
    parse_run_id       uuid NOT NULL REFERENCES source.parse_run(parse_run_id),
    input_label        text NOT NULL,
    content_object_id  uuid NOT NULL REFERENCES source.content_object(content_object_id),
    PRIMARY KEY (parse_run_id, input_label),
    CONSTRAINT parse_run_input_label_not_blank CHECK (btrim(input_label) <> '')
);

COMMENT ON TABLE source.parse_run_input IS
'Immutable labelled ContentObjects consumed by one parser interpretation. A scalar parse has primary only; bundle parsers retain every member independently.';

INSERT INTO source.parse_run_input(parse_run_id, input_label, content_object_id)
SELECT parse_run_id, 'primary', content_object_id
FROM source.parse_run;

COMMENT ON COLUMN source.parse_run.content_object_id IS
'Compatibility/primary ContentObject anchor. The complete parser input set is source.parse_run_input and may contain multiple labelled ContentObjects.';

ALTER TABLE source.capture_parse_run
    ADD COLUMN input_label text NOT NULL DEFAULT 'primary';

ALTER TABLE source.capture_parse_run
    ADD CONSTRAINT capture_parse_run_input_label_not_blank
    CHECK (btrim(input_label) <> '');

ALTER TABLE source.capture_parse_run
    ADD CONSTRAINT capture_parse_run_input_fk
    FOREIGN KEY (parse_run_id, input_label)
    REFERENCES source.parse_run_input(parse_run_id, input_label);

COMMENT ON COLUMN source.capture_parse_run.input_label IS
'Parser input label whose immutable ContentObject was supplied by this capture; not a source edition or document identity.';

DROP TRIGGER capture_parse_content_identity_guard ON source.capture_parse_run;

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
      FROM source.parse_run_input
     WHERE parse_run_id = NEW.parse_run_id
       AND input_label = NEW.input_label;

    IF capture_content IS NULL OR parse_content IS NULL THEN
        RAISE EXCEPTION 'capture/parse association requires an existing labelled ContentObject input'
            USING ERRCODE = '23514';
    END IF;

    IF capture_content IS DISTINCT FROM parse_content THEN
        RAISE EXCEPTION 'capture and labelled parse input refer to different ContentObjects'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER capture_parse_content_identity_guard
BEFORE INSERT OR UPDATE ON source.capture_parse_run
FOR EACH ROW EXECUTE FUNCTION source.enforce_capture_parse_content_identity();

CREATE OR REPLACE FUNCTION source.reject_parse_run_input_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'parse_run_input rows are immutable; create a new parse run for another input set'
        USING ERRCODE = '55000';
END;
$$;

CREATE TRIGGER parse_run_input_immutable
BEFORE UPDATE OR DELETE ON source.parse_run_input
FOR EACH ROW EXECUTE FUNCTION source.reject_parse_run_input_mutation();