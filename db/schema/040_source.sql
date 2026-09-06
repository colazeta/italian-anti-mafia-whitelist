CREATE TABLE source.source_series (
    series_id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    publisher_authority_id  uuid NULL REFERENCES core.public_authority(public_authority_id),
    register_id             uuid NULL REFERENCES whitelist.white_list_register(register_id),
    series_name             text NOT NULL,
    series_type_code        text NOT NULL REFERENCES registry.source_series_type(code),
    created_at              timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT source_series_name_not_blank CHECK (btrim(series_name) <> '')
);

CREATE INDEX source_series_authority_idx ON source.source_series (publisher_authority_id);
CREATE INDEX source_series_register_idx ON source.source_series (register_id);

CREATE TABLE source.source_edition (
    edition_id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    series_id                     uuid NOT NULL REFERENCES source.source_series(series_id),
    reference_period              daterange NULL,
    publication_date              date NULL,
    edition_identity_status_code        text NOT NULL REFERENCES registry.edition_identity_status(code),
    population_scope_completeness_code text NOT NULL REFERENCES registry.scope_completeness(code),
    sector_scope_completeness_code     text NOT NULL REFERENCES registry.scope_completeness(code),
    created_at                    timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT source_edition_reference_nonempty CHECK (reference_period IS NULL OR NOT isempty(reference_period))
);

CREATE INDEX source_edition_series_idx ON source.source_edition (series_id);
CREATE INDEX source_edition_reference_gist ON source.source_edition USING gist (reference_period);

CREATE TABLE source.edition_population_scope (
    edition_id            uuid NOT NULL REFERENCES source.source_edition(edition_id) ON DELETE CASCADE,
    population_type_code  text NOT NULL REFERENCES registry.population_type(code),
    PRIMARY KEY (edition_id, population_type_code)
);

CREATE TABLE source.edition_sector_scope (
    edition_id            uuid NOT NULL REFERENCES source.source_edition(edition_id) ON DELETE CASCADE,
    scheme_membership_id  uuid NOT NULL REFERENCES whitelist.sector_scheme_membership(scheme_membership_id),
    PRIMARY KEY (edition_id, scheme_membership_id)
);

CREATE OR REPLACE FUNCTION source.enforce_edition_sector_regime()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    edition_regime uuid;
    membership_regime uuid;
BEGIN
    SELECT reg.regime_id
      INTO edition_regime
      FROM source.source_edition e
      JOIN source.source_series s ON s.series_id = e.series_id
      JOIN whitelist.white_list_register reg ON reg.register_id = s.register_id
     WHERE e.edition_id = NEW.edition_id;

    IF edition_regime IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT sv.regime_id
      INTO membership_regime
      FROM whitelist.sector_scheme_membership sm
      JOIN whitelist.sector_scheme_version sv ON sv.scheme_version_id = sm.scheme_version_id
     WHERE sm.scheme_membership_id = NEW.scheme_membership_id;

    IF edition_regime IS DISTINCT FROM membership_regime THEN
        RAISE EXCEPTION 'edition sector membership regime does not match source-series register regime'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER edition_sector_regime_guard
BEFORE INSERT OR UPDATE ON source.edition_sector_scope
FOR EACH ROW EXECUTE FUNCTION source.enforce_edition_sector_regime();

CREATE TABLE source.source_resource (
    resource_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_locator   text NOT NULL UNIQUE,
    web_url             text NULL,
    resource_type_code  text NOT NULL REFERENCES registry.resource_type(code),
    created_at          timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT source_resource_locator_not_blank CHECK (btrim(canonical_locator) <> ''),
    CONSTRAINT source_resource_web_url_not_blank CHECK (web_url IS NULL OR btrim(web_url) <> '')
);

CREATE TABLE source.content_object (
    content_object_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sha256            text NOT NULL UNIQUE,
    mime_type         text NOT NULL,
    file_size         bigint NOT NULL,
    storage_uri       text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT content_object_sha256_format CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT content_object_file_size_nonnegative CHECK (file_size >= 0),
    CONSTRAINT content_object_storage_uri_not_blank CHECK (btrim(storage_uri) <> '')
);

