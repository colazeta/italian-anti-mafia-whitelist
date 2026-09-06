-- Operational additions required by the first full row-level parser persistence.
-- The frozen 0.1.0 schema remains the release baseline; these are 0.1.1-dev
-- additions discovered while materialising real Cosenza parser output.

ALTER TABLE source.parse_run
    ADD COLUMN parse_run_code text NULL;

ALTER TABLE source.parse_run
    ADD CONSTRAINT parse_run_code_not_blank
    CHECK (parse_run_code IS NULL OR btrim(parse_run_code) <> '');

CREATE UNIQUE INDEX parse_run_code_unique
    ON source.parse_run(parse_run_code)
    WHERE parse_run_code IS NOT NULL;

COMMENT ON COLUMN source.parse_run.parse_run_code IS
    'Stable internal project key for one content/parser revision/configuration tuple; not a source identifier.';

ALTER TABLE source.parsed_record
    ADD COLUMN raw_record_text text NULL;

ALTER TABLE source.parsed_record
    ADD CONSTRAINT parsed_record_raw_text_not_blank
    CHECK (raw_record_text IS NULL OR btrim(raw_record_text) <> '');

COMMENT ON COLUMN source.parsed_record.raw_record_text IS
    'Raw source record block retained by the parser so later parser versions can re-extract fields without mutating this parse run.';

-- Source-schema field definitions created by a parser must be idempotent for a
-- stable structural locator within one schema version.
CREATE UNIQUE INDEX source_field_definition_locator_unique
    ON source.source_field_definition(schema_version_id, structural_locator)
    WHERE structural_locator IS NOT NULL;

-- One parsed field value per record/field/structural location. Repeated source
-- values remain possible when the parser gives them distinct structural locators.
CREATE UNIQUE INDEX source_field_value_locator_unique
    ON source.source_field_value(
        parsed_record_id,
        field_definition_id,
        (COALESCE(structural_locator, ''))
    );

-- One mention role emitted for a parsed row is enough; rerunning the exact same
-- parse persistence must not create duplicate mention objects.
CREATE UNIQUE INDEX entity_mention_record_role_unique
    ON source.entity_mention(parsed_record_id, mention_role_code);

CREATE OR REPLACE FUNCTION source.reject_parsed_record_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'parsed_record rows are immutable; create a new parse run instead'
        USING ERRCODE = '55000';
END;
$$;

CREATE TRIGGER parsed_record_immutable
BEFORE UPDATE OR DELETE ON source.parsed_record
FOR EACH ROW EXECUTE FUNCTION source.reject_parsed_record_mutation();
