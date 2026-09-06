-- Semantic projection and guarded canonicalisation layer.
-- Parsing remains immutable evidence extraction; semantic projection interprets
-- the parser record contract; canonicalisation promotes only assertions that
-- satisfy explicit deterministic rules.

ALTER TABLE core.legal_entity
    ADD COLUMN entity_code text NULL;
ALTER TABLE core.legal_entity
    ADD CONSTRAINT legal_entity_code_not_blank
    CHECK (entity_code IS NULL OR btrim(entity_code) <> '');
CREATE UNIQUE INDEX legal_entity_code_unique
    ON core.legal_entity(entity_code)
    WHERE entity_code IS NOT NULL;
COMMENT ON COLUMN core.legal_entity.entity_code IS
    'Stable internal project key created by a versioned resolver; never a source identifier.';

ALTER TABLE whitelist.white_list_procedure
    ADD COLUMN procedure_code text NULL;
ALTER TABLE whitelist.white_list_procedure
    ADD CONSTRAINT white_list_procedure_code_not_blank
    CHECK (procedure_code IS NULL OR btrim(procedure_code) <> '');
CREATE UNIQUE INDEX white_list_procedure_code_unique
    ON whitelist.white_list_procedure(procedure_code)
    WHERE procedure_code IS NOT NULL;
COMMENT ON COLUMN whitelist.white_list_procedure.procedure_code IS
    'Stable internal project key for an administratively interpreted procedure; not a source protocol number.';

ALTER TABLE source.procedure_mention
    ADD COLUMN procedure_mention_code text NULL;
ALTER TABLE source.procedure_mention
    ADD CONSTRAINT procedure_mention_code_not_blank
    CHECK (procedure_mention_code IS NULL OR btrim(procedure_mention_code) <> '');
CREATE UNIQUE INDEX procedure_mention_code_unique
    ON source.procedure_mention(procedure_mention_code)
    WHERE procedure_mention_code IS NOT NULL;

CREATE TABLE semantic.projection_run (
    projection_run_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    parse_run_id            uuid NOT NULL REFERENCES source.parse_run(parse_run_id),
    processing_activity_id  uuid NOT NULL UNIQUE REFERENCES provenance.processing_activity(processing_activity_id),
    projection_run_code     text NOT NULL UNIQUE,
    projector_code          text NOT NULL,
    projector_version       text NOT NULL,
    record_contract_code    text NOT NULL,
    status_code             text NOT NULL REFERENCES registry.parse_run_status(code),
    created_at              timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT projection_run_code_not_blank CHECK (btrim(projection_run_code) <> ''),
    CONSTRAINT projection_projector_not_blank CHECK (btrim(projector_code) <> ''),
    CONSTRAINT projection_version_not_blank CHECK (btrim(projector_version) <> ''),
    CONSTRAINT projection_contract_not_blank CHECK (btrim(record_contract_code) <> '')
);
CREATE INDEX projection_run_parse_idx ON semantic.projection_run(parse_run_id);

CREATE TABLE semantic.entity_observation (
    entity_observation_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    projection_run_id            uuid NOT NULL REFERENCES semantic.projection_run(projection_run_id),
    entity_mention_id            uuid NOT NULL REFERENCES source.entity_mention(entity_mention_id),
    parsed_record_id             uuid NOT NULL REFERENCES source.parsed_record(parsed_record_id),
    edition_id                   uuid NOT NULL REFERENCES source.source_edition(edition_id),
    observation_date             date NOT NULL,
    source_name_raw              text NOT NULL,
    source_name_normalised       text NOT NULL,
    name_source_field_value_id   uuid NOT NULL REFERENCES source.source_field_value(source_field_value_id),
    resolution_readiness_code    text NOT NULL,
    CONSTRAINT entity_observation_name_not_blank CHECK (btrim(source_name_raw) <> ''),
    CONSTRAINT entity_observation_normalised_not_blank CHECK (btrim(source_name_normalised) <> ''),
    CONSTRAINT entity_observation_readiness CHECK (
        resolution_readiness_code IN ('ready','requires_resolution','requires_review')
    ),
    CONSTRAINT entity_observation_unique UNIQUE (projection_run_id, entity_mention_id)
);
CREATE INDEX entity_observation_mention_idx ON semantic.entity_observation(entity_mention_id);
CREATE INDEX entity_observation_name_idx ON semantic.entity_observation(source_name_normalised);