CREATE TABLE source.source_capture (
    capture_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id         uuid NOT NULL REFERENCES source.source_resource(resource_id),
    content_object_id   uuid NULL REFERENCES source.content_object(content_object_id),
    captured_at         timestamptz NOT NULL,
    http_status         integer NULL,
    origin_type_code    text NOT NULL REFERENCES registry.source_origin_type(code),
    authority_rank_code text NOT NULL REFERENCES registry.authority_rank(code),
    CONSTRAINT source_capture_http_status_range CHECK (http_status IS NULL OR http_status BETWEEN 100 AND 599)
);

CREATE INDEX source_capture_resource_time_idx ON source.source_capture (resource_id, captured_at DESC);
CREATE INDEX source_capture_content_idx ON source.source_capture (content_object_id);

CREATE TABLE source.capture_edition (
    capture_id              uuid NOT NULL REFERENCES source.source_capture(capture_id) ON DELETE CASCADE,
    edition_id              uuid NOT NULL REFERENCES source.source_edition(edition_id) ON DELETE CASCADE,
    relation_type_code      text NOT NULL REFERENCES registry.capture_edition_relation_type(code),
    attribution_status_code text NOT NULL REFERENCES registry.attribution_status(code),
    PRIMARY KEY (capture_id, edition_id)
);

CREATE TABLE source.source_schema (
    source_schema_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    series_id         uuid NULL REFERENCES source.source_series(series_id),
    schema_name       text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT source_schema_name_not_blank CHECK (btrim(schema_name) <> '')
);

CREATE TABLE source.source_schema_version (
    schema_version_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_schema_id        uuid NOT NULL REFERENCES source.source_schema(source_schema_id),
    structural_fingerprint  text NOT NULL,
    first_observed_at       timestamptz NOT NULL,
    last_observed_at        timestamptz NULL,
    CONSTRAINT source_schema_version_fingerprint_not_blank CHECK (btrim(structural_fingerprint) <> ''),
    CONSTRAINT source_schema_version_time_order CHECK (last_observed_at IS NULL OR first_observed_at <= last_observed_at),
    CONSTRAINT source_schema_fingerprint_unique UNIQUE (source_schema_id, structural_fingerprint)
);

CREATE TABLE source.source_field_definition (
    field_definition_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    schema_version_id         uuid NOT NULL REFERENCES source.source_schema_version(schema_version_id),
    source_label              text NOT NULL,
    normalised_source_label   text NOT NULL,
    ordinal_position          integer NULL,
    observed_datatype         text NULL,
    observed_cardinality      text NULL,
    structural_locator        text NULL,
    CONSTRAINT source_field_label_not_blank CHECK (btrim(source_label) <> ''),
    CONSTRAINT source_field_normalised_label_not_blank CHECK (btrim(normalised_source_label) <> ''),
    CONSTRAINT source_field_ordinal_positive CHECK (ordinal_position IS NULL OR ordinal_position > 0),
    CONSTRAINT source_field_definition_id_schema_unique UNIQUE (field_definition_id, schema_version_id)
);

CREATE INDEX source_field_definition_schema_idx ON source.source_field_definition (schema_version_id);

CREATE TABLE source.parse_run (
    parse_run_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    content_object_id       uuid NOT NULL REFERENCES source.content_object(content_object_id),
    processing_activity_id  uuid NOT NULL UNIQUE REFERENCES provenance.processing_activity(processing_activity_id),
    status_code             text NOT NULL REFERENCES registry.parse_run_status(code)
);

COMMENT ON TABLE source.parse_run IS 'One versioned parsing attempt for immutable content. Parser name/version/configuration and execution timestamps are held by the linked processing_activity to avoid duplication.';

CREATE INDEX parse_run_content_idx ON source.parse_run (content_object_id);

