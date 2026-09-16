# Milano White List — operational source check (16 September 2026)

## Scope and conclusion

This check resolves the Milano source-population question using positive current official evidence. The Prefettura di Milano operates a dedicated White List application at `whitelist.prefmi.it` in addition to the Ministry landing page. The application exposes a combined public table at `https://whitelist.prefmi.it/elenco/elenco.php` containing registered-company, renewal/update and first-time applicant observations. The applicant population is therefore treated as positively published; this conclusion is not inferred from search failure or from the existence of an application-submission route.

The publication source is the combined current table, not a union with the registered-only sibling. The sibling contains exactly the same current non-pending company identity set and is retained as corroborating source evidence only. Co-ingestion would duplicate observations and could create conflicting note/status presentations.

## Official surfaces verified

- Ministry landing page: `https://prefettura.interno.gov.it/it/prefetture/milano/evidenza/white-list`.
- Dedicated application entry point: `https://whitelist.prefmi.it/elenco/inizio.php`.
- Combined operational table: `https://whitelist.prefmi.it/elenco/elenco.php`.
- Registered-company sibling view: `https://whitelist.prefmi.it/elenco/elenco_iscritte.php`.

The Ministry page positively describes the White List consultation and registration/renewal route. The dedicated application entry point identifies both an `ELENCO IMPRESE RICHIEDENTI ISCRIZIONE NELLA WHITE LIST PROVINCIALE` and an `ELENCO IMPRESE ISCRITTE NELLA WHITE LIST PROVINCIALE`. The combined operational table itself publishes source-explicit `RICHIESTA ISCRIZIONE (dd/mm/yyyy)` rows.

## Same-day mutable-source transition and byte identity

The source is a mutable current web application. An earlier independently stable capture on 16 September contained 4,214 sector rows and 2,614 logical observations at SHA-256 `350e995ac06fc9525c1bd21cc2e2ad8b69224e4dd603e530a65553c21f44b044`. Before production finalisation, the fail-closed national build detected that the official source had changed. The project did not relax the denominator or substitute the new hash.

Current-source audit GitHub Actions run `35107286700` then captured both official tables twice with no-cache headers and independently validated their structure and semantics. The paired captures were byte-identical:

- combined table: **972,380 bytes**, SHA-256 **`b360e209f3997894a3e7408e5be7f07d77cddca0c3490581ff3410218a02d9a8`**;
- registered-company sibling: **559,326 bytes**, SHA-256 **`4509948e4baf91ed5c92bd5940a2fca1cd5f9a6fd21f553c4864e68735e36608`**.

The current combined source contains **10** statutory tables, **4,220** physical sector-membership rows and **2,618** conservative logical observations. The registered-only sibling contains **1,456** logical identities, and that identity set exactly equals the **1,456 non-pending identities** in the combined table. No pending combined identity appears in the sibling.

Because both official resources are mutable, **2026-09-16 is a capture/reference boundary only**. It is not treated as an inferred application, decision, registration, expiry or legal-effect date for any company. Publication is byte-pinned to the reviewed current combined capture and fails closed again on further drift.

## Current parser boundary

The current combined boundary is:

- **10** section tables;
- **4,220** source sector-membership rows;
- **2,618** logical observations;
- **2,618/2,618** strict source identifiers, with one logical observation per identifier;
- **2,618/2,618** observations with at least one source-explicit statutory activity section;
- **939** `listed` observations;
- **517** `renewal_update_in_progress` observations;
- **1,162** `pending` observations.

All **1,162** pending observations have explicit application dates. All **939** listed observations have explicit listing and expiry dates. No date is manufactured for update rows. The latest positively observed applicant date is **16 September 2026**. The current source explicitly contains these four pending observations dated 16 September:

- SV VERNICIATURE INDUSTRIALI S.R.L. — `02685280394`;
- G.B.C. INDUSTRIAL TOOLS SPA — `07639230155`;
- VERNIA SRL — `11967860153`;
- CARBON SUD TRASPORTI E SERVIZI S.R.L. — `14302100962`.

The source changed again after the 4,218 / 2,617 boundary was reviewed. The current boundary is +1 logical observation and +2 sector rows relative to that second capture, with status counts moving from 941/515/1,161 to 939/517/1,162. SV VERNICIATURE INDUSTRIALI S.R.L. is positively observed as the additional 16 September pending identity. The retained evidence does not establish the individual identities behind the aggregate two-row `listed` to `renewal_update_in_progress` shift, so no identity or legal effect is inferred for those transitions.

Repeated section membership is retained as requested-activity provenance rather than published as duplicate company observations. Record locators use the source-published identifier and capture reference date rather than mutable HTML row position.

## Source-faithful treatment

No legal status is inferred beyond the source-explicit table semantics. In particular:

- `RICHIESTA ISCRIZIONE (...)` is mapped only to `pending`;
- `IN AGGIORNAMENTO` is mapped only to `renewal_update_in_progress`;
- rows with valid listing and expiry dates are mapped to `listed`;
- any previously unseen status/date pattern fails closed;
- company names, registered offices and identifiers are not repaired from external information;
- repeated sector memberships are grouped only under the reviewed identity/status/date rule.

One logical observation, **COMOTER SRL**, carries the combined-source note `Misura di prevenzione collaborativa ex art. 94 bis D.lgs.159/2011 in data 18/04/2024, per la durata di un anno`. It is retained strictly as source provenance and does not overwrite the table's explicit current status. The registered-only sibling exposes additional note presentations for some identities; those sibling notes are not imported into the chosen combined-series observation model.

## Validation and publication gate

The current-source validation ran Milano semantic tests and the full repository suite, required two byte-identical no-cache captures of each official table, independently audited all ten table headings/header geometry, strict identifiers, source status/date grammar and conservative grouping, verified the combined/non-pending identity set against the registered sibling, and rechecked positive Ministry/application-entry evidence.

The parser remains fail-closed on table count, section headings, expanded header geometry, row width, identifier syntax, unreviewed status/date patterns, logical-record denominator, status counts, identifier coverage and note denominator. The first production candidate run `35058960470` had validly demonstrated the earlier source edition before subsequent official-source drift. The current production finalisation therefore revalidates the complete national boundary from the now-reviewed current source instead of treating that historical candidate as sufficient.

On successful current national build, the expected public boundary is **54,183 records / 47 published Prefectures / 48 published registers / 47 mapped Prefectures**, with exactly **2,618 Milano observations / 2,618 distinct locators** and **48/48 register scopes source-complete**. `canonical_integration_validated` is promoted only inside the same production transaction and is committed only if those gates pass.

`durable_evidence_verified` remains **false** unless the project independently establishes the governed durable-evidence requirement; temporary workflow captures do not satisfy that requirement.
