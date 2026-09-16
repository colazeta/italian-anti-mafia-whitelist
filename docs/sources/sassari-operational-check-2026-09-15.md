# Sassari White List operational check — 2026-09-15

## Decision

The current official Sassari White List workbook positively resolves both logical source populations from one combined publication. It is therefore admissible as a `listed_and_applicant` series; this supersedes the earlier unresolved applicant-population assessment, which had been based only on the generic attachment label without inspection of the workbook schema.

This check does **not** infer publication absence, legal status, dates or completeness from search failure. The decision is based on the current official workbook and its source-explicit row semantics.

## Official source

Landing page:

https://prefettura.interno.gov.it/it/prefetture/sassari/evidenza/white-list

Current workbook:

https://prefettura.interno.gov.it/sites/default/files/93/2026-08/2026-elenco-provinciale-aggiornato-al-31.08.2026.xlsx

The workbook filename supplies the source-edition/reference date **2026-08-31**. That date is not propagated as an inferred company decision, registration, application or legal-effect date.

Two independent no-cache captures in the source-validation gate were byte-identical:

- bytes: **123,745**;
- SHA-256: **`e5cf9776971e4c0b46b97c56e2764f906bd07e3d573ac07b59fcd6605ab9c370`**.

The source-validation workflow independently rechecks the landing-page link, repeats the two captures and fails closed on byte/hash drift.

## Workbook geometry and population evidence

The workbook has four worksheets: `Foglio1`, `Foglio2`, `Foglio3`, `Foglio4`. Exactly one worksheet matches the audited White List schema: `Foglio1`, with the header on physical row 7.

The source table contains 18 relevant columns:

1. company;
2. registered office;
3. tax/VAT identifier field;
4–13. the ten statutory White List activity columns;
14. application date;
15. start of registration/permanence;
16. expiry;
17. notes;
18. previous registration expiry.

The same physical table directly includes both first-time applicants and registered/renewal-side observations. `RICHIESTA ISCRIZIONE` (including the observed whitespace and `ISCRIZONE` source typography variants) is positive source evidence for a pending application. `RICHIESTA PERMANENZA` and source note `AGGIORNAMENTO` are positive evidence for renewal/update in progress. A valid source date in the start column is treated as a listed observation only when no stronger source-explicit update/expiry qualifier applies.

The parser does not derive a legal status from a blank status cell.

## Frozen parser boundary

The complete non-empty source-row population is **478 observations**, with 478 unique observation locators:

- `listed`: **335**;
- `pending`: **129**;
- `renewal_update_in_progress`: **12**;
- `expired_observed`: **1**;
- `other_or_unknown`: **1**.

Strict identifier coverage is **472/478**. Six raw identifier fields fail the repository's strict 11-digit VAT / 16-character fiscal-code shapes and remain raw rather than being padded, truncated or repaired.

Every accepted row has at least one source-explicit activity marker. The parser accepts only an exact `x` marker case-insensitively; any different nonblank marker or a row with no marked activity fails closed.

## Reviewed anomalies preserved without repair

The audited edition contains the following source anomalies; they are frozen as evidence rather than silently corrected:

- `M.I.A. SRL`: application-date cell `129.01.2025`. The raw value is preserved and the canonical application date is blank; source digits are not repaired.
- `DE.SCA.RI DEL GEOM. CALIA GIANLUCA`: the registered-office column contains `CLAGLC74B11E736M`, while the identifier column contains `OLBIA`. The apparent column swap is preserved exactly; no cross-column correction is made.
- `AAC COOPERATIVA SOCIALE`: application and expiry data are present but the source supplies no start/request status lexeme. The observation therefore remains `other_or_unknown` rather than being inferred as listed or pending.
- `ROMANO FRANCA`: the start/request column says `RICHIESTA ISCRIZIONE` but the source note says `SCADUTA`. The stronger explicit expiry note is preserved as `expired_observed`, not flattened to pending.
- six malformed/raw-only identifier fields are preserved for `COOPERATIVA SO.LI.DA. SOCIETA' COOPERATIVA SOCIALE`, `CROCE SARDA BONORVA SOCIETA' COOPERATIVA SOCIALE ONLUS`, `DE.SCA.RI DEL GEOM. CALIA GIANLUCA`, `MEDITERRANEA AMBIENTE SRL`, `SACCU DAVIDE` and `SOLIMAS SRL`.

Source-row provenance is retained through the physical worksheet/row locator, raw application date, source note/previous-expiry text and activity-marker provenance. The public provenance projection uses only fields already admitted by the recursively closed public contract.

## Validation state

- current official source positively verified: **yes**;
- combined listed/applicant population positively established: **yes**;
- byte-pinned parser implemented: **yes**;
- parser semantic boundary validated: **yes**;
- company observations loaded into a national candidate: **yes** — the successful candidate build validated **51,566** national records, **46** published Prefectures, **47** published registers and **47** mapped Prefectures, including exactly **478** Sassari observations and **478** distinct locators;
- `canonical_integration_validated`: **true**;
- `durable_evidence_verified`: **false**.

The canonical/public integration flag is promoted only because the national candidate build, denominator checks, exact production-transaction recheck and integration commit all completed successfully. Independent durable-evidence verification remains a separate infrastructure/evidence concern and is not inferred from publication success.
