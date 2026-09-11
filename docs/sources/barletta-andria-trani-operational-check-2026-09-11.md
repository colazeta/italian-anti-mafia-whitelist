# Barletta-Andria-Trani operational source check — 11 September 2026

## Current official publications

The current White List populations were independently reverified on the Prefettura di Barletta Andria Trani website on 11 September 2026. The authority publishes separate dedicated official pages for registered companies and applicants; each page directly exposes one current PDF attachment.

- Registered-company page: `https://prefettura.interno.gov.it/it/prefetture/barletta-andria-trani/white-list-elenco-imprese-iscritte`.
- Registered-company PDF: `https://prefettura.interno.gov.it/sites/default/files/104/2026-09/white-list-prefettura-di-barletta-andria-trani_1.pdf`; 211 pages; SHA-256 `d3c0e61942cbdefd03cfa7d99f71b2abbfc430f25ff86b8693d44ef14de07e13`.
- Applicant page: `https://prefettura.interno.gov.it/it/prefetture/barletta-andria-trani/white-list-elenco-imprese-richiedenti-liscrizione`.
- Applicant PDF: `https://prefettura.interno.gov.it/sites/default/files/104/2026-09/elenco-imprese-rich-iscriz-white-list-prefettura-di-barletta-andria-trani_0.pdf`; 15 pages; SHA-256 `ce460ca66f2d996784ac28d559af5fe702ae8a1d72ed80affeb70a0cb36b0d57`.

The applicant PDF is positively population-bounded by its in-document title, `ELENCO DELLE IMPRESE RICHIEDENTI L’ISCRIZIONE`; applicant status is therefore not inferred from discovery failure or from an unlabeled document.

The archive reference date `2026-09-11` records this verified current-edition checkpoint; it is not presented as an inferred legal effective date for an individual firm.

## Registered-company parser boundary

The registered-company PDF is organised into the ten White List sections. The parser freezes both page boundaries and the exact reviewed sector-row denominators: I 148, II 68, III 211, IV 84, V 205, VI 136, VII 8, VIII 12, IX 23 and X 118, for **1,013 source sector rows**.

Because the official document repeats the same firm across sections, the public archive groups rows only when the source-backed identity, semantic listing/expiry dates, procedural status and note agree. This yields **493 public registered-population observations**, while preserving all contributing sections. The current grouped status distribution is **437 `listed`** and **56 `renewal_update_in_progress`**. At the ungrouped source-row layer the frozen distribution is **883 listed + 130 update-in-progress = 1,013**.

Two rows for `EDIL AGRESTI SRL` (page 167, source row 4, section VI; page 210, source row 2, section X) contain the visibly split source typography `Aggiornament o in corso`. That exact reviewed source token is treated as positive update-in-progress evidence and is preserved raw; the parser does not generalise this repair to arbitrary near-matches.

Seven malformed date strings are retained verbatim in provenance and are never reconstructed: `14/072026`, `21/05/20259`, `30/06 /2027`, `17/11/20255`, `17/07/202 6`, `01/09/20267`, and `2/6/09/2025`. The reviewed embedded string `31/07/2026 Aggiornamento in corso` contributes the explicit date `31/07/2026` while preserving the procedural text. Any new unsupported date typography fails closed.

Identifiers are normalised only when an exact contiguous 11-digit numeric or 16-character alphanumeric token is present. The parser does not pad, truncate or reconstruct identifiers.

## Applicant parser boundary

The current applicant edition yields exactly **81 public observations**, all mapped to `pending` because they occur in the positively identified applicant publication. The parser freezes the reviewed 15-page geometry and two page-leading continuations needed to preserve split source rows; any new unresolved structural drift fails closed.

## Publication boundary

The two current populations contribute **574 source-backed public observations**. Canonical hosted-database integration and independent durable-evidence verification remain separately governed under issue #16 and are not implied by this public-source validation.
