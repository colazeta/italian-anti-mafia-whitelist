CREATE TABLE derived.derived_event (
    derived_event_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_entity_id        uuid NULL REFERENCES core.legal_entity(legal_entity_id),
    relationship_id        uuid NULL REFERENCES whitelist.white_list_relationship(relationship_id),
    event_type_code        text NOT NULL REFERENCES registry.event_type(code),
    event_class_code       text NOT NULL REFERENCES registry.event_class(code),
    time_lower_bound       timestamptz NULL,
    time_upper_bound       timestamptz NULL,
    time_precision_code    text NOT NULL REFERENCES registry.time_precision(code),
    confidence_score       numeric(5,4) NULL,
    derivation_rule        text NOT NULL,
    derivation_version     text NOT NULL,
    processing_activity_id uuid NOT NULL REFERENCES provenance.processing_activity(processing_activity_id),
    generated_at           timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT derived_event_subject CHECK (legal_entity_id IS NOT NULL OR relationship_id IS NOT NULL),
    CONSTRAINT derived_event_time_order CHECK (time_lower_bound IS NULL OR time_upper_bound IS NULL OR time_lower_bound <= time_upper_bound),
    CONSTRAINT derived_event_confidence CHECK (confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1)
);

CREATE INDEX derived_event_entity_idx ON derived.derived_event (legal_entity_id, time_lower_bound);
CREATE INDEX derived_event_relationship_idx ON derived.derived_event (relationship_id, time_lower_bound);

CREATE TABLE derived.derived_event_relationship_state_input (
    derived_event_id              uuid NOT NULL REFERENCES derived.derived_event(derived_event_id) ON DELETE CASCADE,
    relationship_state_version_id uuid NOT NULL REFERENCES whitelist.relationship_state_version(relationship_state_version_id),
    PRIMARY KEY (derived_event_id, relationship_state_version_id)
);

CREATE TABLE derived.derived_event_sector_state_input (
    derived_event_id                     uuid NOT NULL REFERENCES derived.derived_event(derived_event_id) ON DELETE CASCADE,
    relationship_sector_state_version_id uuid NOT NULL REFERENCES whitelist.relationship_sector_state_version(relationship_sector_state_version_id),
    PRIMARY KEY (derived_event_id, relationship_sector_state_version_id)
);

CREATE TABLE derived.derived_event_procedure_version_input (
    derived_event_id   uuid NOT NULL REFERENCES derived.derived_event(derived_event_id) ON DELETE CASCADE,
    procedure_version_id uuid NOT NULL REFERENCES whitelist.procedure_version(procedure_version_id),
    PRIMARY KEY (derived_event_id, procedure_version_id)
);

CREATE TABLE governance.dissemination_policy (
    dissemination_policy_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_code              text NOT NULL UNIQUE,
    description              text NOT NULL
);

CREATE TABLE governance.dissemination_profile (
    dissemination_profile_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_code              text NOT NULL UNIQUE,
    description               text NOT NULL
);

CREATE TABLE governance.canonical_field_dissemination (
    dissemination_profile_id  uuid NOT NULL REFERENCES governance.dissemination_profile(dissemination_profile_id),
    canonical_field_id         uuid NOT NULL REFERENCES mapping.canonical_field(canonical_field_id),
    dissemination_policy_id    uuid NOT NULL REFERENCES governance.dissemination_policy(dissemination_policy_id),
    transformation_rule        text NULL,
    legal_review_status_code   text NOT NULL REFERENCES registry.legal_review_status(code),
    PRIMARY KEY (dissemination_profile_id, canonical_field_id)
);
