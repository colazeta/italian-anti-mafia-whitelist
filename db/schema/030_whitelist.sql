CREATE TABLE whitelist.white_list_regime (
    regime_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    regime_code       text NOT NULL UNIQUE,
    preferred_label   text NOT NULL,
    description       text NULL,
    legal_basis_uri   text NULL,
    effective_period  daterange NOT NULL,
    CONSTRAINT white_list_regime_code_not_blank CHECK (btrim(regime_code) <> ''),
    CONSTRAINT white_list_regime_effective_valid CHECK (NOT isempty(effective_period) AND lower(effective_period) IS NOT NULL)
);

CREATE TABLE whitelist.white_list_register (
    register_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_authority_id uuid NOT NULL REFERENCES core.public_authority(public_authority_id),
    regime_id           uuid NOT NULL REFERENCES whitelist.white_list_regime(regime_id),
    register_code       text NOT NULL UNIQUE,
    official_name       text NOT NULL,
    effective_period    daterange NOT NULL,
    CONSTRAINT white_list_register_name_not_blank CHECK (btrim(official_name) <> ''),
    CONSTRAINT white_list_register_effective_valid CHECK (NOT isempty(effective_period) AND lower(effective_period) IS NOT NULL)
);

CREATE INDEX white_list_register_authority_idx ON whitelist.white_list_register (public_authority_id);
CREATE INDEX white_list_register_regime_idx ON whitelist.white_list_register (regime_id);

CREATE TABLE whitelist.sector_concept (
    sector_concept_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    concept_code      text NOT NULL UNIQUE,
    concept_uri       text NULL UNIQUE,
    CONSTRAINT sector_concept_code_not_blank CHECK (btrim(concept_code) <> '')
);

CREATE TABLE whitelist.sector_concept_label (
    sector_label_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sector_concept_id  uuid NOT NULL REFERENCES whitelist.sector_concept(sector_concept_id),
    label              text NOT NULL,
    label_type_code    text NOT NULL REFERENCES registry.sector_label_type(code),
    language_code      text NOT NULL DEFAULT 'it',
    effective_period   daterange NULL,
    CONSTRAINT sector_label_language_format CHECK (language_code ~ '^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$'),
    CONSTRAINT sector_label_not_blank CHECK (btrim(label) <> ''),
    CONSTRAINT sector_label_effective_nonempty CHECK (effective_period IS NULL OR NOT isempty(effective_period))
);

CREATE INDEX sector_concept_label_concept_idx ON whitelist.sector_concept_label (sector_concept_id);

ALTER TABLE whitelist.sector_concept_label
    ADD CONSTRAINT sector_preferred_label_no_overlap
    EXCLUDE USING gist (
        sector_concept_id WITH =,
        language_code WITH =,
        (COALESCE(effective_period, daterange(NULL, NULL, '()'))) WITH &&
    )
    WHERE (label_type_code = 'preferred');

CREATE TABLE whitelist.sector_scheme_version (
    scheme_version_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    regime_id         uuid NOT NULL REFERENCES whitelist.white_list_regime(regime_id),
    version_code      text NOT NULL,
    legal_basis_uri   text NULL,
    effective_period  daterange NOT NULL,
    CONSTRAINT sector_scheme_version_code_not_blank CHECK (btrim(version_code) <> ''),
    CONSTRAINT sector_scheme_version_effective_valid CHECK (NOT isempty(effective_period) AND lower(effective_period) IS NOT NULL),
    CONSTRAINT sector_scheme_version_unique UNIQUE (regime_id, version_code)
);

ALTER TABLE whitelist.sector_scheme_version
    ADD CONSTRAINT sector_scheme_version_no_overlap
    EXCLUDE USING gist (
        regime_id WITH =,
        effective_period WITH &&
    );

CREATE TABLE whitelist.sector_scheme_membership (
    scheme_membership_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_version_id    uuid NOT NULL REFERENCES whitelist.sector_scheme_version(scheme_version_id),
    sector_concept_id    uuid NOT NULL REFERENCES whitelist.sector_concept(sector_concept_id),
    notation             text NOT NULL,
    legal_label          text NOT NULL,
    effective_period     daterange NOT NULL,
    CONSTRAINT sector_scheme_membership_notation_not_blank CHECK (btrim(notation) <> ''),
    CONSTRAINT sector_scheme_membership_label_not_blank CHECK (btrim(legal_label) <> ''),
    CONSTRAINT sector_scheme_membership_effective_valid CHECK (NOT isempty(effective_period) AND lower(effective_period) IS NOT NULL),
    CONSTRAINT sector_scheme_notation_unique UNIQUE (scheme_version_id, notation),
    CONSTRAINT sector_scheme_concept_unique UNIQUE (scheme_version_id, sector_concept_id)
);

CREATE INDEX sector_scheme_membership_concept_idx ON whitelist.sector_scheme_membership (sector_concept_id);

