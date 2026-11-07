-- An explicit semantic input pin is separate from source-edition approval.
-- Existing projection identities remain intact and keep NULL (legacy unpinned).
ALTER TABLE semantic.projection_run
    ADD COLUMN source_capture_id uuid NULL;

ALTER TABLE semantic.projection_run
    ADD CONSTRAINT projection_capture_parse_input_fk
    FOREIGN KEY (source_capture_id, parse_run_id)
    REFERENCES source.capture_parse_run(capture_id, parse_run_id);

COMMENT ON COLUMN semantic.projection_run.source_capture_id IS
'Exact pre-existing acquisition/interpretation link selected for a pinned projection. NULL means legacy unpinned provenance; it is not retrospectively filled or treated as an explicit pin. Edition attribution remains separate.';

CREATE FUNCTION semantic.reject_projection_capture_selection_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.source_capture_id IS DISTINCT FROM OLD.source_capture_id THEN
        RAISE EXCEPTION 'Projection capture selection is immutable; do not relabel legacy or pinned provenance'
            USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER projection_capture_selection_immutable
BEFORE UPDATE OF source_capture_id ON semantic.projection_run
FOR EACH ROW EXECUTE FUNCTION semantic.reject_projection_capture_selection_mutation();
