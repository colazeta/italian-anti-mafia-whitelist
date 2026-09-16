# Milano White List — operational source check (16 September 2026)

## Scope and conclusion

This check resolves the previously open Milano source-population question using positive current official evidence. The Prefettura di Milano operates a dedicated White List application at `whitelist.prefmi.it` in addition to the Ministry landing page. On 16 September 2026 the application exposed a current combined public table at `https://whitelist.prefmi.it/elenco/elenco.php` containing registered-company, renewal/update and first-time applicant observations. The applicant population is therefore treated as positively published; this conclusion is not inferred from search failure or from the existence of the separate application-submission route.

The approved candidate source is the combined current table, not a union with the registered-only view. The combined surface contains the same non-pending company identity set observed in the sibling registered-company view and additionally exposes explicit applicant rows. Using both would therefore duplicate observations and could create conflicting current-status presentations.

## Official surfaces verified

- Ministry landing page: `https://prefettura.interno.gov.it/it/prefetture/milano/evidenza/white-list`.
- Dedicated application entry point: `https://whitelist.prefmi.it/elenco/inizio.php`.
- Combined operational table: `https://whitelist.prefmi.it/elenco/elenco.php`.
- Registered-company sibling view: `https://whitelist.prefmi.it/elenco/elenco_iscritte.php`.

The Ministry page expressly distinguishes the registered-company consultation link and the registration-request route and instructs contracting authorities, for firms not yet registered, to ascertain through the Prefecture White Lists that registration or renewal has been requested. The dedicated application entry point identifies both an `ELENCO IMPRESE RICHIEDENTI ISCRIZIONE NELLA WHITE LIST PROVINCIALE` and an `ELENCO IMPRESE ISCRITTE NELLA WHITE LIST PROVINCIALE`. Most importantly, the combined operational table itself currently publishes source-explicit `RICHIESTA ISCRIZIONE (dd/mm/yyyy)` rows, including September 2026 requests.

## Byte identity and current-source boundary

Two independent no-cache GETs of the combined table on 16 September 2026 were byte-identical:

- bytes: **970,875**;
- SHA-256: **`350e995ac06fc9525c1bd21cc2e2ad8b69224e4dd603e530a65553c21f44b044`**.

Two independent no-cache GETs of the registered-company sibling view were also byte-identical:

- bytes: **559,278**;
- SHA-256: **`81226e37aa744a8907f4de70121e46362ceb0177259e3de076f2eb15ebaafb7e`**.

The combined source is a mutable current web application rather than a dated immutable attachment. Accordingly, **2026-09-16 is the capture/verification reference date only**. It is not treated as an inferred application, decision, registration, expiry or legal-effect date for any company. Publication is byte-pinned to the validated capture and fails closed on source drift.

## Parser boundary

The source is HTML with ten statutory White List section tables. Applicant and update rows use `colspan="2"` in the date area, so the parser expands source colspan geometry before interpreting cells; otherwise note and date fields would be shifted.

The validated capture contains:

- **10** section tables;
- **4,214** physical sector-membership rows;
- **2,614** conservative logical company observations after grouping only repeated sector memberships with the same normalised company identity, status/date semantics and note;
- **2,614/2,614** strict source identifiers, with one logical observation per identifier;
- **2,614/2,614** observations with at least one source-explicit statutory activity section.

Logical current status counts are:

- **940** `listed` observations with source-explicit listing and expiry dates;
- **516** `renewal_update_in_progress` observations from the source-explicit label `IN AGGIORNAMENTO`;
- **1,158** `pending` observations from source-explicit `RICHIESTA ISCRIZIONE (dd/mm/yyyy)` labels.

All 1,158 pending observations have an explicit application date. All 940 listed observations have both listing and expiry dates. No date is manufactured for update rows. The latest positively observed applicant date in the validated capture is **15 September 2026**.

Repeated section membership is retained as requested-activity provenance rather than published as duplicate company observations. Record locators use the source-published identifier and the capture reference date rather than mutable HTML row position.

## Source-faithful treatment

No legal status is inferred beyond the source-explicit table semantics. In particular:

- `RICHIESTA ISCRIZIONE (...)` is mapped only to `pending`;
- `IN AGGIORNAMENTO` is mapped only to `renewal_update_in_progress`;
- rows with valid listing and expiry dates are mapped to `listed`;
- any previously unseen status/date pattern fails closed;
- company names, registered offices and identifiers are not repaired from external information;
- repeated sector memberships are grouped only under the reviewed identity/status/date rule.

One logical observation, **COMOTER SRL**, carries the source note `Misura di prevenzione collaborativa ex art. 94 bis D.lgs.159/2011 in data 18/04/2024, per la durata di un anno`. It is retained strictly as source provenance and is not used to overwrite the table's explicit current status.

## Validation and publication gate

The temporary source-validation gate on the expansion branch runs the Milano semantic tests and the full repository test suite, captures the combined and registered sibling surfaces twice, requires byte identity across the paired GETs, parses the current combined source through the production parser and asserts the complete denominator/status/date/identifier/activity boundary above. It also ties the current Ministry-page and application-entry-point evidence to the same validation run.

The parser is fail-closed on table count, section headings, expanded header geometry, row width, identifier syntax, unreviewed status/date patterns, logical-record denominator, status counts, identifier coverage and note denominator. National publication remains a separate transaction and must prove the actual national registry denominators before `canonical_integration_validated` can be promoted.

`durable_evidence_verified` must remain false unless the project independently establishes the governed durable-evidence requirement; temporary workflow captures do not satisfy that requirement.
