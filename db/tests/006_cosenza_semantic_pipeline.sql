\set ON_ERROR_STOP on

DO $$
DECLARE
    n integer;
BEGIN
    SELECT count(*) INTO n FROM semantic.projection_run WHERE status_code='succeeded';
    IF n <> 2 THEN RAISE EXCEPTION 'Expected 2 semantic projection runs, got %', n; END IF;

    SELECT count(*) INTO n FROM semantic.entity_observation;
    IF n <> 2661 THEN RAISE EXCEPTION 'Expected 2661 entity observations, got %', n; END IF;

    SELECT count(*) INTO n FROM semantic.identifier_observation;
    IF n <> 3258 THEN RAISE EXCEPTION 'Expected 3258 identifier observations, got %', n; END IF;

    SELECT count(*) INTO n FROM semantic.establishment_observation;
    IF n <> 2663 THEN RAISE EXCEPTION 'Expected 2663 establishment observations, got %', n; END IF;

    SELECT count(*) INTO n FROM semantic.relationship_observation;
    IF n <> 2661 THEN RAISE EXCEPTION 'Expected 2661 relationship observations, got %', n; END IF;

    SELECT count(*) INTO n FROM semantic.procedure_observation;
    IF n <> 3226 THEN RAISE EXCEPTION 'Expected 3226 procedure observations, got %', n; END IF;

    SELECT count(*) INTO n FROM semantic.procedure_sector_observation;
    IF n <> 8710 THEN RAISE EXCEPTION 'Expected 8710 procedure-sector observations, got %', n; END IF;

    SELECT count(*) INTO n FROM semantic.procedure_sector_observation WHERE mapping_status_code <> 'mapped';
    IF n <> 0 THEN RAISE EXCEPTION 'Expected zero unmapped requested activities, got %', n; END IF;

    -- Semantic issues remain part of the data, not parser failures. The current
    -- frozen pair contains 569 parenthesized application dates, two unexpected
    -- identifier shapes and 29 rows where a published listing date predates a
    -- later/current application date and therefore cannot be promoted as that
    -- procedure's decision date.
    SELECT count(*) INTO n FROM semantic.projection_issue;
    IF n <> 600 THEN RAISE EXCEPTION 'Expected 600 projection QA issues, got %', n; END IF;

    SELECT count(*) INTO n FROM semantic.projection_issue WHERE issue_code='PARENTHESIZED_APPLICATION_DATE';
    IF n <> 569 THEN RAISE EXCEPTION 'Expected 569 parenthesized application-date issues, got %', n; END IF;

    SELECT count(*) INTO n FROM semantic.projection_issue WHERE issue_code='IDENTIFIER_UNEXPECTED_SHAPE';
    IF n <> 2 THEN RAISE EXCEPTION 'Expected 2 unexpected identifier-shape issues, got %', n; END IF;

    SELECT count(*) INTO n FROM semantic.projection_issue WHERE issue_code='LISTING_DATE_PRECEDES_APPLICATION_DATE';
    IF n <> 29 THEN RAISE EXCEPTION 'Expected 29 chronology guard issues, got %', n; END IF;

    SELECT count(*) INTO n FROM semantic.procedure_observation
     WHERE observed_decision_date IS NOT NULL AND observed_decision_date < application_date;
    IF n <> 0 THEN RAISE EXCEPTION 'Found % procedure observations with decision date before application date', n; END IF;

    SELECT count(*) INTO n FROM mapping.field_mapping WHERE mapping_version='prefecture-combined-whitelist-v1' AND effective_to IS NULL;
    IF n <> 14 THEN RAISE EXCEPTION 'Expected 14 active field mappings for selected parser family, got %', n; END IF;

    SELECT count(*) INTO n FROM semantic.canonicalisation_run WHERE status_code='succeeded';
    IF n <> 1 THEN RAISE EXCEPTION 'Expected one canonicalisation run, got %', n; END IF;

    SELECT count(*) INTO n FROM semantic.entity_projection_resolution WHERE decision_status_code='accepted';
    IF n <> 2655 THEN RAISE EXCEPTION 'Expected 2655 accepted entity observation resolutions, got %', n; END IF;

    SELECT count(*) INTO n FROM semantic.entity_projection_resolution WHERE decision_status_code='requires_resolution';
    IF n <> 6 THEN RAISE EXCEPTION 'Expected 6 deliberately unresolved entity observations, got %', n; END IF;

    SELECT count(*) INTO n FROM core.legal_entity;
    IF n <> 1343 THEN RAISE EXCEPTION 'Expected 1343 guarded canonical legal entities, got %', n; END IF;

    SELECT count(*) INTO n FROM provenance.entity_resolution WHERE decision_status_code='accepted';
    IF n <> 2655 THEN RAISE EXCEPTION 'Expected 2655 accepted mention-to-entity resolutions, got %', n; END IF;

    SELECT count(*) INTO n FROM core.entity_name;
    IF n <> 2655 THEN RAISE EXCEPTION 'Expected 2655 source-supported canonical name observations, got %', n; END IF;

    SELECT count(*) INTO n FROM core.entity_identifier;
    IF n <> 3250 THEN RAISE EXCEPTION 'Expected 3250 source-supported canonical identifier observations, got %', n; END IF;

    SELECT count(*) INTO n FROM core.address;
    IF n <> 1298 THEN RAISE EXCEPTION 'Expected 1298 distinct source-address objects, got %', n; END IF;

    SELECT count(*) INTO n FROM core.establishment;
    IF n <> 2657 THEN RAISE EXCEPTION 'Expected 2657 source-supported establishment observations, got %', n; END IF;

    SELECT count(*) INTO n FROM whitelist.white_list_relationship;
    IF n <> 1343 THEN RAISE EXCEPTION 'Expected 1343 entity-register relationships, got %', n; END IF;

    SELECT count(*) INTO n FROM whitelist.relationship_state_version;
    IF n <> 2655 THEN RAISE EXCEPTION 'Expected 2655 relationship-state observations, got %', n; END IF;

    -- Requested activities belong to procedures. The current combined source does
    -- not prove that those sectors are relationship/listed sectors.
    SELECT count(*) INTO n FROM whitelist.relationship_sector;
    IF n <> 0 THEN RAISE EXCEPTION 'Requested activities leaked into relationship_sector (% rows)', n; END IF;

    SELECT count(*) INTO n FROM whitelist.white_list_procedure;
    IF n <> 1368 THEN RAISE EXCEPTION 'Expected 1368 canonical procedure identities, got %', n; END IF;

    SELECT count(*) INTO n FROM whitelist.procedure_version;
    IF n <> 2651 THEN RAISE EXCEPTION 'Expected 2651 eligible procedure observations, got %', n; END IF;

    SELECT count(*) INTO n FROM whitelist.procedure_version
     WHERE decision_date IS NOT NULL AND decision_date < application_date;
    IF n <> 0 THEN RAISE EXCEPTION 'Found % canonical procedure versions with decision date before application date', n; END IF;

    SELECT count(*) INTO n FROM whitelist.procedure_sector;
    IF n <> 3614 THEN RAISE EXCEPTION 'Expected 3614 unique procedure-sector links, got %', n; END IF;

    SELECT count(*) INTO n FROM provenance.procedure_resolution WHERE decision_status_code='accepted';
    IF n <> 2651 THEN RAISE EXCEPTION 'Expected 2651 accepted procedure resolutions, got %', n; END IF;

    SELECT count(*) INTO n FROM provenance.procedure_resolution
     WHERE decision_status_code='accepted' AND resolution_method_code <> 'deterministic_source_fields';
    IF n <> 0 THEN RAISE EXCEPTION 'Found % procedure resolutions using the wrong resolution-method semantics', n; END IF;

    -- Three strong identifier values are deliberately ambiguous across distinct
    -- names; none may silently resolve all six affected observations.
    SELECT count(*) INTO n
      FROM semantic.entity_projection_resolution epr
      JOIN semantic.entity_observation eo USING(entity_observation_id)
      JOIN semantic.identifier_observation io USING(entity_observation_id)
     WHERE io.normalised_value IN ('03579010780','03865410785','03849810787')
       AND epr.decision_status_code='accepted';
    IF n <> 0 THEN RAISE EXCEPTION 'Ambiguous identifier observations were incorrectly canonicalised (% accepted)', n; END IF;
END;
$$;
