# Cagliari White List — operational source check (11 September 2026)

## Current official publication surface

The official Prefettura di Cagliari White List landing page was fetched directly on 11 September 2026:

- landing page: `https://prefettura.interno.gov.it/it/prefetture/cagliari/evidenza/white-list`
- fetched bytes: 116,969
- landing-page SHA-256 observed during the verification run: `39cb9378d02a4a02aa999aca1e4e760f9331d7ea594b4bceba3018011e403122`

The page positively exposes two separate current resources, both explicitly dated 6 September 2026:

1. `White List - Elenco Ditte iscritte al 06 settembre 2026`
2. `White List - Elenco Ditte richiedenti iscrizione al 06 settembre 2026`

This is positive evidence for both the registered/listed population and the applicant population. No population scope is inferred from failed search or from absence of a link.

## Listed-company source

- resource URL: `https://prefettura.interno.gov.it/sites/default/files/0/2026-09/white-list-elenco-ditte-iscritte-al-06-settembre-2026.pdf`
- bytes: 1,457,900
- SHA-256: `dfbc00403ee287511a48df5314c663f5a1c6173803d87c4ce27b1d80e2c13114`
- pages: 24
- source reference date: 6 September 2026

The table semantics are those of the listed population: every accepted source row carries a section code, `DATA ISCRIZIONE`, `DATA SCADENZA ISCRIZIONE`, and an optional `AGGIORNAMENTO IN CORSO` note. The attachment contains 1,832 valid sector rows, with the following exact section denominator:

| Section | Source rows |
| --- | ---: |
| I | 263 |
| II | 117 |
| III | 297 |
| IV | 125 |
| V | 348 |
| VI | 266 |
| VII | 53 |
| VIII | 33 |
| IX | 62 |
| X | 268 |
| **Total** | **1,832** |

At source-row level, 1,723 rows are ordinary listed observations and 109 carry an update/renewal-in-progress annotation.

### Reviewed source-title anomaly

The listed attachment's internal heading says `ELENCO DELLE IMPRESE RICHIEDENTI L'ISCRIZIONE...`, which conflicts with the official landing-page link label and with the table's registration/expiry semantics. This is retained as a source anomaly, not silently corrected. Population classification is based on the official landing-page designation of the resource as `Elenco Ditte iscritte` together with the registration-date, expiry-date and update-in-progress columns. The raw attachment is byte-pinned above.

### Conservative repeat grouping

Cagliari publishes the same listed observation once for each applicable White List section. A dedicated geometry/conflict audit compared:

- a broad identity/date/status grouping; and
- a stricter grouping requiring the same cleaned legal name, raw identifier, legal address, secondary address, registration date, expiry date, status and source note.

Both produce exactly **750** public listed-population observations. The audit found:

- 0 name-conflict groups;
- 0 address-conflict groups;
- 0 address-sensitive groups;
- 0 duplicate same-section rows within a group;
- 397 observations spanning more than one section;
- maximum of 10 section rows for one observation.

The grouped population is therefore frozen at:

- 713 `listed`;
- 37 `renewal_update_in_progress`;
- **750 listed-population observations in total**.

The parser retains all applicable source sections on the grouped observation and does not deduplicate across records unless the conservative source identity, address, dates and status agree.

### Identifier anomaly

Two sector rows — sections I and V for `AEFFE di Farci Alessandro`, `Cagliari, Via Del Pozzetto 8` — publish the ten-digit raw value `0336817853`, with the same registration date `07/11/2025` and expiry date `06/11/2026`. They form one source observation because all conservative grouping fields agree. The raw value is retained in `identifier_field_raw`; no digit is added or inferred and the canonical identifier array remains empty.

## Applicant source

- resource URL: `https://prefettura.interno.gov.it/sites/default/files/0/2026-09/white-list-elenco-ditte-richiedenti-iscrizione-al-06-settembre-2026.pdf`
- bytes: 125,176
- SHA-256: `7429040f5945ecb72cc7b152dbd8aaeee0e0a5df9bb7414e951a4cec4a4f50f7`
- pages: 2
- source reference date: 6 September 2026

The PDF contains exactly **51 applicant rows**: 40 on page 1 and 11 on page 2. Every accepted row contains an explicit application date and an explicit `In istruttoria` outcome. All 51 are therefore mapped to the public source status `pending`; the requested White List sections are retained explicitly from the source rather than inferred.

Fifty applicant rows contain a strict 11-digit VAT/fiscal number or 16-character fiscal code. One row, `La Pignola S.r.l.`, publishes the ten-digit raw value `3814850925`; it is retained raw and is not reconstructed into a canonical identifier. `Collu Giuliano Impresa Individuale` has a blank source address; the blank is preserved and no address is inferred.

There are no exact duplicate applicant rows in the current attachment.

## Publication boundary

The Cagliari current-source contribution is therefore **801 public source observations**:

- 750 from the listed population: 713 `listed`, 37 `renewal_update_in_progress`;
- 51 applicants: 51 `pending`.

Parser validation is fail-closed on the pinned page counts, sector-row denominator, section counts, grouped-record denominator, applicant page counts, status counts and identifier coverage. Conservative address handling and raw identifier preservation remain unchanged.

Canonical hosted-database integration and independent durable-evidence verification remain governed under issue #16; the public source observation layer is validated independently of that infrastructure.