CREATE TABLE semantic.identifier_observation (
    identifier_observation_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_observation_id      uuid NOT NULL REFERENCES semantic.entity_observation(entity_observation_id) ON DELETE CASCADE,
    source_field_value_id      uuid NOT NULL REFERENCES source.source_field_value(source_field_value_id),
    raw_value                  text NOT NULL,
    normalised_value           text NOT NULL,
    shape_code                 text NOT NULL,
    scheme_assertion_code      text NOT NULL,
    candidate_schemes_json     jsonb NOT NULL DEFAULT '[]'::jsonb,
    source_hint                text NULL,
    CONSTRAINT identifier_observation_raw_not_blank CHECK (btrim(raw_value) <> ''),
    CONSTRAINT identifier_observation_normalised_not_blank CHECK (btrim(normalised_value) <> ''),
    CONSTRAINT identifier_observation_unique UNIQUE (entity_observation_id, normalised_value)
);
CREATE INDEX identifier_observation_lookup_idx ON semantic.identifier_observation(normalised_value);

CREATE TABLE semantic.establishment_observation (
    establishment_observation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_observation_id         uuid NOT NULL REFERENCES semantic.entity_observation(entity_observation_id) ON DELETE CASCADE,
    source_field_value_id         uuid NOT NULL REFERENCES source.source_field_value(source_field_value_id),
    establishment_type_code       text NOT NULL REFERENCES registry.establishment_type(code),
    full_address_raw              text NOT NULL,
    CONSTRAINT establishment_observation_address_not_blank CHECK (btrim(full_address_raw) <> ''),
    CONSTRAINT establishment_observation_unique UNIQUE (
        entity_observation_id, establishment_type_code, full_address_raw
    )
);

CREATE TABLE semantic.relationship_observation (
    relationship_observation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    projection_run_id           uuid NOT NULL REFERENCES semantic.projection_run(projection_run_id),
    entity_observation_id       uuid NOT NULL REFERENCES semantic.entity_observation(entity_observation_id) ON DELETE CASCADE,
    register_id                 uuid NOT NULL REFERENCES whitelist.white_list_register(register_id),
    outcome_source_field_value_id uuid NOT NULL REFERENCES source.source_field_value(source_field_value_id),
    source_status_code          text NOT NULL,
    outcome_raw                 text NOT NULL,
    observed_listing_date       date NULL,
    observed_expiry_date        date NULL,
    renewal_requested           boolean NOT NULL DEFAULT false,
    update_in_progress          boolean NOT NULL DEFAULT false,
    CONSTRAINT relationship_observation_status CHECK (
        source_status_code IN (
            'listed','pending','renewal_requested','renewal_update_in_progress',
            'rejected_or_denied','cancellation_related','other_or_unknown'
        )
    ),
    CONSTRAINT relationship_observation_dates CHECK (
        observed_listing_date IS NULL OR observed_expiry_date IS NULL OR observed_listing_date <= observed_expiry_date
    ),
    CONSTRAINT relationship_observation_unique UNIQUE (projection_run_id, entity_observation_id, register_id)
);
CREATE INDEX relationship_observation_entity_idx ON semantic.relationship_observation(entity_observation_id);

