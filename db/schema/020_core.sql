CREATE TABLE core.legal_entity (
    legal_entity_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_class_code    text NOT NULL REFERENCES registry.entity_class(code),
    legal_form_code      text NULL REFERENCES registry.legal_form(code),
    registration_country char(2) NULL,
    created_at           timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT legal_entity_country_upper CHECK (registration_country IS NULL OR registration_country = upper(registration_country))
);

COMMENT ON TABLE core.legal_entity IS 'Canonical subject represented in the White List archive. Identity is internal and never keyed by name, tax identifier, or VAT number.';

CREATE TABLE core.entity_name (
    entity_name_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_entity_id     uuid NOT NULL REFERENCES core.legal_entity(legal_entity_id),
    name_type_code      text NOT NULL REFERENCES registry.name_type(code),
    language_code       text NOT NULL DEFAULT 'it',
    name                text NOT NULL,
    normalised_name     text NOT NULL,
    effective_period    daterange NULL,
    observation_period  tstzrange NOT NULL,
    system_period       tstzrange NOT NULL DEFAULT tstzrange(CURRENT_TIMESTAMP, NULL, '[)'),
    processing_activity_id uuid NOT NULL REFERENCES provenance.processing_activity(processing_activity_id),
    CONSTRAINT entity_name_language_format CHECK (language_code ~ '^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$'),
    CONSTRAINT entity_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT entity_name_normalised_not_blank CHECK (btrim(normalised_name) <> ''),
    CONSTRAINT entity_name_effective_nonempty CHECK (effective_period IS NULL OR NOT isempty(effective_period)),
    CONSTRAINT entity_name_observation_valid CHECK (NOT isempty(observation_period) AND lower(observation_period) IS NOT NULL),
    CONSTRAINT entity_name_system_valid CHECK (NOT isempty(system_period) AND lower(system_period) IS NOT NULL)
);

CREATE INDEX entity_name_normalised_idx ON core.entity_name (normalised_name);
CREATE INDEX entity_name_entity_idx ON core.entity_name (legal_entity_id);
CREATE INDEX entity_name_observation_gist ON core.entity_name USING gist (observation_period);
CREATE INDEX entity_name_system_gist ON core.entity_name USING gist (system_period);

ALTER TABLE core.entity_name
    ADD CONSTRAINT entity_legal_name_no_overlap
    EXCLUDE USING gist (
        legal_entity_id WITH =,
        language_code WITH =,
        (COALESCE(effective_period, daterange(NULL, NULL, '()'))) WITH &&,
        observation_period WITH &&,
        system_period WITH &&
    )
    WHERE (name_type_code = 'legal_name');

CREATE TABLE core.identifier_scheme (
    identifier_scheme_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_code             text NOT NULL UNIQUE,
    scheme_uri              text NULL,
    uniqueness_scope_code   text NOT NULL REFERENCES registry.identifier_uniqueness_scope(code),
    description             text NULL
);

CREATE TABLE core.public_authority (
    public_authority_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    authority_type_code text NOT NULL REFERENCES registry.authority_type(code),
    preferred_name      text NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT public_authority_name_not_blank CHECK (btrim(preferred_name) <> '')
);

CREATE TABLE core.authority_identifier (
    authority_identifier_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_authority_id      uuid NOT NULL REFERENCES core.public_authority(public_authority_id),
    identifier_scheme       text NOT NULL,
    identifier_value        text NOT NULL,
    effective_period        daterange NULL,
    system_period           tstzrange NOT NULL DEFAULT tstzrange(CURRENT_TIMESTAMP, NULL, '[)'),
    CONSTRAINT authority_identifier_not_blank CHECK (btrim(identifier_value) <> ''),
    CONSTRAINT authority_identifier_effective_nonempty CHECK (effective_period IS NULL OR NOT isempty(effective_period)),
    CONSTRAINT authority_identifier_system_valid CHECK (NOT isempty(system_period) AND lower(system_period) IS NOT NULL)
);

CREATE INDEX authority_identifier_authority_idx ON core.authority_identifier (public_authority_id);

CREATE TABLE core.authority_jurisdiction (
    authority_jurisdiction_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_authority_id       uuid NOT NULL REFERENCES core.public_authority(public_authority_id),
    jurisdiction_type_code    text NOT NULL REFERENCES registry.jurisdiction_type(code),
    jurisdiction_code         text NOT NULL,
    effective_period          daterange NOT NULL,
    system_period             tstzrange NOT NULL DEFAULT tstzrange(CURRENT_TIMESTAMP, NULL, '[)'),
    CONSTRAINT authority_jurisdiction_code_not_blank CHECK (btrim(jurisdiction_code) <> ''),
    CONSTRAINT authority_jurisdiction_effective_valid CHECK (NOT isempty(effective_period) AND lower(effective_period) IS NOT NULL),
    CONSTRAINT authority_jurisdiction_system_valid CHECK (NOT isempty(system_period) AND lower(system_period) IS NOT NULL)
);

