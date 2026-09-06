CREATE TABLE mapping.canonical_field (
    canonical_field_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_path     text NOT NULL UNIQUE,
    semantic_domain    text NOT NULL,
    definition         text NOT NULL,
    datatype           text NOT NULL,
    cardinality        text NOT NULL,
    standard_uri       text NULL,
    CONSTRAINT canonical_field_path_not_blank CHECK (btrim(canonical_path) <> '')
);

CREATE TABLE mapping.field_mapping (
    field_mapping_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    field_definition_id    uuid NOT NULL REFERENCES source.source_field_definition(field_definition_id),
    canonical_field_id     uuid NOT NULL REFERENCES mapping.canonical_field(canonical_field_id),
    mapping_rule           text NOT NULL,
    mapping_version        text NOT NULL,
    confidence             numeric(5,4) NOT NULL,
    information_loss_flag  boolean NOT NULL DEFAULT false,
    effective_from         timestamptz NOT NULL,
    effective_to           timestamptz NULL,
    CONSTRAINT field_mapping_confidence CHECK (confidence BETWEEN 0 AND 1),
    CONSTRAINT field_mapping_time_order CHECK (effective_to IS NULL OR effective_from <= effective_to)
);

CREATE INDEX field_mapping_source_field_idx ON mapping.field_mapping (field_definition_id);
CREATE INDEX field_mapping_canonical_idx ON mapping.field_mapping (canonical_field_id);

CREATE TABLE mapping.divergence_type (
    divergence_type_code text PRIMARY KEY,
    definition           text NOT NULL
);

CREATE TABLE mapping.field_divergence (
    field_divergence_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    field_definition_id   uuid NOT NULL REFERENCES source.source_field_definition(field_definition_id),
    divergence_type_code  text NOT NULL REFERENCES mapping.divergence_type(divergence_type_code),
    description           text NOT NULL,
    resolution_rule       text NOT NULL,
    review_status_code    text NOT NULL REFERENCES registry.review_status(code)
);

CREATE TABLE provenance.entity_resolution (
    entity_resolution_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_mention_id      uuid NOT NULL REFERENCES source.entity_mention(entity_mention_id),
    legal_entity_id        uuid NOT NULL REFERENCES core.legal_entity(legal_entity_id),
    resolution_method_code text NOT NULL REFERENCES registry.resolution_method(code),
    confidence_score       numeric(5,4) NOT NULL,
    decision_status_code   text NOT NULL REFERENCES registry.decision_status(code),
    processing_activity_id uuid NOT NULL REFERENCES provenance.processing_activity(processing_activity_id),
    system_period          tstzrange NOT NULL DEFAULT tstzrange(CURRENT_TIMESTAMP, NULL, '[)'),
    CONSTRAINT entity_resolution_confidence CHECK (confidence_score BETWEEN 0 AND 1),
    CONSTRAINT entity_resolution_system_valid CHECK (NOT isempty(system_period) AND lower(system_period) IS NOT NULL)
);

CREATE INDEX entity_resolution_mention_idx ON provenance.entity_resolution (entity_mention_id);
CREATE INDEX entity_resolution_entity_idx ON provenance.entity_resolution (legal_entity_id);

ALTER TABLE provenance.entity_resolution
    ADD CONSTRAINT entity_resolution_accepted_system_no_overlap
    EXCLUDE USING gist (
        entity_mention_id WITH =,
        system_period WITH &&
    )
    WHERE (decision_status_code = 'accepted');
CREATE UNIQUE INDEX entity_resolution_one_current_accepted
    ON provenance.entity_resolution (entity_mention_id)
    WHERE decision_status_code = 'accepted' AND upper_inf(system_period);

CREATE TABLE provenance.procedure_resolution (
    procedure_resolution_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    procedure_mention_id    uuid NOT NULL REFERENCES source.procedure_mention(procedure_mention_id),
    procedure_id            uuid NOT NULL REFERENCES whitelist.white_list_procedure(procedure_id),
    resolution_method_code  text NOT NULL REFERENCES registry.resolution_method(code),
    confidence_score        numeric(5,4) NOT NULL,
    decision_status_code    text NOT NULL REFERENCES registry.decision_status(code),
    processing_activity_id  uuid NOT NULL REFERENCES provenance.processing_activity(processing_activity_id),
    system_period           tstzrange NOT NULL DEFAULT tstzrange(CURRENT_TIMESTAMP, NULL, '[)'),
    CONSTRAINT procedure_resolution_confidence CHECK (confidence_score BETWEEN 0 AND 1),
    CONSTRAINT procedure_resolution_system_valid CHECK (NOT isempty(system_period) AND lower(system_period) IS NOT NULL)
);

CREATE INDEX procedure_resolution_mention_idx ON provenance.procedure_resolution (procedure_mention_id);
CREATE INDEX procedure_resolution_procedure_idx ON provenance.procedure_resolution (procedure_id);

ALTER TABLE provenance.procedure_resolution
    ADD CONSTRAINT procedure_resolution_accepted_system_no_overlap
    EXCLUDE USING gist (
        procedure_mention_id WITH =,
        system_period WITH &&
    )
    WHERE (decision_status_code = 'accepted');
