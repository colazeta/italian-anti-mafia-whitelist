INSERT INTO registry.entity_class(code,label) VALUES
('organisation','Organisation'),
('self_employed_person','Self-employed person'),
('other','Other'),
('unknown','Unknown') ON CONFLICT DO NOTHING;

INSERT INTO registry.name_type(code,label) VALUES
('legal_name','Legal name'),('trade_name','Trade name'),('historical_name','Historical name'),('other','Other') ON CONFLICT DO NOTHING;

INSERT INTO registry.verification_status(code,label) VALUES
('verified','Verified'),('source_asserted','Source asserted'),('unresolved','Unresolved'),('invalid','Invalid'),('unknown','Unknown') ON CONFLICT DO NOTHING;

INSERT INTO registry.establishment_type(code,label) VALUES
('registered_office','Registered office'),('secondary_establishment','Secondary establishment'),('stable_representative_establishment','Stable representative establishment'),('other','Other') ON CONFLICT DO NOTHING;

INSERT INTO registry.competence_relevance(code,label) VALUES
('determines_competence','Determines authority competence'),('relevant','Relevant'),('not_relevant','Not relevant'),('unknown','Unknown') ON CONFLICT DO NOTHING;

INSERT INTO registry.authority_type(code,label) VALUES
('prefecture_utg','Prefecture - Territorial Government Office'),('government_commissioner','Government Commissioner'),('other','Other') ON CONFLICT DO NOTHING;

INSERT INTO registry.jurisdiction_type(code,label) VALUES
('province','Province'),('metropolitan_city','Metropolitan city'),('autonomous_province','Autonomous province'),('region','Region'),('national','National'),('other','Other') ON CONFLICT DO NOTHING;

INSERT INTO registry.sector_label_type(code,label) VALUES
('preferred','Preferred'),('alternative','Alternative'),('historical','Historical'),('source_equivalent','Source equivalent') ON CONFLICT DO NOTHING;

INSERT INTO registry.administrative_disposition(code,label) VALUES
('registered','Registered'),('removed','Removed'),('rejected','Rejected'),('unknown','Unknown') ON CONFLICT DO NOTHING;

INSERT INTO registry.legal_effect_status(code,label) VALUES
('effective','Effective'),('not_effective','Not effective'),('unknown','Unknown') ON CONFLICT DO NOTHING;

INSERT INTO registry.sector_listing_status(code,label) VALUES
('listed','Listed'),('removed_explicitly','Explicitly removed'),('unknown','Unknown') ON CONFLICT DO NOTHING;

INSERT INTO registry.procedure_type(code,label) VALUES
('initial_registration','Initial registration'),('renewal','Renewal'),('update','Update'),('variation','Variation'),('other','Other'),('unknown','Unknown') ON CONFLICT DO NOTHING;

INSERT INTO registry.procedure_status(code,label) VALUES
('submitted','Submitted'),('pending','Pending'),('under_investigation','Under investigation'),('completed','Completed'),('withdrawn','Withdrawn'),('unknown','Unknown') ON CONFLICT DO NOTHING;

INSERT INTO registry.procedure_outcome(code,label) VALUES
('approved','Approved'),('rejected','Rejected'),('cancelled','Cancelled'),('unknown','Unknown') ON CONFLICT DO NOTHING;

INSERT INTO registry.source_series_type(code,label) VALUES
('list','Recurring list'),('information_page','Information page'),('register_interface','Register/interface'),('other','Other') ON CONFLICT DO NOTHING;

INSERT INTO registry.edition_identity_status(code,label) VALUES
('explicit','Explicit'),('inferred','Inferred'),('unknown','Unknown') ON CONFLICT DO NOTHING;

INSERT INTO registry.scope_completeness(code,label) VALUES
('all','Complete/all'),('partial','Partial'),('unknown','Unknown') ON CONFLICT DO NOTHING;

INSERT INTO registry.population_type(code,label) VALUES
('listed','Listed entities'),('applicant','Applicants'),('removed','Removed entities'),('other','Other') ON CONFLICT DO NOTHING;

INSERT INTO registry.resource_type(code,label) VALUES
('html','HTML page'),('pdf','PDF'),('xlsx','XLSX'),('xls','XLS'),('docx','DOCX'),('csv','CSV'),('zip','ZIP'),('api','API endpoint'),('other','Other') ON CONFLICT DO NOTHING;

INSERT INTO registry.source_origin_type(code,label) VALUES
('official_current','Official current source'),('official_historical','Official historical source'),('official_archived_copy','Official archived copy'),('web_archive_capture','Web archive capture'),('secondary_mirror','Secondary mirror'),('other','Other') ON CONFLICT DO NOTHING;

INSERT INTO registry.authority_rank(code,label) VALUES
('primary_official','Primary official evidence'),('official_archive','Official archive evidence'),('archive_proxy','Archive proxy'),('secondary','Secondary evidence'),('unknown','Unknown') ON CONFLICT DO NOTHING;

INSERT INTO registry.capture_edition_relation_type(code,label) VALUES
('is_representation_of','Is representation of'),('contains','Contains'),('lists','Lists'),('supports_identification_of','Supports identification of') ON CONFLICT DO NOTHING;

