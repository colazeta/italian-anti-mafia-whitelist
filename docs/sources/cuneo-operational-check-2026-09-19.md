# Cuneo White List operational check — 19 September 2026

## Official publication surface

The current official Prefettura di Cuneo page positively exposes two separate White List populations: **Elenco iscritti White List** and **Elenco richiedenti iscrizione White List**. The source documents themselves carry the explicit marker **martedì 15 settembre 2026**. The landing-page timestamp is not used as the edition date.

- Official page: https://prefettura.interno.gov.it/it/prefetture/cuneo/elenco-iscritti-white-liste-e-elenco-richiedenti-white-list
- Listed PDF: https://prefettura.interno.gov.it/sites/default/files/39/2026-09/elenco-iscritti-white-list_0.pdf
- Applicant PDF: https://prefettura.interno.gov.it/sites/default/files/39/2026-09/elenco-richiedenti-iscrizione_0.pdf

Two independent cache-bypassed captures of each attachment were byte-identical during the reviewed validation run. The approved content identities are:

- listed: `3556b033acea0b035ad8f955973affa97637260c4abe233d53518e5c7a32a2f7` (653,517 bytes);
- applicants: `25ee4f5fff0b0f6580396c27f3e73abfdcfa994bfe673e7a86ca33377e784cea` (239,448 bytes).

## Parsed boundary

The fail-closed positioned-text parser binds the two series separately. The listed document has 137 pages and yields **468 company observations from 1,063 activity rows**: **402 listed** and **66 renewal/update in progress**. The applicant document has 13 pages and yields **48 pending observations from 93 activity rows**. Combined Cuneo publication therefore contributes **516 observations**.

Structured identifier coverage is **457/468** for the listed population and **48/48** for applicants, hence **505/516** overall. Eleven malformed numeric identifier strings in the listed source are retained verbatim in `identifier_field_raw` and are deliberately not padded, truncated or promoted to structured identifiers. The two strict listed identifiers observed twice remain duplicated as source evidence rather than being deduplicated across source records.

## Reviewed source anomalies and conservative handling

The parser freezes page-level denominators, the exact source-status vocabulary, activity-row counts, duplicate-identifier boundary and reviewed layout exceptions. Two identity-column spillovers are accepted only at their reviewed ordinals: record 113 contributes `d'Alba` to the registered office and record 394 contributes `Cuneo`; any additional spillover fails closed.

Listed record 71 (BAUDINO TRASPORTI S.r.l., identifier `02905860041`) carries conflicting raw listing dates `07/01/2025` and `07/01/2015` across repeated activity rows. Both raw variants are preserved and `observed_listing_date` remains empty; no preferred date is inferred. Sixty-five listed observations have no expiry date in the source and remain empty.

The applicant population is positive evidence, not an inference from search: the document title is explicitly “elenco delle ditte richiedenti l'iscrizione nella white list”. PDF extraction splits that title across a line break, so the guard normalises whitespace and apostrophe typography only before matching the reviewed title. It does not broaden the accepted population semantics.

## Publication decision

The approved publication configuration uses raw SHA-256 pinning for both attachments, retains the two source series separately under register `cuneo-ordinary`, and exposes only source-backed observations through the existing recursively closed public contract. Canonical hosted-database integration and durable evidence remain separate concerns and are not asserted by this expansion.