CREATE UNIQUE INDEX procedure_resolution_one_current_accepted
    ON provenance.procedure_resolution (procedure_mention_id)
    WHERE decision_status_code = 'accepted' AND upper_inf(system_period);

CREATE TABLE provenance.evidence_item (
    evidence_item_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_type_code     text NOT NULL REFERENCES registry.evidence_type(code),
    source_field_value_id  uuid NULL REFERENCES source.source_field_value(source_field_value_id),
    parsed_record_id       uuid NULL REFERENCES source.parsed_record(parsed_record_id),
    source_edition_id      uuid NULL REFERENCES source.source_edition(edition_id),
    source_capture_id      uuid NULL REFERENCES source.source_capture(capture_id),
    created_at             timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT evidence_item_exactly_one_source CHECK (
        num_nonnulls(source_field_value_id, parsed_record_id, source_edition_id, source_capture_id) = 1
    ),
    CONSTRAINT evidence_item_type_matches_source CHECK (
        (evidence_type_code = 'field_value' AND source_field_value_id IS NOT NULL) OR
        (evidence_type_code = 'parsed_record' AND parsed_record_id IS NOT NULL) OR
        (evidence_type_code = 'source_edition' AND source_edition_id IS NOT NULL) OR
        (evidence_type_code = 'source_capture' AND source_capture_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX evidence_item_field_value_unique ON provenance.evidence_item (source_field_value_id) WHERE source_field_value_id IS NOT NULL;
CREATE UNIQUE INDEX evidence_item_parsed_record_unique ON provenance.evidence_item (parsed_record_id) WHERE parsed_record_id IS NOT NULL;
CREATE UNIQUE INDEX evidence_item_source_edition_unique ON provenance.evidence_item (source_edition_id) WHERE source_edition_id IS NOT NULL;
CREATE UNIQUE INDEX evidence_item_source_capture_unique ON provenance.evidence_item (source_capture_id) WHERE source_capture_id IS NOT NULL;

CREATE TABLE provenance.entity_name_evidence (
    evidence_link_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_name_id     uuid NOT NULL REFERENCES core.entity_name(entity_name_id),
    canonical_field_id uuid NULL REFERENCES mapping.canonical_field(canonical_field_id),
    evidence_item_id   uuid NOT NULL REFERENCES provenance.evidence_item(evidence_item_id),
    evidence_role_code text NOT NULL REFERENCES registry.evidence_role(code)
);

CREATE TABLE provenance.entity_identifier_evidence (
    evidence_link_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_identifier_id  uuid NOT NULL REFERENCES core.entity_identifier(entity_identifier_id),
    canonical_field_id    uuid NULL REFERENCES mapping.canonical_field(canonical_field_id),
    evidence_item_id      uuid NOT NULL REFERENCES provenance.evidence_item(evidence_item_id),
    evidence_role_code    text NOT NULL REFERENCES registry.evidence_role(code)
);

CREATE TABLE provenance.establishment_evidence (
    evidence_link_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    establishment_id     uuid NOT NULL REFERENCES core.establishment(establishment_id),
    canonical_field_id    uuid NULL REFERENCES mapping.canonical_field(canonical_field_id),
    evidence_item_id      uuid NOT NULL REFERENCES provenance.evidence_item(evidence_item_id),
    evidence_role_code    text NOT NULL REFERENCES registry.evidence_role(code)
);

CREATE TABLE provenance.address_evidence (
    evidence_link_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    address_id            uuid NOT NULL REFERENCES core.address(address_id),
    canonical_field_id    uuid NULL REFERENCES mapping.canonical_field(canonical_field_id),
    evidence_item_id      uuid NOT NULL REFERENCES provenance.evidence_item(evidence_item_id),
    evidence_role_code    text NOT NULL REFERENCES registry.evidence_role(code)
);

CREATE TABLE provenance.relationship_state_evidence (
    evidence_link_id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    relationship_state_version_id  uuid NOT NULL REFERENCES whitelist.relationship_state_version(relationship_state_version_id),
    canonical_field_id             uuid NULL REFERENCES mapping.canonical_field(canonical_field_id),
    evidence_item_id               uuid NOT NULL REFERENCES provenance.evidence_item(evidence_item_id),
    evidence_role_code             text NOT NULL REFERENCES registry.evidence_role(code)
);

CREATE TABLE provenance.relationship_sector_state_evidence (
    evidence_link_id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    relationship_sector_state_version_id  uuid NOT NULL REFERENCES whitelist.relationship_sector_state_version(relationship_sector_state_version_id),
    canonical_field_id                    uuid NULL REFERENCES mapping.canonical_field(canonical_field_id),
    evidence_item_id                      uuid NOT NULL REFERENCES provenance.evidence_item(evidence_item_id),
    evidence_role_code                    text NOT NULL REFERENCES registry.evidence_role(code)
);

CREATE TABLE provenance.procedure_version_evidence (
    evidence_link_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    procedure_version_id uuid NOT NULL REFERENCES whitelist.procedure_version(procedure_version_id),
    canonical_field_id uuid NULL REFERENCES mapping.canonical_field(canonical_field_id),
    evidence_item_id   uuid NOT NULL REFERENCES provenance.evidence_item(evidence_item_id),
    evidence_role_code text NOT NULL REFERENCES registry.evidence_role(code)
);
