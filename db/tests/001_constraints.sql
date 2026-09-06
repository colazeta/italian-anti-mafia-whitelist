\set ON_ERROR_STOP on
BEGIN;

-- Shared processing activities ------------------------------------------------
INSERT INTO provenance.processing_activity(
    processing_activity_id, activity_type_code, software_name, software_version, configuration_hash,
    started_at, completed_at
) VALUES
('61000000-0000-0000-0000-000000000001','normalise','test-normaliser','1.0','test','2026-01-01','2026-01-01'),
('61000000-0000-0000-0000-000000000002','parse','test-parser','1.0','v1','2026-01-01','2026-01-01'),
('61000000-0000-0000-0000-000000000003','parse','test-parser','2.0','v2','2026-02-01','2026-02-01'),
('61000000-0000-0000-0000-000000000004','entity_resolve','test-resolver','1.0','test','2026-02-01','2026-02-01'),
('61000000-0000-0000-0000-000000000005','procedure_resolve','test-procedure-resolver','1.0','test','2026-02-01','2026-02-01'),
('61000000-0000-0000-0000-000000000006','derive_event','test-event-deriver','1.0','test','2026-02-01','2026-02-01');

-- Core fixtures ----------------------------------------------------------------
INSERT INTO core.public_authority(public_authority_id, authority_type_code, preferred_name)
VALUES ('10000000-0000-0000-0000-000000000001', 'prefecture_utg', 'Test Prefecture');

INSERT INTO core.legal_entity(legal_entity_id, entity_class_code, registration_country)
VALUES
('20000000-0000-0000-0000-000000000001', 'organisation', 'IT'),
('20000000-0000-0000-0000-000000000002', 'organisation', 'IT'),
('20000000-0000-0000-0000-000000000003', 'organisation', 'IT');

INSERT INTO core.entity_name(
    entity_name_id, legal_entity_id, name_type_code, language_code, name, normalised_name,
    observation_period, system_period, processing_activity_id
) VALUES (
    '21000000-0000-0000-0000-000000000001',
    '20000000-0000-0000-0000-000000000001',
    'legal_name','it','Impresa Test S.r.l.','IMPRESA TEST SRL',
    tstzrange('2020-01-01 00:00+00',NULL,'[)'),
    tstzrange('2020-01-01 00:00+00',NULL,'[)'),
    '61000000-0000-0000-0000-000000000001'
);

INSERT INTO whitelist.white_list_register(
    register_id, public_authority_id, regime_id, register_code, official_name, effective_period
)
SELECT
    '30000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    regime_id,
    'TEST-REGISTER',
    'Test White List Register',
    daterange('2020-01-01', NULL, '[)')
FROM whitelist.white_list_regime
WHERE regime_code='WL-REGIME-L190-2012';

INSERT INTO whitelist.white_list_relationship(relationship_id, legal_entity_id, register_id)
VALUES
('40000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000001'),
('40000000-0000-0000-0000-000000000002','20000000-0000-0000-0000-000000000002','30000000-0000-0000-0000-000000000001'),
('40000000-0000-0000-0000-000000000003','20000000-0000-0000-0000-000000000003','30000000-0000-0000-0000-000000000001');

-- 1. Duplicate entity/register relationship must fail -------------------------
DO $$
BEGIN
    BEGIN
        INSERT INTO whitelist.white_list_relationship(legal_entity_id, register_id)
        VALUES ('20000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001');
        RAISE EXCEPTION 'TEST FAILED: duplicate White List relationship was accepted';
    EXCEPTION WHEN unique_violation THEN
        NULL;
    END;
END $$;

-- 2. True unbounded system periods must be current ----------------------------
DO $$
DECLARE r tstzrange := tstzrange('2026-01-01 00:00+00', NULL, '[)');
BEGIN
    IF NOT upper_inf(r) THEN
        RAISE EXCEPTION 'TEST FAILED: true unbounded tstzrange was not recognised by upper_inf()';
    END IF;
END $$;

-- 3. Tri-temporal overlap must fail, including historical system time ---------
INSERT INTO whitelist.relationship_state_version(
    relationship_state_version_id, relationship_id,
    administrative_disposition_code, legal_effect_status_code,
    effective_period, observation_period, system_period, processing_activity_id
) VALUES (
    '50000000-0000-0000-0000-000000000001',
    '40000000-0000-0000-0000-000000000001',
    'registered', 'effective',
    daterange('2020-01-01',NULL,'[)'),
    tstzrange('2020-01-01 00:00+00',NULL,'[)'),
    tstzrange('2020-01-01 00:00+00',NULL,'[)'),
    '61000000-0000-0000-0000-000000000001'
);