CREATE OR REPLACE FUNCTION whitelist.enforce_sector_membership_period()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_period daterange;
BEGIN
    SELECT effective_period
      INTO parent_period
      FROM whitelist.sector_scheme_version
     WHERE scheme_version_id = NEW.scheme_version_id;

    IF parent_period IS NULL OR NOT (NEW.effective_period <@ parent_period) THEN
        RAISE EXCEPTION 'sector membership effective period must be contained in its scheme version'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER sector_membership_period_guard
BEFORE INSERT OR UPDATE ON whitelist.sector_scheme_membership
FOR EACH ROW EXECUTE FUNCTION whitelist.enforce_sector_membership_period();

CREATE TABLE whitelist.white_list_relationship (
    relationship_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_entity_id  uuid NOT NULL REFERENCES core.legal_entity(legal_entity_id),
    register_id      uuid NOT NULL REFERENCES whitelist.white_list_register(register_id),
    created_at       timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT white_list_relationship_unique UNIQUE (legal_entity_id, register_id)
);

CREATE INDEX white_list_relationship_entity_idx ON whitelist.white_list_relationship (legal_entity_id);
CREATE INDEX white_list_relationship_register_idx ON whitelist.white_list_relationship (register_id);

CREATE TABLE whitelist.relationship_state_version (
    relationship_state_version_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    relationship_id                 uuid NOT NULL REFERENCES whitelist.white_list_relationship(relationship_id),
    administrative_disposition_code text NULL REFERENCES registry.administrative_disposition(code),
    legal_effect_status_code        text NOT NULL REFERENCES registry.legal_effect_status(code),
    nominal_valid_from              date NULL,
    nominal_valid_until             date NULL,
    effective_period                daterange NULL,
    observation_period              tstzrange NOT NULL,
    system_period                   tstzrange NOT NULL DEFAULT tstzrange(CURRENT_TIMESTAMP, NULL, '[)'),
    processing_activity_id          uuid NOT NULL REFERENCES provenance.processing_activity(processing_activity_id),
    CONSTRAINT relationship_state_nominal_dates CHECK (
        nominal_valid_from IS NULL OR nominal_valid_until IS NULL OR nominal_valid_from <= nominal_valid_until
    ),
    CONSTRAINT relationship_state_effective_nonempty CHECK (effective_period IS NULL OR NOT isempty(effective_period)),
    CONSTRAINT relationship_state_observation_valid CHECK (NOT isempty(observation_period) AND lower(observation_period) IS NOT NULL),
    CONSTRAINT relationship_state_system_valid CHECK (NOT isempty(system_period) AND lower(system_period) IS NOT NULL)
);

CREATE INDEX relationship_state_relationship_idx ON whitelist.relationship_state_version (relationship_id);
CREATE INDEX relationship_state_effective_gist ON whitelist.relationship_state_version USING gist (effective_period);
CREATE INDEX relationship_state_observation_gist ON whitelist.relationship_state_version USING gist (observation_period);
CREATE INDEX relationship_state_system_gist ON whitelist.relationship_state_version USING gist (system_period);

ALTER TABLE whitelist.relationship_state_version
    ADD CONSTRAINT relationship_state_tri_temporal_no_overlap
    EXCLUDE USING gist (
        relationship_id WITH =,
        (COALESCE(effective_period, daterange(NULL, NULL, '()'))) WITH &&,
        observation_period WITH &&,
        system_period WITH &&
    );

CREATE TABLE whitelist.relationship_sector (
    relationship_sector_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    relationship_id        uuid NOT NULL REFERENCES whitelist.white_list_relationship(relationship_id),
    sector_concept_id      uuid NOT NULL REFERENCES whitelist.sector_concept(sector_concept_id),
    CONSTRAINT relationship_sector_unique UNIQUE (relationship_id, sector_concept_id)
);

CREATE TABLE whitelist.relationship_sector_state_version (
    relationship_sector_state_version_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    relationship_sector_id               uuid NOT NULL REFERENCES whitelist.relationship_sector(relationship_sector_id),
    scheme_membership_id                 uuid NULL REFERENCES whitelist.sector_scheme_membership(scheme_membership_id),
    sector_listing_status_code           text NOT NULL REFERENCES registry.sector_listing_status(code),
    effective_period                     daterange NULL,
    observation_period                   tstzrange NOT NULL,
    system_period                        tstzrange NOT NULL DEFAULT tstzrange(CURRENT_TIMESTAMP, NULL, '[)'),
    processing_activity_id               uuid NOT NULL REFERENCES provenance.processing_activity(processing_activity_id),
    CONSTRAINT relationship_sector_state_effective_nonempty CHECK (effective_period IS NULL OR NOT isempty(effective_period)),
    CONSTRAINT relationship_sector_state_observation_valid CHECK (NOT isempty(observation_period) AND lower(observation_period) IS NOT NULL),
    CONSTRAINT relationship_sector_state_system_valid CHECK (NOT isempty(system_period) AND lower(system_period) IS NOT NULL)
);

