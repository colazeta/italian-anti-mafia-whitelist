# Campobasso operational source check — 11 September 2026

## Current official evidence

The current official Prefettura di Campobasso White List landing page was directly verified on 11 September 2026. It positively exposes two distinct current populations, both explicitly dated **11 August 2026**: the registered-company list and the applicant-company list. No absence or completeness claim is inferred from search failure.

- Landing page: https://prefettura.interno.gov.it/it/prefetture/campobasso/evidenza/white-list
- Listed XLSX SHA-256: `9d07423eb023025e1dd318c610a205f287a4bee165e4f7fe34e2448f8d91d2a1` (380,550 bytes).
- Applicant DOCX SHA-256: `6b1b1f877a0ae5fe68d2472034975914723626a553257d4978296b3632a635ba` (28,695 bytes).

## Listed population

The XLSX contains one worksheet with ten stacked statutory White List sections. The frozen physical denominator is **882 section rows**: I 134; II 60; III 199; IV 51; V 179; VI 107; VII 31; VIII 19; IX 19; X 83.

Conservative grouping on exact company name, registered office, secondary office, raw identifier, registration date and expiry date yields **323 company observations**: **276 `listed`** and **47 `renewal_update_in_progress`**. Province is deliberately excluded from the grouping key only because the audited source uses `==`, `CB` and blank province cells inconsistently for otherwise exact repeated observations. Registered-office differences remain identity-relevant and are never fuzzy-merged.

The update column contains 741 blank row values, 132 exact `SI` values and 9 `SI (non richiesto per questa sezione)` values. No semantic group is classified as update-in-progress solely from the scoped note: every grouped observation carrying that note also contains an explicit plain `SI` occurrence.

Malformed source identifiers remain raw. The audit observed 53 malformed-identifier row occurrences (51 ten-digit and 2 nine-digit); examples include `1933960708`, `1910940707`, `1821800701`, `880470703` and `895390706`. No digit is added, removed or guessed.

## Applicant population

The current DOCX contains one table and exactly **19 applicant company rows**, with the header repeated twice. The population is positively identified by the official page as companies requesting registration; all 19 observations are therefore represented as `pending`. No duplicate applicant rows were found and no applicant identifier required reconstruction.

Application dates use Italian written month names (for example `14 novembre 2025` and `07 agosto 2026`). The parser accepts only the explicitly reviewed Italian month-name mapping and fails closed on unreviewed date typography or invalid calendar dates.

## Publication and validation boundary

The parser freezes the current worksheet/table structure, ten section denominators, semantic-group count, status counts, repeated applicant headers and exact source hashes. Unknown status text, duplicate rows within a statutory section, source hash drift, unexpected worksheet/table structure, unreviewed dates or denominator drift fail closed. Address normalisation is conservative and no missing identity, address, legal status or population evidence is inferred.

The resulting public candidate contributes **342 source observations**: 323 listed-population observations and 19 applicant observations. Canonical hosted-database integration and independently durable evidence remain governed separately under issue #16 and are not claimed by this source/publication validation.