DO $$
BEGIN
    BEGIN
        INSERT INTO whitelist.relationship_state_version(
            relationship_id, administrative_disposition_code, legal_effect_status_code,
            effective_period, observation_period, system_period, processing_activity_id
        ) VALUES (
            '40000000-0000-0000-0000-000000000001','registered','not_effective',
            daterange('2026-06-01',NULL,'[)'),
            tstzrange('2026-06-01 00:00+00',NULL,'[)'),
            tstzrange('2026-06-01 00:00+00',NULL,'[)'),
            '61000000-0000-0000-0000-000000000001'
        );
        RAISE EXCEPTION 'TEST FAILED: overlapping tri-temporal states were accepted';
    EXCEPTION WHEN exclusion_violation THEN
        NULL;
    END;
END $$;

-- Closed historical system versions may coexist with a later correction.
INSERT INTO whitelist.relationship_state_version(
    relationship_id, administrative_disposition_code, legal_effect_status_code,
    effective_period, observation_period, system_period, processing_activity_id
) VALUES
(
    '40000000-0000-0000-0000-000000000002','registered','not_effective',
    daterange('2020-01-01',NULL,'[)'),
    tstzrange('2020-01-01 00:00+00',NULL,'[)'),
    tstzrange('2026-01-02 00:00+00','2026-02-01 00:00+00','[)'),
    '61000000-0000-0000-0000-000000000001'
),
(
    '40000000-0000-0000-0000-000000000002','registered','effective',
    daterange('2020-01-01',NULL,'[)'),
    tstzrange('2020-01-01 00:00+00',NULL,'[)'),
    tstzrange('2026-02-01 00:00+00',NULL,'[)'),
    '61000000-0000-0000-0000-000000000001'
);

-- 4. Unknown effective time acts as an integrity wildcard ---------------------
INSERT INTO whitelist.relationship_state_version(
    relationship_id, administrative_disposition_code, legal_effect_status_code,
    effective_period, observation_period, system_period, processing_activity_id
) VALUES (
    '40000000-0000-0000-0000-000000000003','registered','unknown',NULL,
    tstzrange('2026-01-01 00:00+00',NULL,'[)'),
    tstzrange('2026-01-01 00:00+00',NULL,'[)'),
    '61000000-0000-0000-0000-000000000001'
);

DO $$
BEGIN
    BEGIN
        INSERT INTO whitelist.relationship_state_version(
            relationship_id, administrative_disposition_code, legal_effect_status_code,
            effective_period, observation_period, system_period, processing_activity_id
        ) VALUES (
            '40000000-0000-0000-0000-000000000003','registered','effective',
            daterange('2026-01-01',NULL,'[)'),
            tstzrange('2026-02-01 00:00+00',NULL,'[)'),
            tstzrange('2026-02-01 00:00+00',NULL,'[)'),
            '61000000-0000-0000-0000-000000000001'
        );
        RAISE EXCEPTION 'TEST FAILED: known effective period overlapped an unknown-period assertion';
    EXCEPTION WHEN exclusion_violation THEN
        NULL;
    END;
END $$;

-- 5. Current mart sees true unbounded rows ------------------------------------
DO $$
DECLARE c integer;
BEGIN
    SELECT count(*) INTO c
    FROM mart.current_relationship_state
    WHERE relationship_id='40000000-0000-0000-0000-000000000001';
    IF c <> 1 THEN
        RAISE EXCEPTION 'TEST FAILED: current relationship state view returned % rows, expected 1', c;
    END IF;

    SELECT count(*) INTO c
    FROM mart.current_entity_name
    WHERE legal_entity_id='20000000-0000-0000-0000-000000000001';
    IF c <> 1 THEN
        RAISE EXCEPTION 'TEST FAILED: current entity-name view returned % rows, expected 1', c;
    END IF;
END $$;

-- 6. Scheme versions cannot overlap for the same regime -----------------------
DO $$
DECLARE rid uuid;
BEGIN
    SELECT regime_id INTO rid FROM whitelist.white_list_regime WHERE regime_code='WL-REGIME-L190-2012';
    BEGIN
        INSERT INTO whitelist.sector_scheme_version(regime_id, version_code, effective_period)
        VALUES (rid,'TEST-OVERLAP',daterange('2030-01-01',NULL,'[)'));
        RAISE EXCEPTION 'TEST FAILED: overlapping taxonomy version was accepted';
    EXCEPTION WHEN exclusion_violation THEN
        NULL;
    END;