CREATE TABLE source.parsed_record (
    parsed_record_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    parse_run_id       uuid NOT NULL REFERENCES source.parse_run(parse_run_id),
    schema_version_id  uuid NOT NULL REFERENCES source.source_schema_version(schema_version_id),
    record_locator     text NOT NULL,
    record_hash        text NOT NULL,
    CONSTRAINT parsed_record_locator_not_blank CHECK (btrim(record_locator) <> ''),
    CONSTRAINT parsed_record_hash_not_blank CHECK (btrim(record_hash) <> ''),
    CONSTRAINT parsed_record_locator_unique_per_run UNIQUE (parse_run_id, record_locator),
    CONSTRAINT parsed_record_id_schema_unique UNIQUE (parsed_record_id, schema_version_id)
);

CREATE INDEX parsed_record_schema_idx ON source.parsed_record (schema_version_id);
CREATE INDEX parsed_record_hash_idx ON source.parsed_record (record_hash);

CREATE TABLE source.source_field_value (
    source_field_value_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    parsed_record_id       uuid NOT NULL,
    field_definition_id    uuid NOT NULL,
    schema_version_id      uuid NOT NULL,
    raw_value              text NULL,
    parsed_value_json      jsonb NULL,
    structural_locator     text NULL,
    CONSTRAINT source_field_value_record_schema_fk
        FOREIGN KEY (parsed_record_id, schema_version_id)
        REFERENCES source.parsed_record(parsed_record_id, schema_version_id),
    CONSTRAINT source_field_value_field_schema_fk
        FOREIGN KEY (field_definition_id, schema_version_id)
        REFERENCES source.source_field_definition(field_definition_id, schema_version_id)
);

CREATE INDEX source_field_value_record_idx ON source.source_field_value (parsed_record_id);
CREATE INDEX source_field_value_field_idx ON source.source_field_value (field_definition_id);
CREATE INDEX source_field_value_schema_idx ON source.source_field_value (schema_version_id);

CREATE OR REPLACE FUNCTION source.guard_content_object_identity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'content_object rows are append-only and cannot be deleted'
            USING ERRCODE = '55000';
    END IF;
    IF NEW.sha256 IS DISTINCT FROM OLD.sha256 OR NEW.file_size IS DISTINCT FROM OLD.file_size THEN
        RAISE EXCEPTION 'content_object byte identity is immutable; create a new content object'
            USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER content_object_identity_immutable
BEFORE UPDATE OR DELETE ON source.content_object
FOR EACH ROW EXECUTE FUNCTION source.guard_content_object_identity();

CREATE OR REPLACE FUNCTION source.reject_source_field_value_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'source_field_value rows are immutable; create a new parse run instead'
        USING ERRCODE = '55000';
END;
$$;

CREATE TRIGGER source_field_value_immutable
BEFORE UPDATE OR DELETE ON source.source_field_value
FOR EACH ROW EXECUTE FUNCTION source.reject_source_field_value_mutation();

CREATE TABLE source.entity_mention (
    entity_mention_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    parsed_record_id    uuid NOT NULL REFERENCES source.parsed_record(parsed_record_id),
    mention_role_code   text NOT NULL REFERENCES registry.mention_role(code),
    UNIQUE (entity_mention_id, parsed_record_id)
);

CREATE INDEX entity_mention_record_idx ON source.entity_mention (parsed_record_id);

CREATE TABLE source.procedure_mention (
    procedure_mention_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    parsed_record_id      uuid NOT NULL REFERENCES source.parsed_record(parsed_record_id),
    entity_mention_id     uuid NULL,
    mention_type_code     text NOT NULL REFERENCES registry.mention_type(code),
    FOREIGN KEY (entity_mention_id, parsed_record_id)
        REFERENCES source.entity_mention(entity_mention_id, parsed_record_id)
);

CREATE INDEX procedure_mention_record_idx ON source.procedure_mention (parsed_record_id);
