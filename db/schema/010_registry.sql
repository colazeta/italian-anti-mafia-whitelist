CREATE TABLE IF NOT EXISTS registry.entity_class (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.entity_class IS 'Legal-entity class';

CREATE TABLE IF NOT EXISTS registry.name_type (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.name_type IS 'Entity-name type';

CREATE TABLE IF NOT EXISTS registry.verification_status (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.verification_status IS 'Identifier/attribute verification status';

CREATE TABLE IF NOT EXISTS registry.establishment_type (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.establishment_type IS 'Establishment type';

CREATE TABLE IF NOT EXISTS registry.competence_relevance (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.competence_relevance IS 'Relevance of an establishment to authority competence';

CREATE TABLE IF NOT EXISTS registry.authority_type (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.authority_type IS 'Public-authority type';

CREATE TABLE IF NOT EXISTS registry.jurisdiction_type (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.jurisdiction_type IS 'Authority jurisdiction type';

CREATE TABLE IF NOT EXISTS registry.sector_label_type (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.sector_label_type IS 'Sector label type';

CREATE TABLE IF NOT EXISTS registry.administrative_disposition (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.administrative_disposition IS 'Administrative disposition';

CREATE TABLE IF NOT EXISTS registry.legal_effect_status (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.legal_effect_status IS 'Legal effect status';

CREATE TABLE IF NOT EXISTS registry.sector_listing_status (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.sector_listing_status IS 'Status of a sector in the register';

CREATE TABLE IF NOT EXISTS registry.procedure_type (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.procedure_type IS 'White List procedure type';

CREATE TABLE IF NOT EXISTS registry.procedure_status (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.procedure_status IS 'White List procedure status';

CREATE TABLE IF NOT EXISTS registry.procedure_outcome (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.procedure_outcome IS 'White List procedure outcome';

CREATE TABLE IF NOT EXISTS registry.source_series_type (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.source_series_type IS 'Recurring source-series type';

CREATE TABLE IF NOT EXISTS registry.edition_identity_status (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.edition_identity_status IS 'Whether an edition identity is explicit or inferred';

CREATE TABLE IF NOT EXISTS registry.scope_completeness (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.scope_completeness IS 'Completeness of an edition scope';

CREATE TABLE IF NOT EXISTS registry.population_type (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.population_type IS 'Population represented by a source edition';

CREATE TABLE IF NOT EXISTS registry.resource_type (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.resource_type IS 'Source resource type';

CREATE TABLE IF NOT EXISTS registry.source_origin_type (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.source_origin_type IS 'Origin of a source capture';

CREATE TABLE IF NOT EXISTS registry.authority_rank (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.authority_rank IS 'Evidential/authority rank of a capture';

CREATE TABLE IF NOT EXISTS registry.capture_edition_relation_type (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.capture_edition_relation_type IS 'Relation between a capture and edition';

CREATE TABLE IF NOT EXISTS registry.attribution_status (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.attribution_status IS 'Confidence basis for capture-to-edition attribution';

CREATE TABLE IF NOT EXISTS registry.parse_run_status (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.parse_run_status IS 'Parser execution status';

CREATE TABLE IF NOT EXISTS registry.mention_role (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.mention_role IS 'Role of an entity mention in a parsed record';

CREATE TABLE IF NOT EXISTS registry.mention_type (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.mention_type IS 'Type of procedure mention';

CREATE TABLE IF NOT EXISTS registry.resolution_method (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.resolution_method IS 'Resolution method';

CREATE TABLE IF NOT EXISTS registry.decision_status (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.decision_status IS 'Resolution decision status';

CREATE TABLE IF NOT EXISTS registry.activity_type (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.activity_type IS 'Processing activity type';

CREATE TABLE IF NOT EXISTS registry.evidence_type (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.evidence_type IS 'Evidence item type';

CREATE TABLE IF NOT EXISTS registry.evidence_role (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.evidence_role IS 'Role of an evidence item';

CREATE TABLE IF NOT EXISTS registry.event_type (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.event_type IS 'Derived/observed event type';

CREATE TABLE IF NOT EXISTS registry.event_class (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.event_class IS 'Event class';

CREATE TABLE IF NOT EXISTS registry.time_precision (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.time_precision IS 'Precision of an event time';

CREATE TABLE IF NOT EXISTS registry.legal_review_status (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.legal_review_status IS 'Legal review status';

CREATE TABLE IF NOT EXISTS registry.review_status (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.review_status IS 'Generic review status';

CREATE TABLE IF NOT EXISTS registry.identifier_uniqueness_scope (
    code        text PRIMARY KEY,
    label       text NOT NULL,
    description text NULL
);
COMMENT ON TABLE registry.identifier_uniqueness_scope IS 'Uniqueness scope of an identifier scheme';

CREATE TABLE IF NOT EXISTS registry.legal_form (
    code       text PRIMARY KEY,
    label      text NOT NULL,
    scheme_uri text NULL,
    description text NULL
);
COMMENT ON TABLE registry.legal_form IS 'Legal-form vocabulary; intended to align to an external official code list where available.';