END $$;

-- 7. Membership period must be contained in its scheme version ----------------
DO $$
DECLARE sid uuid; cid uuid;
BEGIN
    SELECT sv.scheme_version_id INTO sid
    FROM whitelist.sector_scheme_version sv
    JOIN whitelist.white_list_regime r USING(regime_id)
    WHERE r.regime_code='WL-REGIME-L190-2012' AND sv.version_code='L190-2020';
    SELECT sector_concept_id INTO cid FROM whitelist.sector_concept WHERE concept_code='WL-ACT-ENVIRONMENTAL-SERVICES';
    BEGIN
        INSERT INTO whitelist.sector_scheme_membership(
            scheme_version_id, sector_concept_id, notation, legal_label, effective_period
        ) VALUES (sid,cid,'TEST-BAD-PERIOD','Bad period',daterange('2019-01-01','2020-01-01','[)'));
        RAISE EXCEPTION 'TEST FAILED: membership outside scheme period was accepted';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;
END $$;

-- 8. Relationship sector must match scheme membership concept -----------------
INSERT INTO whitelist.relationship_sector(
    relationship_sector_id, relationship_id, sector_concept_id
)
SELECT '51000000-0000-0000-0000-000000000001',
       '40000000-0000-0000-0000-000000000001', sector_concept_id
FROM whitelist.sector_concept WHERE concept_code='WL-ACT-ENVIRONMENTAL-SERVICES';

DO $$
DECLARE bad_membership uuid;
BEGIN
    SELECT sm.scheme_membership_id INTO bad_membership
    FROM whitelist.sector_scheme_membership sm
    JOIN whitelist.sector_scheme_version sv USING(scheme_version_id)
    JOIN whitelist.white_list_regime r USING(regime_id)
    WHERE r.regime_code='WL-REGIME-L190-2012' AND sv.version_code='L190-2020' AND sm.notation='I';
    BEGIN
        INSERT INTO whitelist.relationship_sector_state_version(
            relationship_sector_id, scheme_membership_id, sector_listing_status_code,
            observation_period, system_period, processing_activity_id
        ) VALUES (
            '51000000-0000-0000-0000-000000000001',bad_membership,'listed',
            tstzrange('2026-01-01',NULL,'[)'),tstzrange('2026-01-01',NULL,'[)'),
            '61000000-0000-0000-0000-000000000001'
        );
        RAISE EXCEPTION 'TEST FAILED: mismatched relationship-sector membership was accepted';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;
END $$;

-- Add a valid current sector and ensure the current mart can expose its label.
INSERT INTO whitelist.relationship_sector_state_version(
    relationship_sector_id, scheme_membership_id, sector_listing_status_code,
    observation_period, system_period, processing_activity_id
)
SELECT '51000000-0000-0000-0000-000000000001', sm.scheme_membership_id, 'listed',
       tstzrange('2026-01-01',NULL,'[)'), tstzrange('2026-01-01',NULL,'[)'),
       '61000000-0000-0000-0000-000000000001'
FROM whitelist.sector_scheme_membership sm
JOIN whitelist.sector_scheme_version sv USING(scheme_version_id)
JOIN whitelist.white_list_regime r USING(regime_id)
WHERE r.regime_code='WL-REGIME-L190-2012' AND sv.version_code='L190-2020' AND sm.notation='X';

DO $$
DECLARE lbl text;
BEGIN
    SELECT sector_label INTO lbl
    FROM mart.current_whitelist
    WHERE relationship_id='40000000-0000-0000-0000-000000000001'
      AND sector_concept_code='WL-ACT-ENVIRONMENTAL-SERVICES';
    IF lbl IS NULL OR btrim(lbl)='' THEN
        RAISE EXCEPTION 'TEST FAILED: current whitelist did not expose canonical sector label';
    END IF;
END $$;

-- 9. Parser versions can coexist for the same immutable content ---------------
INSERT INTO source.content_object(
    content_object_id, sha256, mime_type, file_size, storage_uri
) VALUES (
    '60000000-0000-0000-0000-000000000001',repeat('a',64),'application/pdf',100,'sha256://aa/test.pdf'
);

