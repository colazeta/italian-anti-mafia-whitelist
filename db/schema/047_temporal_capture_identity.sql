ALTER TABLE source.source_capture
    ADD COLUMN declared_reference_date date NULL;

COMMENT ON COLUMN source.source_capture.declared_reference_date IS
'Declared source reference date associated with this acquisition when known. It is capture provenance, not SourceEdition identity, publication time, effective time or legal time.';

COMMENT ON COLUMN source.source_edition.edition_code IS
'Optional stable label for an identified administrative source edition. A locator or reference date must not be silently promoted to edition identity; legacy date-coded editions remain valid for compatibility.';

CREATE OR REPLACE FUNCTION source.guard_source_capture_provenance()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'source_capture rows are append-only and cannot be deleted'
            USING ERRCODE = '55000';
    END IF;
    IF NEW.capture_id IS DISTINCT FROM OLD.capture_id
       OR NEW.resource_id IS DISTINCT FROM OLD.resource_id
       OR NEW.content_object_id IS DISTINCT FROM OLD.content_object_id
       OR NEW.captured_at IS DISTINCT FROM OLD.captured_at
       OR NEW.http_status IS DISTINCT FROM OLD.http_status
       OR NEW.origin_type_code IS DISTINCT FROM OLD.origin_type_code
       OR NEW.authority_rank_code IS DISTINCT FROM OLD.authority_rank_code
       OR NEW.resolved_url IS DISTINCT FROM OLD.resolved_url
       OR NEW.etag IS DISTINCT FROM OLD.etag
       OR NEW.last_modified IS DISTINCT FROM OLD.last_modified
       OR NEW.declared_reference_date IS DISTINCT FROM OLD.declared_reference_date THEN
        RAISE EXCEPTION 'source_capture provenance is immutable; create a new capture/check instead'
            USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER source_capture_provenance_immutable
BEFORE UPDATE OR DELETE ON source.source_capture
FOR EACH ROW EXECUTE FUNCTION source.guard_source_capture_provenance();
