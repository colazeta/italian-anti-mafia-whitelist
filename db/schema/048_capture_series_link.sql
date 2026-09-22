-- Archive-first captures may be temporally meaningful without an identified
-- administrative SourceEdition. Preserve their SourceSeries membership directly
-- instead of inventing an edition merely to obtain a relational link.

ALTER TABLE source.source_capture
    ADD COLUMN series_id uuid NULL REFERENCES source.source_series(series_id);

COMMENT ON COLUMN source.source_capture.series_id IS
'Logical SourceSeries observed by this acquisition. Nullable only for legacy captures whose series relationship is available through capture_edition or has not yet been migrated. This does not identify a SourceEdition.';

CREATE INDEX source_capture_series_time_idx
    ON source.source_capture (series_id, captured_at DESC)
    WHERE series_id IS NOT NULL;

-- Extend the append-only provenance guard introduced in 047. Existing capture IDs
-- remain unchanged; new archive-first captures can carry a direct series link.
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
       OR NEW.series_id IS DISTINCT FROM OLD.series_id
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