INSERT INTO source.parse_run(parse_run_id, content_object_id, processing_activity_id, status_code)
VALUES
('62000000-0000-0000-0000-000000000001','60000000-0000-0000-0000-000000000001','61000000-0000-0000-0000-000000000002','succeeded'),
('62000000-0000-0000-0000-000000000002','60000000-0000-0000-0000-000000000001','61000000-0000-0000-0000-000000000003','succeeded');

INSERT INTO source.source_schema(source_schema_id, schema_name)
VALUES
('63000000-0000-0000-0000-000000000001','Test schema A'),
('63000000-0000-0000-0000-000000000002','Test schema B');

INSERT INTO source.source_schema_version(schema_version_id, source_schema_id, structural_fingerprint, first_observed_at)
VALUES
('64000000-0000-0000-0000-000000000001','63000000-0000-0000-0000-000000000001','test-a-v1','2026-01-01'),
('64000000-0000-0000-0000-000000000002','63000000-0000-0000-0000-000000000002','test-b-v1','2026-01-01');

INSERT INTO source.source_field_definition(
    field_definition_id, schema_version_id, source_label, normalised_source_label, ordinal_position
) VALUES
('64100000-0000-0000-0000-000000000001','64000000-0000-0000-0000-000000000001','Ragione sociale','ragione sociale',1),
('64100000-0000-0000-0000-000000000002','64000000-0000-0000-0000-000000000002','Other field','other field',1);

INSERT INTO source.parsed_record(parsed_record_id, parse_run_id, schema_version_id, record_locator, record_hash)
VALUES
('65000000-0000-0000-0000-000000000001','62000000-0000-0000-0000-000000000001','64000000-0000-0000-0000-000000000001','table1/row1','hash-v1'),
('65000000-0000-0000-0000-000000000002','62000000-0000-0000-0000-000000000002','64000000-0000-0000-0000-000000000001','table1/row1','hash-v2');

DO $$
BEGIN
    BEGIN
        INSERT INTO source.parsed_record(parse_run_id, schema_version_id, record_locator, record_hash)
        VALUES ('62000000-0000-0000-0000-000000000001','64000000-0000-0000-0000-000000000001','table1/row1','duplicate');
        RAISE EXCEPTION 'TEST FAILED: duplicate locator within one parse run was accepted';
    EXCEPTION WHEN unique_violation THEN
        NULL;
    END;
END $$;

-- 10. Source field values cannot mix schema versions ---------------------------
DO $$
BEGIN
    BEGIN
        INSERT INTO source.source_field_value(
            parsed_record_id, field_definition_id, schema_version_id, raw_value
        ) VALUES (
            '65000000-0000-0000-0000-000000000001',
            '64100000-0000-0000-0000-000000000002',
            '64000000-0000-0000-0000-000000000001','bad'
        );
        RAISE EXCEPTION 'TEST FAILED: source field value mixed incompatible schema versions';
    EXCEPTION WHEN foreign_key_violation THEN
        NULL;
    END;
END $$;

INSERT INTO source.source_field_value(
    source_field_value_id, parsed_record_id, field_definition_id, schema_version_id, raw_value
) VALUES (
    '64200000-0000-0000-0000-000000000001','65000000-0000-0000-0000-000000000001',
    '64100000-0000-0000-0000-000000000001','64000000-0000-0000-0000-000000000001','Impresa Test S.r.l.'
);

-- 11. Raw field values and content byte identity are immutable -----------------
DO $$
BEGIN
    BEGIN
        UPDATE source.source_field_value
           SET raw_value='mutated'
         WHERE source_field_value_id='64200000-0000-0000-0000-000000000001';
        RAISE EXCEPTION 'TEST FAILED: immutable source field value was updated';
    EXCEPTION WHEN SQLSTATE '55000' THEN
        NULL;
    END;
    BEGIN
        UPDATE source.content_object
           SET sha256=repeat('b',64)
         WHERE content_object_id='60000000-0000-0000-0000-000000000001';
        RAISE EXCEPTION 'TEST FAILED: immutable content byte identity was updated';
    EXCEPTION WHEN SQLSTATE '55000' THEN
        NULL;
    END;
END $$;

-- 12. Only one accepted entity resolution may apply at a system time -----------
INSERT INTO source.entity_mention(entity_mention_id, parsed_record_id, mention_role_code)
VALUES
('66000000-0000-0000-0000-000000000001','65000000-0000-0000-0000-000000000001','listed_entity'),
('66000000-0000-0000-0000-000000000002','65000000-0000-0000-0000-000000000002','listed_entity');