CREATE TABLE semantic.procedure_observation (
    procedure_observation_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    relationship_observation_id   uuid NOT NULL REFERENCES semantic.relationship_observation(relationship_observation_id) ON DELETE CASCADE,
    procedure_mention_id          uuid NOT NULL REFERENCES source.procedure_mention(procedure_mention_id),
    application_source_field_value_id uuid NOT NULL REFERENCES source.source_field_value(source_field_value_id),
    outcome_source_field_value_id uuid NOT NULL REFERENCES source.source_field_value(source_field_value_id),
    application_date              date NOT NULL,
    parenthesized_in_source       boolean NOT NULL DEFAULT false,
    projected_procedure_type_code text NOT NULL REFERENCES registry.procedure_type(code),
    projected_status_code         text NOT NULL REFERENCES registry.procedure_status(code),
    projected_outcome_code        text NULL REFERENCES registry.procedure_outcome(code),
    observed_decision_date        date NULL,
    canonicalisation_eligible     boolean NOT NULL,
    CONSTRAINT procedure_observation_unique UNIQUE (relationship_observation_id, procedure_mention_id)
);
CREATE INDEX procedure_observation_relationship_idx ON semantic.procedure_observation(relationship_observation_id);

CREATE TABLE semantic.procedure_sector_observation (
    procedure_sector_observation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    procedure_observation_id         uuid NOT NULL REFERENCES semantic.procedure_observation(procedure_observation_id) ON DELETE CASCADE,
    source_field_value_id            uuid NOT NULL REFERENCES source.source_field_value(source_field_value_id),
    source_activity_raw              text NOT NULL,
    source_activity_normalised       text NOT NULL,
    sector_concept_id                uuid NULL REFERENCES whitelist.sector_concept(sector_concept_id),
    scheme_membership_id             uuid NULL REFERENCES whitelist.sector_scheme_membership(scheme_membership_id),
    mapping_status_code              text NOT NULL,
    mapping_confidence               numeric(5,4) NOT NULL,
    CONSTRAINT procedure_sector_mapping_status CHECK (
        mapping_status_code IN ('mapped','unmapped','requires_review')
    ),
    CONSTRAINT procedure_sector_mapping_confidence CHECK (mapping_confidence BETWEEN 0 AND 1),
    CONSTRAINT procedure_sector_observation_unique UNIQUE (
        procedure_observation_id, source_activity_normalised
    )
);

CREATE TABLE semantic.projection_issue (
    projection_issue_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    projection_run_id        uuid NOT NULL REFERENCES semantic.projection_run(projection_run_id),
    parsed_record_id         uuid NOT NULL REFERENCES source.parsed_record(parsed_record_id),
    issue_code               text NOT NULL,
    severity_code            text NOT NULL,
    field_name               text NULL,
    source_value             text NULL,
    details_json             jsonb NULL,
    review_status_code       text NOT NULL DEFAULT 'open' REFERENCES registry.review_status(code),
    CONSTRAINT projection_issue_severity CHECK (severity_code IN ('info','warning','error')),
    CONSTRAINT projection_issue_code_not_blank CHECK (btrim(issue_code) <> '')
);
CREATE INDEX projection_issue_record_idx ON semantic.projection_issue(parsed_record_id);

CREATE TABLE semantic.canonicalisation_run (
    canonicalisation_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    series_id                uuid NOT NULL REFERENCES source.source_series(series_id),
    processing_activity_id   uuid NOT NULL UNIQUE REFERENCES provenance.processing_activity(processing_activity_id),
    canonicalisation_run_code text NOT NULL UNIQUE,
    resolver_code            text NOT NULL,
    resolver_version         text NOT NULL,
    status_code              text NOT NULL REFERENCES registry.parse_run_status(code),
    created_at               timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT canonicalisation_run_code_not_blank CHECK (btrim(canonicalisation_run_code) <> '')
);

CREATE TABLE semantic.entity_projection_resolution (
    entity_observation_id      uuid PRIMARY KEY REFERENCES semantic.entity_observation(entity_observation_id) ON DELETE CASCADE,
    canonicalisation_run_id    uuid NOT NULL REFERENCES semantic.canonicalisation_run(canonicalisation_run_id),
    legal_entity_id            uuid NULL REFERENCES core.legal_entity(legal_entity_id),
    decision_status_code       text NOT NULL,
    confidence_score           numeric(5,4) NULL,
    decision_reason            text NOT NULL,
    CONSTRAINT entity_projection_resolution_status CHECK (
        decision_status_code IN ('accepted','requires_resolution','requires_review')
    ),
    CONSTRAINT entity_projection_resolution_confidence CHECK (
        confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1
    )
);
