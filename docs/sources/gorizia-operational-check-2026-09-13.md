# Gorizia White List operational check — 2026-09-13

## Scope

This checkpoint records positive current-source evidence for the Prefettura di Gorizia, freezes the current official source bytes, and documents the conservative parser candidate now implemented on the expansion branch. National integration and public export are not yet approved.

## Official publication surface

- Official landing page: `https://prefettura.interno.gov.it/it/prefetture/gorizia/evidenza/white-list`
- Live verification on 13 September 2026 returned the official page successfully. The page reports its own last update as **17 August 2026, 12:37**.
- The landing page positively exposes two distinct current publication resources:
  - applicants, labelled `Ditte per cui è in corso la richiesta di iscrizione alla WhiteList`: `https://prefettura.interno.gov.it/sites/default/files/0/2026-08/2026.08-white-list-ditte-richiedenti-iscrizione.pdf`
  - listed companies, labelled `Elenco delle Ditte della provincia di Gorizia iscritte alla White List`: `https://prefettura.interno.gov.it/sites/default/files/0/2026-08/gorizia-elenco-ditte-iscritte-wl.docx`
- The applicant publication is a PDF and the listed publication is a DOCX. The official page therefore provides positive evidence for both logical populations; neither population is inferred from filename construction or search-engine absence.
- The attachments do not provide a safely established document-level reference date. The parser candidate therefore uses **2026-09-13 as the archive capture/verification date**, not as a claimed publication date. The August 2026 URL paths and the landing-page update timestamp remain provenance signals only.

## Frozen capture

The two exact official resources were each fetched twice independently by the source-audit workflow. Both repeat captures were byte-identical and passed native-container validation.

- listed DOCX:
  - bytes: **108,574**
  - SHA-256: `680f0822f56ce7499a5d3f6c9e524d3d33b631feca51886e57e70fdf9e5fbd6d`
  - valid OOXML/ZIP container with required `[Content_Types].xml` and `word/document.xml`; **21** container entries
- applicant PDF:
  - bytes: **143,930**
  - SHA-256: `befe7ed054e0cfe9dda48c8dec59f843b569019e40b925d6d5d1fcec19021c7c`
  - valid PDF; **2 pages**

Any later source failure must be recorded as a retrieval failure. It must **not** be converted into `NOT_PUBLISHED`, a missing applicant population, a legal-status claim, or an assertion of completeness. Any later byte change must be treated as source drift and re-audited before parsing.

## Document structure and parser contract

### Listed DOCX

The frozen listed source contains **10 sector tables**, with non-header row counts `26, 13, 25, 14, 32, 38, 0, 1, 10, 27`, for **186 sector rows**. Every source row has seven physical OOXML cells matching the publication schema: Ragione Sociale; Sede legale; Sede secondaria con rappresentanza stabile in Italia; Codice fiscale/Partita IVA; Data d’iscrizione; Data scadenza iscrizione; Aggiornamento in corso.

Because the same registration is repeated across sector tables, 186 is not a company-observation count. The implemented parser groups only exact cleaned `(name, office, secondary office, identifier_raw, listing_raw, expiry_raw)` tuples, aggregates sector memberships and update evidence, and performs no fuzzy spelling, address, identifier or date merge. This conservative contract yields a **candidate 117 listed-registration observations** from all 186 source rows. The candidate status split is **86 `listed` and 31 `renewal_update_in_progress`**. These counts remain subject to the current byte-pinned parser-validation gate before national integration.

The `Aggiornamento in corso` column is not binary. Across sector rows the raw lexemes are blank 138; `IN AGGIORNAMENTO` 41; `21 gennaio 2026` 1; `25 settembre 2026` 3; `30 luglio 2027` 1; and `“` 2. The parser treats a nonblank value in this explicitly labelled source column as positive update evidence and preserves the raw value; it does not reinterpret the publisher's date or ditto typography into a different legal meaning.

Identifier and date anomalies are preserved raw. Reviewed malformed date lexemes include `10.12.202` and `14 agosto 204`; they are not silently repaired into normalized dates. The source also contains the valid Italian ordinal typography **`1° giugno 2027`**. Support for the optional ordinal marker was added explicitly after the parser correctly failed closed on that previously unreviewed form; accepting it is source-supported date parsing, not a relaxation of validation. The physical OOXML extraction also exposes one reviewed split-run typography, `2 1 aprile 2026`, for MOVITUB di Giovanni Veneruso & C. SAS. The same source cell's logical text is `21 aprile 2026`, and another source occurrence for the same company/identifier also reads `21 aprile 2026`. The parser therefore maps only this exact reviewed physical lexeme to `2026-04-21`, while preserving the raw source value and keeping the exact physical registration grouping unchanged; no generic whitespace/date repair is enabled. Other examples retained raw include `00001092420312`, `001370303018`, `0237978303` and company-name variants such as `EQUIPE SRL` / `EQUPE SRL`.

### Applicant PDF

The frozen applicant source is a two-page table publication. Coordinate and table-structure probes positively establish **10 distinct 11-digit identifier anchors** in source order:

`01270500315`, `01262160318`, `01190800316`, `01270740317`, `00407990316`, `01268270319`, `00557360310`, `01040110312`, `01170510315`, `01195820319`.

The corresponding source names are ITALTRCH SRL, METAL X SRL, `“L’ANTICA RICETTA SRLS”`, EL.NET SOLUTION SRL, C.M.T. SRL, FMGDUE SRL, SI.ECO:SICUREZZA ED ECOLOGIA SRL, SULTAN SRL, SVILUPPO SOLARE SRL and T-RECYCLE SRL. The publication crosses a page boundary at the SULTAN record. The implemented parser reconstructs records from the 11-digit anchors and source row boundaries, requires exactly seven anchors on page 1 and three on page 2, and preserves blank application dates as blank. The candidate applicant population is therefore **10 `pending` observations**, again subject to the byte-pinned parser-validation gate.

## Gate state

At this checkpoint:

- `source_verified`: **true**, from positive official landing-page evidence;
- current listed publication resource: **identified and byte-frozen**;
- current applicant publication resource: **identified and byte-frozen**;
- repeat-fetch byte identity: **verified** for both resources;
- document-level publication dates: **not asserted**; archive capture/verification date is 2026-09-13;
- parser family: **implemented on the expansion branch with fail-closed structural invariants**;
- candidate observations: **127 total** = 117 listed-series observations + 10 applicant observations;
- candidate statuses: **86 `listed` / 31 `renewal_update_in_progress` / 10 `pending`**;
- `population_scopes_complete`: **not yet promoted to canonical status until parser validation and national integration gates succeed**;
- public export: **not approved**.

The next gate is the current byte-pinned parser validation plus ordinary CI. If both succeed, the workstream can proceed to permanent semantic tests and transactional national integration. No national totals or live coverage increase should be asserted before that gate passes.
