-- Operational metadata required by the first real content-level ingestion.
-- These additions preserve the 0.1.0 conceptual model while making repeated
-- source capture/import idempotent and distinguishing ephemeral from durable
-- byte storage.

CREATE TABLE IF NOT EXISTS registry.content_storage_status (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.content_storage_status IS 'Operational persistence state of an immutable content object.';

INSERT INTO registry.content_storage_status(code,label,description) VALUES
('ephemeral','Ephemeral','Bytes were acquired and hash-identified but are currently held only in a non-durable location.'),
('durable','Durable','Bytes are stored in the designated durable content-addressed object store.'),
('unavailable','Unavailable','The content identity is known but no retrievable byte location is currently available.')
ON CONFLICT (code) DO NOTHING;

ALTER TABLE core.public_authority
    ADD COLUMN authority_code text NULL;

ALTER TABLE core.public_authority
    ADD CONSTRAINT public_authority_code_not_blank
    CHECK (authority_code IS NULL OR btrim(authority_code) <> '');

CREATE UNIQUE INDEX public_authority_code_unique
    ON core.public_authority(authority_code)
    WHERE authority_code IS NOT NULL;

-- A register can be known to exist even when its exact administrative start
-- date has not yet been established from evidence. NULL means unknown, not
-- unbounded. Both the nullability and the validation CHECK must therefore be
-- relaxed: dropping only NOT NULL would leave the 0.1.0 CHECK rejecting NULL.
ALTER TABLE whitelist.white_list_register
    ALTER COLUMN effective_period DROP NOT NULL;

ALTER TABLE whitelist.white_list_register
    DROP CONSTRAINT white_list_register_effective_valid;

ALTER TABLE whitelist.white_list_register
    ADD CONSTRAINT white_list_register_effective_valid
    CHECK (
        effective_period IS NULL
        OR (NOT isempty(effective_period) AND lower(effective_period) IS NOT NULL)
    );

ALTER TABLE source.source_series
    ADD COLUMN series_code text NULL;

ALTER TABLE source.source_series
    ADD CONSTRAINT source_series_code_not_blank
    CHECK (series_code IS NULL OR btrim(series_code) <> '');

CREATE UNIQUE INDEX source_series_code_unique
    ON source.source_series(series_code)
    WHERE series_code IS NOT NULL;

ALTER TABLE source.source_edition
    ADD COLUMN edition_code text NULL;

ALTER TABLE source.source_edition
    ADD CONSTRAINT source_edition_code_not_blank
    CHECK (edition_code IS NULL OR btrim(edition_code) <> '');

CREATE UNIQUE INDEX source_edition_code_unique_per_series
    ON source.source_edition(series_id, edition_code)
    WHERE edition_code IS NOT NULL;

ALTER TABLE source.source_schema
    ADD CONSTRAINT source_schema_name_unique_per_series
    UNIQUE (series_id, schema_name);

ALTER TABLE source.content_object
    ADD COLUMN storage_status_code text NOT NULL DEFAULT 'ephemeral'
        REFERENCES registry.content_storage_status(code);

ALTER TABLE source.source_capture
    ADD COLUMN resolved_url text NULL,
    ADD COLUMN etag text NULL,
    ADD COLUMN last_modified timestamptz NULL;

ALTER TABLE source.source_capture
    ADD CONSTRAINT source_capture_resolved_url_not_blank
    CHECK (resolved_url IS NULL OR btrim(resolved_url) <> '');

COMMENT ON COLUMN core.public_authority.authority_code IS 'Stable internal project code; not an administrative identifier.';
COMMENT ON COLUMN source.source_series.series_code IS 'Stable internal project code for a recurring logical source series.';
COMMENT ON COLUMN source.source_edition.edition_code IS 'Optional stable source/project edition code within a source series; repeated captures can map to the same edition.';
COMMENT ON COLUMN source.content_object.storage_status_code IS 'Operational durability status; content byte identity remains the SHA-256 regardless of storage transition.';
COMMENT ON COLUMN source.source_capture.resolved_url IS 'Final URL after HTTP redirects, when applicable.';
COMMENT ON COLUMN source.source_capture.etag IS 'HTTP ETag observed at capture time, if supplied.';
COMMENT ON COLUMN source.source_capture.last_modified IS 'HTTP Last-Modified value observed at capture time, parsed as timestamptz when supplied.';

CREATE OR REPLACE FUNCTION source.guard_content_storage_downgrade()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND OLD.storage_status_code = 'durable'
       AND NEW.storage_status_code <> 'durable' THEN
        RAISE EXCEPTION 'durable content storage status cannot be downgraded'
            USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER content_storage_no_downgrade
BEFORE UPDATE OF storage_status_code ON source.content_object
FOR EACH ROW EXECUTE FUNCTION source.guard_content_storage_downgrade();