CREATE INDEX relationship_sector_state_sector_idx ON whitelist.relationship_sector_state_version (relationship_sector_id);

ALTER TABLE whitelist.relationship_sector_state_version
    ADD CONSTRAINT relationship_sector_state_tri_temporal_no_overlap
    EXCLUDE USING gist (
        relationship_sector_id WITH =,
        (COALESCE(effective_period, daterange(NULL, NULL, '()'))) WITH &&,
        observation_period WITH &&,
        system_period WITH &&
    );

CREATE OR REPLACE FUNCTION whitelist.enforce_relationship_sector_membership()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    relationship_concept uuid;
    relationship_regime uuid;
    membership_concept uuid;
    membership_regime uuid;
BEGIN
    IF NEW.scheme_membership_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT rs.sector_concept_id, reg.regime_id
      INTO relationship_concept, relationship_regime
      FROM whitelist.relationship_sector rs
      JOIN whitelist.white_list_relationship rel ON rel.relationship_id = rs.relationship_id
      JOIN whitelist.white_list_register reg ON reg.register_id = rel.register_id
     WHERE rs.relationship_sector_id = NEW.relationship_sector_id;

    SELECT sm.sector_concept_id, sv.regime_id
      INTO membership_concept, membership_regime
      FROM whitelist.sector_scheme_membership sm
      JOIN whitelist.sector_scheme_version sv ON sv.scheme_version_id = sm.scheme_version_id
     WHERE sm.scheme_membership_id = NEW.scheme_membership_id;

    IF relationship_concept IS DISTINCT FROM membership_concept THEN
        RAISE EXCEPTION 'scheme membership sector concept does not match relationship sector'
            USING ERRCODE = '23514';
    END IF;
    IF relationship_regime IS DISTINCT FROM membership_regime THEN
        RAISE EXCEPTION 'scheme membership regime does not match relationship register regime'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER relationship_sector_membership_guard
BEFORE INSERT OR UPDATE ON whitelist.relationship_sector_state_version
FOR EACH ROW EXECUTE FUNCTION whitelist.enforce_relationship_sector_membership();

CREATE TABLE whitelist.white_list_procedure (
    procedure_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    relationship_id  uuid NOT NULL REFERENCES whitelist.white_list_relationship(relationship_id),
    created_at       timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX white_list_procedure_relationship_idx ON whitelist.white_list_procedure (relationship_id);

CREATE TABLE whitelist.procedure_version (
    procedure_version_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    procedure_id            uuid NOT NULL REFERENCES whitelist.white_list_procedure(procedure_id),
    procedure_type_code     text NOT NULL REFERENCES registry.procedure_type(code),
    official_identifier     text NULL,
    application_date        date NULL,
    decision_date           date NULL,
    procedure_status_code   text NOT NULL REFERENCES registry.procedure_status(code),
    procedure_outcome_code  text NULL REFERENCES registry.procedure_outcome(code),
    effective_period        daterange NULL,
    observation_period      tstzrange NOT NULL,
    system_period           tstzrange NOT NULL DEFAULT tstzrange(CURRENT_TIMESTAMP, NULL, '[)'),
    processing_activity_id  uuid NOT NULL REFERENCES provenance.processing_activity(processing_activity_id),
    CONSTRAINT procedure_version_dates CHECK (application_date IS NULL OR decision_date IS NULL OR application_date <= decision_date),
    CONSTRAINT procedure_version_effective_nonempty CHECK (effective_period IS NULL OR NOT isempty(effective_period)),
    CONSTRAINT procedure_version_observation_valid CHECK (NOT isempty(observation_period) AND lower(observation_period) IS NOT NULL),
    CONSTRAINT procedure_version_system_valid CHECK (NOT isempty(system_period) AND lower(system_period) IS NOT NULL)
);

CREATE INDEX procedure_version_procedure_idx ON whitelist.procedure_version (procedure_id);

ALTER TABLE whitelist.procedure_version
    ADD CONSTRAINT procedure_version_tri_temporal_no_overlap
    EXCLUDE USING gist (
        procedure_id WITH =,
        (COALESCE(effective_period, daterange(NULL, NULL, '()'))) WITH &&,
        observation_period WITH &&,
        system_period WITH &&
    );

CREATE TABLE whitelist.procedure_sector (
    procedure_sector_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    procedure_id        uuid NOT NULL REFERENCES whitelist.white_list_procedure(procedure_id),
    sector_concept_id   uuid NOT NULL REFERENCES whitelist.sector_concept(sector_concept_id),
    CONSTRAINT procedure_sector_unique UNIQUE (procedure_id, sector_concept_id)
);
