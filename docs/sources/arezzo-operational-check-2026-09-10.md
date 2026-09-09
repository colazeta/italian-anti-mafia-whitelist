# Arezzo current-source operational check — 10 September 2026

## Official source identity

The direct official Prefettura di Arezzo page verified in this run is:

- `https://prefettura.interno.gov.it/it/prefetture/arezzo/iscrizione-white-list`

It exposes two distinct current populations:

- **Elenco imprese iscritte** — `https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco_imprese_iscritte_1.xlsx` — SHA-256 `9543260b49417fc8b223dc88a5838cd2cf4ef182fe4d3b690e4f5dbd5f6afd5f`, 72,001 bytes at verification.
- **Elenco imprese richiedenti l'iscrizione** — `https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco_imprese_richiedenti_iscrizione_1.docx` — SHA-256 `e12d9eb42894f90a4c7e40501006e36af14264ad34ce10cdee6c37e604bb15e7`, 161,650 bytes at verification.

The visible page metadata reports an older update date, while the live attachment paths are under `2026-09` and the applicant table contains applications through 8 September 2026. The archive therefore does **not** convert page metadata, Office document metadata or file path into a claimed statutory/publication date. `2026-09-10` is the verification/reference date for this byte-pinned current-source observation.

## Listed-company parser boundary

The current XLSX contains ten section sheets. Audit of the live bytes found **616 non-empty source sector rows** with explicit company identity and expiry date. Exact repetitions of the same company/office/identifier/date/update observation across sectors are grouped only for public readability, yielding **332 source-backed listed observations**.

Twenty company identity groups contain materially different listing dates, expiry dates or update annotations across source sections. Those variants are retained as separate observations. The parser does not choose a preferred date or silently collapse them.

One source row for `CO.I. INERTI S.R.L.` contains the listing-date string `0702/2025`. The missing separator is not inferred. The observation is retained because company identity and expiry date are explicit, but its canonical listing date is blank and the raw malformed pair is kept in source provenance. Raw identifiers that do not parse as an 11-digit numeric identifier or a 16-character alphanumeric identifier are likewise preserved without padding or truncation.

The 332 listed observations comprise **288 `listed`** and **44 `renewal_update_in_progress`** source statuses.

## Applicant parser boundary

The current DOCX contains one table with **32 applicant rows** and no incomplete identity/date rows. Membership in this official applicant list is represented as `pending`; it is not treated as independent evidence of a final legal outcome.

Word concatenates multiple requested activity labels into a single cell. The parser recognises only the audited White List activity vocabulary and fails closed on unrecognised residue. A small number of explicit dates use repeated slash typography (for example `03//06/2026`); only the separator duplication is normalised, no digit is changed, and the raw source form is retained in provenance.

## Publication and evidence status

The two byte identities are pinned in `data/publication/multi_prefecture_pilot.json`. The public pipeline must reproduce exactly 332 listed plus 32 applicant observations before Arezzo can be published. This is a verified public-source integration, **not** a claim that independent R2 durable evidence storage or canonical database integration has been completed for Arezzo. Those remain separately governed by issue #16.

The source-discovery and parser-boundary evidence was produced by GitHub Actions run `34417675583` after two preceding structure checks on the same official resources.