INSERT INTO registry.attribution_status(code,label) VALUES
('explicit','Explicit'),('inferred','Inferred') ON CONFLICT DO NOTHING;

INSERT INTO registry.parse_run_status(code,label) VALUES
('running','Running'),('succeeded','Succeeded'),('failed','Failed'),('partial','Partial') ON CONFLICT DO NOTHING;

INSERT INTO registry.mention_role(code,label) VALUES
('listed_entity','Listed entity'),('applicant','Applicant'),('removed_entity','Removed entity'),('unknown','Unknown') ON CONFLICT DO NOTHING;

INSERT INTO registry.mention_type(code,label) VALUES
('registration','Registration'),('renewal','Renewal'),('update','Update'),('variation','Variation'),('unknown','Unknown') ON CONFLICT DO NOTHING;

INSERT INTO registry.resolution_method(code,label) VALUES
('exact_identifier','Exact identifier'),('multi_identifier','Multiple identifiers'),('name_address','Name and address'),('probabilistic','Probabilistic'),('manual','Manual'),('unknown','Unknown') ON CONFLICT DO NOTHING;

INSERT INTO registry.decision_status(code,label) VALUES
('accepted','Accepted'),('rejected','Rejected'),('candidate','Candidate'),('superseded','Superseded') ON CONFLICT DO NOTHING;

INSERT INTO registry.activity_type(code,label) VALUES
('fetch','Fetch'),('parse','Parse'),('schema_map','Schema map'),('normalise','Normalise'),('entity_resolve','Entity resolution'),('procedure_resolve','Procedure resolution'),('derive_event','Derive event'),('manual_review','Manual review') ON CONFLICT DO NOTHING;

INSERT INTO registry.evidence_type(code,label) VALUES
('field_value','Source field value'),('parsed_record','Parsed record'),('source_edition','Source edition'),('source_capture','Source capture') ON CONFLICT DO NOTHING;

INSERT INTO registry.evidence_role(code,label) VALUES
('supports','Supports'),('contradicts','Contradicts'),('derives_from','Derives from') ON CONFLICT DO NOTHING;

INSERT INTO registry.event_class(code,label) VALUES
('administrative','Administrative'),('observational','Observational'),('derived','Derived') ON CONFLICT DO NOTHING;

INSERT INTO registry.event_type(code,label) VALUES
('first_observed','First observed'),('disappeared_from_source','Disappeared from source'),('sector_added','Sector added'),('sector_removed','Sector removed'),('renewal_started','Renewal started'),('explicit_removal','Explicit removal'),('source_correction','Source correction') ON CONFLICT DO NOTHING;

INSERT INTO registry.time_precision(code,label) VALUES
('instant','Instant'),('day','Day'),('interval','Interval'),('unknown','Unknown') ON CONFLICT DO NOTHING;

INSERT INTO registry.legal_review_status(code,label) VALUES
('not_reviewed','Not reviewed'),('reviewed','Reviewed'),('approved','Approved'),('restricted','Restricted') ON CONFLICT DO NOTHING;

INSERT INTO registry.review_status(code,label) VALUES
('open','Open'),('resolved','Resolved'),('accepted','Accepted'),('rejected','Rejected') ON CONFLICT DO NOTHING;

INSERT INTO registry.identifier_uniqueness_scope(code,label) VALUES
('global','Global'),('national','National'),('jurisdictional','Jurisdictional'),('issuer','Issuer-specific'),('none','No uniqueness assumption'),('unknown','Unknown') ON CONFLICT DO NOTHING;

INSERT INTO core.identifier_scheme(scheme_code, scheme_uri, uniqueness_scope_code, description) VALUES
('IT_CF', NULL, 'national', 'Italian codice fiscale'),
('IT_VAT', NULL, 'national', 'Italian VAT number / partita IVA'),
('LEI', 'https://www.gleif.org/', 'global', 'Legal Entity Identifier'),
('FOREIGN_REGISTER_ID', NULL, 'jurisdictional', 'Foreign business-register identifier'),
('UNRESOLVED_CF_OR_VAT', NULL, 'none', 'Identifier published in a composite CF/Partita IVA field whose precise scheme cannot yet be established')
ON CONFLICT (scheme_code) DO NOTHING;

INSERT INTO mapping.divergence_type(divergence_type_code, definition) VALUES
('LABEL','Different source labels for the same semantic concept'),
('FORMAT','Different source formatting for the same semantic concept'),
('COMPOSITE','Multiple semantic concepts encoded in one source field'),
('CARDINALITY','Different one-to-many representation'),
('GRANULARITY','Different information granularity'),
('SEMANTIC','Potentially different semantic meaning'),
('STATUS','Different status models'),
('DOCUMENT_MODEL','Different document/table organisation'),
('MISSINGNESS','Different or ambiguous representation of missingness'),
('TEMPORAL','Different temporal meaning or precision'),
('IDENTIFIER','Different identifier semantics'),
('VOCABULARY','Different controlled vocabulary or source wording')
ON CONFLICT DO NOTHING;
