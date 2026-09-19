# Fermo White List operational check — 19 September 2026

## Official publication surface

The current official Prefettura di Fermo page positively exposes two separate populations: **Elenco di imprese iscritte alla White list al 22 maggio 2026** and **Elenco di imprese richiedenti iscrizione alla White list al 22 maggio 2026**. Both resources are XLSX attachments. Applicant completeness is therefore based on positive official evidence, not inferred from failed discovery.

- Listed XLSX: `https://prefettura.interno.gov.it/sites/default/files/0/2026-05/imprese-iscritte-wl-22-maggio-2026_0.xlsx` — SHA-256 `2ed8f867c6ee477ec0af22a827ac0ccf54e4d483eec5de5fc27c812a0c31c6dd`. Two independent cache-bypassed captures on 19 September 2026 were byte-identical.
- Applicant XLSX: `https://prefettura.interno.gov.it/sites/default/files/0/2026-05/imprese-richiedenti-iscrizione-wl-22-maggio-2026.xlsx` — SHA-256 `fa17e1f6676f84dc51e8abd1fd6e7627a1a2ed684a55c490708a06990e48676f`. Two independent cache-bypassed captures on 19 September 2026 were byte-identical.

The edition reference date is **22 May 2026**, taken from the explicit official attachment labels. The 19 September date is only the verification/capture date.

## Reviewed parser boundary

The listed workbook has one sheet (`Foglio1`) and a reviewed physical shape of 400 rows × 12 columns. Styled trailing ordinal-only cells are not company observations. The company boundary is **174 observations**, source ordinals 1–176 with 105 and 121 absent: **97 listed** and **77 renewal/update in progress**. Structured identifier coverage is 163/174; eleven malformed numeric identifiers remain raw-only. One malformed listing-date token, `28/11/204`, remains raw with no canonical date inferred.

The applicant workbook has one sheet and a reviewed physical shape of 267 rows × 15 columns. Its company boundary is **75 pending observations**, source ordinals 1–76 with 38 absent. Structured identifier coverage is 70/75; five malformed numeric identifiers remain raw-only. The raw application-date token `46092` is retained without conversion or inference.

Activity cells expose statutory section codes (`Sez. I` … `Sez. X`); the parser preserves only explicitly observed codes and fails closed on an unknown vocabulary.

## Publication decision

Both official sources are kept as separate source series under register `fermo-ordinary`, approved by exact raw SHA-256. The combined public candidate contributes **249 observations**. Canonical hosted-database integration and independent durable-evidence verification remain separate governance concerns and are not asserted by this expansion.
