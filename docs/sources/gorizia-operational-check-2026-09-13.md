# Gorizia operational source check — 2026-09-13

## Scope

This note records the evidence-first operational check for the Prefettura di Gorizia White List before any national-registry integration. It is intentionally limited to the current official publication surface, byte-level provenance, publication structure and parser invariants. Search/retrieval failure is never used to infer `NOT_PUBLISHED`, legal status, applicant completeness or population completeness.

## Official publication surface

Official landing page:

- `https://prefettura.interno.gov.it/it/prefetture/gorizia/evidenza/white-list`
- official page last updated: **17 August 2026, 12:37**

The landing page exposes two distinct current official attachments:

1. **Listed population** — DOCX
   - `https://prefettura.interno.gov.it/sites/default/files/0/2026-08/gorizia-elenco-ditte-iscritte-wl.docx`
   - verified size: **108,574 bytes**
   - SHA-256: `680f0822f56ce7499a5d3f6c9e524d3d33b631feca51886e57e70fdf9e5fbd6d`
   - valid OOXML ZIP container; 21 members; `[Content_Types].xml` and `word/document.xml` present.

2. **Applicant population** — PDF
   - `https://prefettura.interno.gov.it/sites/default/files/0/2026-08/2026.08-white-list-ditte-richiedenti-iscrizione.pdf`
   - verified size: **143,930 bytes**
   - SHA-256: `befe7ed054e0cfe9dda48c8dec59f843b569019e40b925d6d5d1fcec19021c7c`
   - valid PDF; **2 pages**.

A successful official-source audit obtained two byte-identical downloads for each attachment and froze the hashes above. A later independent audit attempt timed out while repeating the applicant fetch; that transient retrieval failure does not negate the earlier verified byte-identical capture and does not change any publication-status inference. The approved bytes remain content-addressed by the frozen SHA-256 values above.

The attachments do not expose a document date that can safely be treated as the publication reference date. Until stronger positive evidence exists, the parser therefore records **2026-09-13 as the archive capture date**, not as a claimed official publication date.

## Document structure and parser contract

### Listed DOCX

The frozen listed source contains **10 sector tables**, with non-header row counts `26, 13, 25, 14, 32, 38, 0, 1, 10, 27`, for **186 sector rows**. Every source row has seven physical OOXML cells matching the publication schema: Ragione Sociale; Sede legale; Sede secondaria con rappresentanza stabile in Italia; Codice fiscale/Partita IVA; Data d’iscrizione; Data scadenza iscrizione; Aggiornamento in corso.

Because the same registration is repeated across sector tables, 186 is not a company-observation count. The implemented parser groups only exact cleaned `(name, office, secondary office, identifier_raw, listing_raw, expiry_raw)` tuples, aggregates sector memberships and update evidence, and performs no fuzzy spelling, address, identifier or date merge. This conservative contract yields a **candidate 117 listed-registration observations** from all 186 source rows. The candidate status split is **86 `listed` and 31 `renewal_update_in_progress`**. These counts remain subject to the current byte-pinned parser-validation gate before national integration.

The `Aggiornamento in corso` column is not binary. Across sector rows the raw lexemes are blank 138; `IN AGGIORNAMENTO` 41; `21 gennaio 2026` 1; `25 settembre 2026` 3; `30 luglio 2027` 1; and `“` 2. The parser treats a nonblank value in this explicitly labelled source column as positive update evidence and preserves the raw value; it does not reinterpret the publisher's date or ditto typography into a different legal meaning.