INSERT INTO provenance.entity_resolution(
    entity_mention_id, legal_entity_id, resolution_method_code,
    confidence_score, decision_status_code, processing_activity_id, system_period
) VALUES (
    '66000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001',
    'exact_identifier',1.0,'accepted','61000000-0000-0000-0000-000000000004',
    tstzrange('2026-02-01 00:00+00',NULL,'[)')
);

DO $$
BEGIN
    BEGIN
        INSERT INTO provenance.entity_resolution(
            entity_mention_id, legal_entity_id, resolution_method_code,
            confidence_score, decision_status_code, processing_activity_id, system_period
        ) VALUES (
            '66000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000002',
            'manual',1.0,'accepted','61000000-0000-0000-0000-000000000004',
            tstzrange('2026-02-02 00:00+00',NULL,'[)')
        );
        RAISE EXCEPTION 'TEST FAILED: overlapping accepted entity resolution was accepted';
    EXCEPTION WHEN unique_violation OR exclusion_violation THEN
        NULL;
    END;
END $$;

-- 13. Procedure resolution has the same system-time integrity ------------------
INSERT INTO whitelist.white_list_procedure(procedure_id, relationship_id)
VALUES ('67000000-0000-0000-0000-000000000001','40000000-0000-0000-0000-000000000001');

-- A procedure mention cannot attach an entity mention from another source record.
DO $$
BEGIN
    BEGIN
        INSERT INTO source.procedure_mention(
            procedure_mention_id, parsed_record_id, entity_mention_id, mention_type_code
        ) VALUES (
            '68000000-0000-0000-0000-000000000099','65000000-0000-0000-0000-000000000001',
            '66000000-0000-0000-0000-000000000002','renewal'
        );
        RAISE EXCEPTION 'TEST FAILED: procedure mention crossed source-record boundaries';
    EXCEPTION WHEN foreign_key_violation THEN
        NULL;
    END;
END $$;

INSERT INTO source.procedure_mention(procedure_mention_id, parsed_record_id, entity_mention_id, mention_type_code)
VALUES (
    '68000000-0000-0000-0000-000000000001','65000000-0000-0000-0000-000000000001',
    '66000000-0000-0000-0000-000000000001','renewal'
);

INSERT INTO provenance.procedure_resolution(
    procedure_mention_id, procedure_id, resolution_method_code, confidence_score,
    decision_status_code, processing_activity_id, system_period
) VALUES (
    '68000000-0000-0000-0000-000000000001','67000000-0000-0000-0000-000000000001',
    'manual',1.0,'accepted','61000000-0000-0000-0000-000000000005',
    tstzrange('2026-02-01 00:00+00',NULL,'[)')
);

DO $$
BEGIN
    BEGIN
        INSERT INTO provenance.procedure_resolution(
            procedure_mention_id, procedure_id, resolution_method_code, confidence_score,
            decision_status_code, processing_activity_id, system_period
        ) VALUES (
            '68000000-0000-0000-0000-000000000001','67000000-0000-0000-0000-000000000001',
            'manual',1.0,'accepted','61000000-0000-0000-0000-000000000005',
            tstzrange('2026-02-02 00:00+00',NULL,'[)')
        );
        RAISE EXCEPTION 'TEST FAILED: overlapping accepted procedure resolution was accepted';
    EXCEPTION WHEN unique_violation OR exclusion_violation THEN
        NULL;
    END;
END $$;

-- 14. Sector-state and procedure-version tri-temporal constraints apply too ----
DO $$
BEGIN
    BEGIN
        INSERT INTO whitelist.relationship_sector_state_version(
            relationship_sector_id, scheme_membership_id, sector_listing_status_code,
            observation_period, system_period, processing_activity_id
        )
        SELECT '51000000-0000-0000-0000-000000000001', sm.scheme_membership_id, 'removed_explicitly',
               tstzrange('2026-02-01',NULL,'[)'), tstzrange('2026-02-01',NULL,'[)'),
               '61000000-0000-0000-0000-000000000001'
        FROM whitelist.sector_scheme_membership sm
        JOIN whitelist.sector_scheme_version sv USING(scheme_version_id)
        JOIN whitelist.white_list_regime r USING(regime_id)
        WHERE r.regime_code='WL-REGIME-L190-2012' AND sv.version_code='L190-2020' AND sm.notation='X';
        RAISE EXCEPTION 'TEST FAILED: overlapping relationship-sector state was accepted';
    EXCEPTION WHEN exclusion_violation THEN
        NULL;
    END;
