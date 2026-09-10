# Ascoli Piceno operational source check — 10 September 2026

## Current official publication

The current official Prefettura di Ascoli Piceno White List page was re-resolved directly on 10 September 2026:

- landing page: `https://prefettura.interno.gov.it/it/prefetture/ascoli-piceno/elenco-iscritti-white-list`
- live landing response: HTTP 200
- landing capture SHA-256 observed by the audit runner: `2072b102a8f344144c5ae9e585746e867883c91d9273773afbbb4b0f341b96c6`
- the page identifies the current publication as updated on 11 August 2026 and exposes both the comprehensive registered-company PDF and the applicant-company PDF.

The same page also exposes ten section-specific registered-company PDFs. Those sector files are alternate manifestations of the registered population and are not ingested separately when the comprehensive all-sections PDF is available, because doing so would duplicate observations.

## Byte-pinned source editions

### Registered companies

- source key: `ascoli-piceno-listed`
- current resource: `https://prefettura.interno.gov.it/sites/default/files/31/2026-08/elenco-degli-iscritti.pdf`
- HTTP 200 on 10 September 2026
- bytes: 474,484
- SHA-256: `5c1e7e6145929162207721d79302a5267524e5b35429234a961eee504b75c43b`
- document pages: 110
- explicit document marker: `Aggiornato al 11/08/2026`
- logical company starts (`Ragione Sociale:`): 544
- identifier labels (`CODICE FISCALE:`): 544
- explicit source statuses: 448 `Iscritto`; 96 `In aggiornamento`

The parser maps only those source-explicit statuses: `Iscritto` to `listed` and `In aggiornamento` to `renewal_update_in_progress`. It does not reinterpret an update-in-progress observation as a new application or as a final legal outcome.

The document labels its two row dates as `DATA PROVVEDIMENTO` and `SCADENZA`. The parser therefore preserves the first as `decision_date` and the second as the observed expiry date. It does not relabel the first date as an enrolment date without source evidence.

### Companies requesting registration

- source key: `ascoli-piceno-applicants`
- current resource: `https://prefettura.interno.gov.it/sites/default/files/31/2026-08/elenco-dei-richiedenti-l-iscrizione.pdf`
- HTTP 200 on 10 September 2026
- bytes: 61,123
- SHA-256: `b278d9eeb3c387ea6b8eb67f5da74a1918eecdac720a400b34e29b626e962453`
- document pages: 9
- explicit document marker: `Aggiornato al 11/08/2026`
- logical company starts (`Azienda:`): 57
- identifier labels (`Codice fiscale:`): 57
- explicit application-date labels: 57
- explicit outcomes: 57 `istruttoria`

All 57 applicant observations are therefore mapped to `pending` using positive row-level evidence. No applicant population or status is inferred from absence, search failure or a blank field.

## Parser boundary and integrity rules

The approved parser family is label-bounded rather than dependent on a generic PDF table reconstruction. Each registered observation begins at the source label `Ragione Sociale:` and each applicant observation begins at `Azienda:`. The parser fails closed if the expected page counts, update marker, logical-row denominators, identifier-label denominators, recognised source statuses or required source-backed White List section labels drift.

Identifiers are retained verbatim in `identifier_field_raw`; canonical identifiers are emitted only through the repository's existing conservative identifier routine. The parser never repairs malformed or non-canonical identifiers. Dates are normalised only when the exact source token is a valid `dd/mm/yyyy` calendar date. Addresses and activity sections are retained from their labelled source fields; no inferred geography is added.

Expected current public observations after integration: 544 registered-population observations plus 57 applicant observations = 601.

## Remaining infrastructure boundary

This source/parser validation concerns the public-source observation layer. Canonical hosted-database integration and independent durable-evidence verification remain separate under issue #16 and are not represented as completed by this expansion.