Identifier and date anomalies are preserved raw. Reviewed malformed date lexemes include `10.12.202`, `Dal 10.12.202` and `14 agosto 204`; they are not silently repaired into normalized dates. In particular, the pinned DOCX exposes `Dal 10.12.202` as the listing-date cell for `MAROLLI SRL`, MONFALCONE (GO) Viale S. Marco 13/b, `C.F./P.I. 01189860313`, alongside expiry `10.12.2026`; the parser therefore preserves that exact malformed listing lexeme and leaves its normalized listing date blank, without stripping `Dal` or inventing the missing year digit. The source also contains the valid Italian ordinal typography **`1° giugno 2027`**. Support for the optional ordinal marker was added explicitly after the parser correctly failed closed on that previously unreviewed form; accepting it is source-supported date parsing, not a relaxation of validation. The physical OOXML extraction also exposes one reviewed split-run typography, `2 1 aprile 2026`, for MOVITUB di Giovanni Veneruso & C. SAS. The same source cell's logical text is `21 aprile 2026`, and another source occurrence for the same company/identifier also reads `21 aprile 2026`. The parser therefore maps only this exact reviewed physical lexeme to `2026-04-21`, while preserving the raw source value and keeping the exact physical registration grouping unchanged; no generic whitespace/date repair is enabled. Other examples retained raw include `00001092420312`, `001370303018`, `0237978303` and company-name variants such as `EQUIPE SRL` / `EQUPE SRL`. The pinned DOCX also contains exactly one positively reviewed source row with a blank `Data scadenza iscrizione`: `“ MAROLLI COSTRUZIONI SRL”`, MONFALCONE (GO) Viale San Marco, 13/B, `C.F./P.I. 01218760310`, listing date `29 dicembre 2022` (section 2, source row 9). The parser permits a blank expiry only for this exact reviewed name/office/identifier/listing tuple, preserves the blank raw and normalised expiry, and fails closed on any additional blank-expiry row; publication in the listed series is retained as the only positive status evidence.

### Applicant PDF

The frozen applicant source is a two-page table publication. Coordinate and table-structure probes positively establish **10 distinct 11-digit identifier anchors** in source order:

`01270500315`, `01262160318`, `01190800316`, `01270740317`, `00407990316`, `01268270319`, `00557360310`, `01040110312`, `01170510315`, `01195820319`.

The positively extracted company-name sequence is:

`ITALTRCH SRL`; `METAL X SRL`; `“L’ANTICA RICETTA SRLS”`; `EL.NET SOLUTION SRL`; `C.M.T. SRL`; `FMGDUE SRL`; `SI.ECO:SICUREZZA ED ECOLOGIA SRL`; `SULTAN SRL`; `SVILUPPO SOLARE SRL`; `T-RECYCLE SRL`.

The positively extracted date cells in source order are:

`[blank]`; `24.06.2025`; `21.04.2026`; `17.02.2026`; `17.02.2026`; `[blank]`; `14.04.2026`; `[blank]`; `01.04.2026`; `[blank]`.

The applicant parser binds observations only to these exact identifier anchors and source-order/name/date invariants. It does not infer missing dates, addresses, application events or status from layout gaps. Presence in this official applicant publication is positive evidence only for the archive status `pending`.

## Current candidate output

Subject to the byte-pinned parser-validation gate, the current Gorizia parser candidate is:

- **117 listed-series observations**: 86 `listed`, 31 `renewal_update_in_progress`;
- **10 applicant-series observations**: 10 `pending`;
- **127 observations total**.

These are candidate counts for Gorizia only. They must not be added to the canonical national totals until the full repository tests, national build and public-portal gates pass.

## Integration gate

Before Gorizia may be added to canonical/public output, the following must all hold on the same production candidate:

1. both source bytes match the frozen SHA-256 values above and repeat-fetch identity remains satisfactory or any unavailable independent fetch is explicitly reported without being converted into negative evidence;
2. listed parser invariants remain 10 tables, 186 sector rows, exact section counts, 117 exact registration groups and the reviewed status distribution;
3. applicant parser invariants remain 2 pages and the 10 exact identifier/name/date anchors above;
4. full repository tests pass without weakened validation;
5. the national build, generated registry and browser acceptance pass with explicit Gorizia counts;
6. temporary Gorizia audit/probe workflows and `tmp/gorizia_*` artefacts are removed before a production PR;
7. the final diff against `main` contains only production Gorizia changes and required permanent generic gates.

Until those gates pass, `main` and the public archive remain unchanged.