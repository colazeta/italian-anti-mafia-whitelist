# Catania operational source check — 12 September 2026

## Current official evidence

The current official Catania White List landing was directly resolved on 12 September 2026. It exposes separate current XLSX resources for registered companies and companies requesting registration, both explicitly updated **11 September 2026**. Each resource was independently fetched twice during source verification and returned identical bytes across both requests.

- Landing page: https://prefettura.interno.gov.it/it/prefetture/catania/comunicazioni/white-list-provinciale
- Listed XLSX: https://prefettura.interno.gov.it/sites/default/files/18/2026-09/white-list-iscritti-aggiornato-11-settembre-2026.xlsx
- Listed SHA-256: `1d2cbba0751998da03ed7335c6525a8392bd3ec12513e81ee5f3f020e498a291`.
- Applicant XLSX: https://prefettura.interno.gov.it/sites/default/files/18/2026-09/white-list-richiedenti-aggiornato-11-settembre-2026.xlsx
- Applicant SHA-256: `4e0cb83a5718cd54b284847a0746fe52fc48bb81be201b758d55024662cb2c27`.

## Population boundary and parser result

The listed workbook contains a single `Foglio1` sheet. The company population is one contiguous block at source rows 3–1,634, yielding **1,632 listed-population observations**: **1,281 `listed`** and **351 `renewal_update_in_progress`**. Only source text explicitly containing the renewal lexeme (`rinnovo`) is elevated to renewal/update status; cryptic or unrelated update-column content is preserved raw and is not reinterpreted.

The applicant workbook contains a single `Foglio1` sheet. Its company population is one contiguous block at source rows 5–328, yielding **324 applicant observations**, all represented as **`pending`** because the official applicant population is positively identified and the outcome field is blank throughout. The combined Catania public candidate therefore contains **1,956 observations**.

## Conservative exceptions and fail-closed behaviour

The parser freezes source hashes, worksheet names and dimensions, company-row boundaries, footer legends, record denominators, status counts, strict-identifier coverage and the reviewed anomaly classes. Strict identifiers are emitted only for explicit 11-digit numeric or 16-character alphanumeric source values. This yields identifier coverage of **1,588/1,632** listed observations and **322/324** applicant observations; nonstandard raw identifiers are preserved without padding, correction or reconstruction.

Four listed section strings contain fused or otherwise malformed tokens. For those exact reviewed row/value pairs the raw source is preserved and only independently separated, valid section tokens are retained; fused tokens such as `6 10`, `34`, `610` or `69` are never split or repaired. Two malformed listed registration-date strings (`16/072026` and `09/062026`) are preserved raw and their canonical dates are left blank.

The listed expiry column contains 1,491 formulas. Exactly 1,490 use the source's standard self-row `DATE(YEAR(Frow)+1,MONTH(Frow),DAY(Frow))` pattern and may use the workbook's cached source value after strict calendar validation. One reviewed anomalous formula at source row 1,064 is preserved raw and produces no inferred canonical expiry. Three listed rows have blank expiry values, and one listed row has a blank office; these remain blank rather than being reconstructed from surrounding text.

No fuzzy matching, speculative date repair, identifier repair, fused-section decomposition or inferred applicant outcome is used. Unexpected structure, vocabulary, row counts, formula classes or reviewed anomaly values fail closed.

## Publication interpretation

Rows are public-source observations, not an independently adjudicated statement of present legal status. Canonical hosted-database integration and independent durable-evidence verification remain governed separately under issue #16.