END $$;

INSERT INTO whitelist.procedure_version(
    procedure_version_id, procedure_id, procedure_type_code, application_date,
    procedure_status_code, effective_period, observation_period, system_period, processing_activity_id
) VALUES (
    '67100000-0000-0000-0000-000000000001','67000000-0000-0000-0000-000000000001','renewal','2026-01-15',
    'pending',NULL,tstzrange('2026-01-15',NULL,'[)'),tstzrange('2026-01-15',NULL,'[)'),
    '61000000-0000-0000-0000-000000000001'
);

DO $$
BEGIN
    BEGIN
        INSERT INTO whitelist.procedure_version(
            procedure_id, procedure_type_code, application_date, procedure_status_code,
            effective_period, observation_period, system_period, processing_activity_id
        ) VALUES (
            '67000000-0000-0000-0000-000000000001','renewal','2026-01-15','completed',
            daterange('2026-01-15',NULL,'[)'),tstzrange('2026-02-01',NULL,'[)'),tstzrange('2026-02-01',NULL,'[)'),
            '61000000-0000-0000-0000-000000000001'
        );
        RAISE EXCEPTION 'TEST FAILED: overlapping procedure version was accepted';
    EXCEPTION WHEN exclusion_violation THEN
        NULL;
    END;
END $$;

-- 15. Edition sector scope cannot import a taxonomy from another regime -------
INSERT INTO whitelist.white_list_regime(
    regime_id, regime_code, preferred_label, effective_period
) VALUES (
    '70000000-0000-0000-0000-000000000001','TEST-OTHER-REGIME','Other test regime',daterange('2020-01-01',NULL,'[)')
);
INSERT INTO whitelist.sector_scheme_version(
    scheme_version_id, regime_id, version_code, effective_period
) VALUES (
    '71000000-0000-0000-0000-000000000001','70000000-0000-0000-0000-000000000001','OTHER-V1',daterange('2020-01-01',NULL,'[)')
);
INSERT INTO whitelist.sector_scheme_membership(
    scheme_membership_id, scheme_version_id, sector_concept_id, notation, legal_label, effective_period
)
SELECT '72000000-0000-0000-0000-000000000001','71000000-0000-0000-0000-000000000001',sector_concept_id,
       'Z','Other environmental notation',daterange('2020-01-01',NULL,'[)')
FROM whitelist.sector_concept WHERE concept_code='WL-ACT-ENVIRONMENTAL-SERVICES';

INSERT INTO source.source_series(
    series_id, publisher_authority_id, register_id, series_name, series_type_code
) VALUES (
    '73000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001',
    '30000000-0000-0000-0000-000000000001','Test ordinary list','list'
);
INSERT INTO source.source_edition(
    edition_id, series_id, reference_period, edition_identity_status_code,
    population_scope_completeness_code, sector_scope_completeness_code
) VALUES (
    '74000000-0000-0000-0000-000000000001','73000000-0000-0000-0000-000000000001',
    daterange('2026-01-01','2026-01-02','[)'),'explicit','all','partial'
);
DO $$
BEGIN
    BEGIN
        INSERT INTO source.edition_sector_scope(edition_id, scheme_membership_id)
        VALUES ('74000000-0000-0000-0000-000000000001','72000000-0000-0000-0000-000000000001');
        RAISE EXCEPTION 'TEST FAILED: edition accepted a sector taxonomy from another regime';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;
END $$;

-- 16. Derived events can retain concrete canonical inputs ----------------------
INSERT INTO derived.derived_event(
    derived_event_id, relationship_id, event_type_code, event_class_code,
    time_precision_code, derivation_rule, derivation_version, processing_activity_id
) VALUES (
    '69000000-0000-0000-0000-000000000001','40000000-0000-0000-0000-000000000001',
    'first_observed','derived','unknown','test-rule','1.0','61000000-0000-0000-0000-000000000006'
);
INSERT INTO derived.derived_event_relationship_state_input(derived_event_id, relationship_state_version_id)
VALUES ('69000000-0000-0000-0000-000000000001','50000000-0000-0000-0000-000000000001');

ROLLBACK;
\echo 'All database integrity tests passed.'
