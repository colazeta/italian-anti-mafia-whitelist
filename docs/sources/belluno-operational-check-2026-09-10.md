# Belluno White List operational check — 10 September 2026

## Current official source

- Official landing page: `https://prefettura.interno.gov.it/it/prefetture/belluno/evidenza/white-list`.
- Re-resolved current attachment: `https://prefettura.interno.gov.it/sites/default/files/29/2026-09/white_list_02_09_2026-1.pdf`.
- A GitHub-hosted source audit on 10 September resolved exactly one official attachment from the landing page. The PDF itself identifies enterprises enrolled in and requesting enrolment in the provincial Belluno White Lists and carries the explicit source date **2 September 2026**. Search-result labels that surfaced 1 September are not used as edition evidence because the live landing page resolves the dated 2 September PDF.
- Verified byte SHA-256: `65203c633f261deec31bba00be6c4893f90c8a40cd293b832066d20520ff8b58`.
- The source has 44 pages: page 1 is the ten-section legend, pages 2–43 contain one stable eight-column data table each, and page 44 has no data table.

## Population and parser boundary

The audited edition contains **402 source rows**: **392** listed-population rows with explicit listing and expiry dates and **10** rows explicitly marked `IN FASE ISTRUTTORIA`. Observed source-status counts are **281 listed**, **62 renewal/update in progress**, **49 expired observed**, and **10 pending/in istruttoria**. Status mapping uses only source-explicit notes and fails closed on unrecognised non-blank legal-status text.

Dates are normalised only from complete valid `DD/MM/YYYY` tokens. One visibly truncated source application date, `07/04/202`, is not reconstructed and remains canonically blank. Identifiers are preserved verbatim: **388/402** rows yield a strict canonical CF/PIVA token, **13/402** contain a non-empty raw identifier that does not satisfy the canonical rule, and **1/402** has a blank source identifier. No identifier is padded, truncated or repaired.

## Validation and publication boundary

`belluno_combined` requires 44 pages, the ten-section legend, 42 exact data-page headers, one table per data page, exactly eight columns and exactly 402 source rows. Publication requires the pinned source SHA-256 and confirms the full identifier partition and source-backed status counts. Public records stay inside public contract v3. Canonical hosted-database integration and independent durable-evidence verification are **not** claimed by this expansion and remain governed separately under issue #16.