CREATE INDEX authority_jurisdiction_authority_idx ON core.authority_jurisdiction (public_authority_id);
CREATE INDEX authority_jurisdiction_effective_gist ON core.authority_jurisdiction USING gist (effective_period);

CREATE TABLE core.entity_identifier (
    entity_identifier_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_entity_id           uuid NOT NULL REFERENCES core.legal_entity(legal_entity_id),
    identifier_scheme_id      uuid NOT NULL REFERENCES core.identifier_scheme(identifier_scheme_id),
    identifier_value          text NOT NULL,
    normalised_value          text NOT NULL,
    issuing_authority_id      uuid NULL REFERENCES core.public_authority(public_authority_id),
    issuing_jurisdiction      text NULL,
    verification_status_code  text NOT NULL REFERENCES registry.verification_status(code),
    effective_period          daterange NULL,
    observation_period        tstzrange NOT NULL,
    system_period             tstzrange NOT NULL DEFAULT tstzrange(CURRENT_TIMESTAMP, NULL, '[)'),
    processing_activity_id     uuid NOT NULL REFERENCES provenance.processing_activity(processing_activity_id),
    CONSTRAINT entity_identifier_value_not_blank CHECK (btrim(identifier_value) <> ''),
    CONSTRAINT entity_identifier_normalised_not_blank CHECK (btrim(normalised_value) <> ''),
    CONSTRAINT entity_identifier_effective_nonempty CHECK (effective_period IS NULL OR NOT isempty(effective_period)),
    CONSTRAINT entity_identifier_observation_valid CHECK (NOT isempty(observation_period) AND lower(observation_period) IS NOT NULL),
    CONSTRAINT entity_identifier_system_valid CHECK (NOT isempty(system_period) AND lower(system_period) IS NOT NULL)
);

CREATE INDEX entity_identifier_entity_idx ON core.entity_identifier (legal_entity_id);
CREATE INDEX entity_identifier_lookup_idx ON core.entity_identifier (identifier_scheme_id, normalised_value);

CREATE TABLE core.address (
    address_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    full_address        text NOT NULL,
    street_name         text NULL,
    locator_designator  text NULL,
    postal_code         text NULL,
    locality            text NULL,
    admin_unit_l2       text NULL,
    admin_unit_l1       text NULL,
    country_code        char(2) NULL,
    processing_activity_id uuid NOT NULL REFERENCES provenance.processing_activity(processing_activity_id),
    created_at          timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT address_not_blank CHECK (btrim(full_address) <> ''),
    CONSTRAINT address_country_upper CHECK (country_code IS NULL OR country_code = upper(country_code))
);

CREATE TABLE core.establishment (
    establishment_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_entity_id           uuid NOT NULL REFERENCES core.legal_entity(legal_entity_id),
    establishment_type_code   text NOT NULL REFERENCES registry.establishment_type(code),
    establishment_name        text NULL,
    establishment_identifier  text NULL,
    competence_relevance_code text NULL REFERENCES registry.competence_relevance(code),
    effective_period          daterange NULL,
    observation_period        tstzrange NOT NULL,
    system_period             tstzrange NOT NULL DEFAULT tstzrange(CURRENT_TIMESTAMP, NULL, '[)'),
    processing_activity_id     uuid NOT NULL REFERENCES provenance.processing_activity(processing_activity_id),
    CONSTRAINT establishment_effective_nonempty CHECK (effective_period IS NULL OR NOT isempty(effective_period)),
    CONSTRAINT establishment_observation_valid CHECK (NOT isempty(observation_period) AND lower(observation_period) IS NOT NULL),
    CONSTRAINT establishment_system_valid CHECK (NOT isempty(system_period) AND lower(system_period) IS NOT NULL)
);

CREATE INDEX establishment_entity_idx ON core.establishment (legal_entity_id);

CREATE TABLE core.establishment_address (
    establishment_address_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    establishment_id         uuid NOT NULL REFERENCES core.establishment(establishment_id),
    address_id               uuid NOT NULL REFERENCES core.address(address_id),
    effective_period         daterange NULL,
    observation_period       tstzrange NOT NULL,
    system_period            tstzrange NOT NULL DEFAULT tstzrange(CURRENT_TIMESTAMP, NULL, '[)'),
    processing_activity_id    uuid NOT NULL REFERENCES provenance.processing_activity(processing_activity_id),
    CONSTRAINT establishment_address_effective_nonempty CHECK (effective_period IS NULL OR NOT isempty(effective_period)),
    CONSTRAINT establishment_address_observation_valid CHECK (NOT isempty(observation_period) AND lower(observation_period) IS NOT NULL),
    CONSTRAINT establishment_address_system_valid CHECK (NOT isempty(system_period) AND lower(system_period) IS NOT NULL)
);

CREATE INDEX establishment_address_establishment_idx ON core.establishment_address (establishment_id);
CREATE INDEX establishment_address_address_idx ON core.establishment_address (address_id);
