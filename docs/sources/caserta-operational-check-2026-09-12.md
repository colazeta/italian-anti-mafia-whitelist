# Caserta operational source check — 12 September 2026

## Current official evidence

The current official Caserta White List landing was directly resolved on 12 September 2026. It exposes separate current PDFs for registered companies and companies requesting registration, both with a **31 August 2026** population boundary. During the source audit each resource was independently fetched twice and returned identical bytes across both requests.

- Landing page: https://prefettura.interno.gov.it/it/prefetture/caserta/elenco-white-list
- Listed PDF: https://prefettura.interno.gov.it/sites/default/files/30/2026-09/elenco-iscritti-31082026_white-list.pdf
- Listed SHA-256: `d323335641b3a84a2e13c047e403030b5bb6a98ec6d034c8648d1286d703585a`.
- Applicant PDF: https://prefettura.interno.gov.it/sites/default/files/30/2026-08/elenco_imprese_richiedenti_iscrizione_white_list-al-31.08.2026.pdf
- Applicant SHA-256: `90f4bfbedd6c2e4794330066df83bfce834bb3a2707902fe2705430439d1ffc5`.

## Population boundary and parser result

The listed PDF has 89 pages with exactly one nine-column table per page. After excluding one repeated header row on every page, the source indices are contiguous 1–950 and yield **950 observations**: **395 `listed`**, **548 `renewal_update_in_progress`**, and **7 `other_or_unknown`** observations preserving special source conditions without reinterpretation.

The applicant PDF has 68 pages with exactly one eight-column table per page. After excluding repeated headers, source indices are contiguous 1–1,208 and yield **1,208 applicant observations**, all represented as **`pending`**. The combined Caserta public candidate therefore contains **2,158 observations**.

## Conservative exceptions and fail-closed behaviour

The parser freezes page count, one-table-per-page geometry, table widths, source-index sequences, source-status vocabularies, identifier-token distributions, blank-date counts and the complete reviewed anomaly vocabulary. Identifiers are extracted only as explicit strict 11-digit numeric or 16-character alphanumeric tokens. A single reviewed listed row (source index 7) contains its otherwise strict identifier in the secondary-office column; this exact row/value pair is allowlisted and no generic column-shift fallback exists.

Reviewed malformed/noncanonical source date strings remain raw and their canonical date is left blank. This includes the applicant source token **`28/25/2025`** at source index 188, which is an invalid calendar date and is not corrected or inferred. Three listed registration-date tokens and five listed expiry-date/source-condition strings are likewise frozen as reviewed raw exceptions. Source-section anomalies are accepted only for the exact reviewed index/value pairs; unexpected values fail closed.

No fuzzy matching, inferred applicant outcome, inferred identifier, or speculative date correction is used.

## Publication interpretation

Rows are public-source observations, not an independently adjudicated statement of present legal status. `other_or_unknown` is used where the source carries a special condition that cannot defensibly be collapsed into `listed` or renewal/update status. Canonical hosted-database integration and independent durable-evidence verification remain governed separately under issue #16.
