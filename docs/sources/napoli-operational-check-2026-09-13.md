# Napoli White List operational check — 2026-09-13

## Scope

Expansion work for the current public White List publications of the Prefettura di Napoli. This note records only source-positive facts observed from official publication surfaces and byte-level capture. Public integration remains gated until the fail-closed parser is validated.

## Current official publication surfaces

The Prefettura publishes the two required populations on distinct official pages:

- listed companies: `https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-iscritte`;
- applicant companies: `https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-richiedenti`.

A live retrieval on 13 September 2026 exposed current attachments dated 11 September 2026:

- listed: `IMPRESE ISCRITTE WHITE-LIST 11_9_2026`, resource `https://prefettura.interno.gov.it/sites/default/files/79/2026-09/whitelistprefnapoli_11_settembre_26.pdf`;
- applicants: `WHITE-LIST RICHIEDENTI 11_9_2026`, resource `https://prefettura.interno.gov.it/sites/default/files/79/2026-09/ditterichiedenti_wl_11_settembre_26.pdf`.

The applicant page positively states that the published applicant list contains the references of all firms that submitted a formal request for White List registration. The listed page positively identifies its attachment as the list of firms registered in the Prefettura's White List. No population status is inferred from search absence or retrieval failure.

## Byte-level capture

The source-audit gate repeated each direct official-resource fetch twice. Both publications were valid `%PDF-1.7` payloads and each pair was byte-identical:

- listed: 3,081,398 bytes; SHA-256 `93a8635c0bd9b00587f9cc60c52752061bd239a7c16cb34b64a11e495a0ab4be`; 60 pages;
- applicants: 3,566,448 bytes; SHA-256 `053be2500b07a7da536c344aede12084dde9b7cf28b4717af99764cbd05e7e6b`; 215 pages.

`pdfinfo` and layout-text extraction succeeded for both byte-pinned publications. The extracted source itself is dated `Napoli, 11 settembre 2026`; the applicant document states that it covers complete applications received through 9 September 2026.

## Full-layout validation

A full-document audit used the pinned bytes and inspected every page through `pdfplumber` table extraction.

- listed: exactly one table on each of 60 pages; every extracted table row has nine cells; the numbered source rows form the exact, gap-free, non-duplicated sequence 1–2,259;
- applicants: exactly one table on each of 215 pages; every extracted table row has eight cells; the numbered source rows form the exact, gap-free, non-duplicated sequence 1–2,571.

Accordingly **2,259 listed source observations and 2,571 applicant source observations are frozen as the current source-row denominators**. These are not yet promoted as public-record counts until the parser and national integration gates pass.

## Semantic audit and spatial reconstruction

Plain table extraction exposed a small number of vertically misassigned cells. The first spatial reconstruction used table x-column geometry and numbered-row anchor midpoints. That method was useful diagnostically but is no longer accepted as the row-ownership primitive because a later audit against the physical PDF table-row boundaries demonstrated systematic cross-row contamination in long cells.

A 14 September 2026 row-bound audit therefore compared every numbered observation with the actual physical `pdfplumber` table-row geometry while retaining the same pinned bytes, x-column geometry and exact ordinal sequences. The physical table representation preserves materially more complete row ownership than the earlier inter-anchor midpoint reconstruction, but a few glyph lines straddle a horizontal border. Those exceptional fragments are now handled only through exact reviewed bindings rather than a generic cross-row concatenation rule.

### Listed publication

The physical-row reconstruction yields all **2,259** numbered observations. Relative to the earlier midpoint reconstruction, **89 rows have a difference in one or more core cells**; inspection shows the midpoint method commonly truncated a long company name and prefixed the remainder to the following company. The physical-row representation is therefore the preferred basis for identity and core-field ownership, subject to exact exceptional review where a printed continuation visibly crosses a numbered-row boundary.

The physical outcome/update column contains **1,467 nonblank cells** and therefore 792 blank cells. This supersedes the earlier provisional midpoint count of 1,474 nonblank cells. Of the 1,467 physical nonblank values:

- **1,419** start with the source wording `iscrizione in aggiornamento`;
- **48** are other source-positive values requiring reviewed semantics.

There are **27 rows whose outcome assignment differs between midpoint and physical-row reconstruction**. The differences show why midpoint ownership is unsafe. For example, complete judicial-administration notes belong physically to `AMBIENTE CAMPANIA S.R.L.`, `AURORA S.R.L.`, `COSTRUZIONI GENERALI SUD S.R.L.` and `FONTANA DI FONTANA FRANCESCO S.R.L.`, while the following numbered rows are physically blank in the outcome column. Likewise, `LEONIDA COOPERATIVA SOCIALE` physically carries `DINIEGO DI ISCRIZIONE PROVVEDIMENTO PROT. 0106177 21/03/2024`, whereas the midpoint method had distributed fragments across neighbouring rows.

The 48 non-prefix outcomes are not one semantic class. They include, among other positively observed source wordings:

- collaborative-prevention measures under art. 94-bis;
- judicial control/admission under art. 34-bis;
- judicial administration notes;
- interdittiva and diniego language;
- revocation language;
- a Council of State judgment reference;
- update variants not beginning with the exact canonical phrase, including `in aggiornamento per variazione societaria` and the source typo `iscrizione in aggiornametnto`.

Accordingly a blanket nonblank→`renewal_update_in_progress` rule remains prohibited. Exact positive update wording may support `renewal_update_in_progress`; explicit diniego/interdittiva/revocation evidence must follow the repository's reviewed adverse/cancellation semantics; control, administration, collaborative-prevention and judgment notes require conservative reviewed treatment with the raw source wording preserved.

Identifier evidence remains 2,068 eleven-digit values, 167 sixteen-character alphanumeric fiscal-code-shaped values and 24 other raw values. The 24 noncanonical values are preserved as raw-only evidence rather than padded or otherwise repaired.

### Applicant publication

The physical-row reconstruction yields all **2,571** numbered observations. It exposes **44 physically nonblank `ESITO` cells** rather than the earlier midpoint count of 41. The difference is fully localised: **41 values contain explicit diniego/interdittiva wording and three additional cells contain continuation text printed across or immediately below the preceding adverse outcome**.

The three reviewed continuation bindings are now frozen as follows:

1. row 511 `CONSORZIO STABILE GOSERVICE S.C.A.R.L.` carries `DINIEGO DI ISCRIZIONE Provv. 0135353 del 05/07/2017 confermato con` and absorbs the exact row-512 fragment `provvedimento`; row 512 `CONSORZIO STABILE ICON S.C. A R.L.` has no independent adverse outcome;
2. row 879 `EDIL SAN MARCO SRL` carries `DINIEGO DI ISCRIZIONE Provv. 0132224 del 30/06/2017 confermato da` and absorbs the exact fragment `provv. 399217 del`; row 880 `EDIL SANT'ANNA S.R.L.` has no independent adverse outcome. The page-74 audit shows that `provv.`, `399217` and `del` are the final words in the entire outcome column for that source entry: their glyph box straddles the horizontal 879/880 border and there is no later outcome-column text before subsequent rows. The source therefore genuinely ends at `del`; no missing date is reconstructed or fabricated;
3. row 1259 `GIUGA ECOLOGY S.R.L.` carries `Provvedimento interdittivo prot.193574 dell'11/05/2026 sospeso con` and absorbs the exact row-1260 fragment `ordinanza TAR`; row 1260 `GIUGLIANO HOLDING S.R.L.` has no independent adverse outcome.

The earlier physical-vs-midpoint comparison reported four adjacent company-name difference pairs. Exact row-bound review resolves them without a generic spill heuristic:

- **402/403 is a midpoint-only false alarm**. Physical table ownership is already coherent: row 402 is `CEM.AR. 86 - SOCIETA' COOPERATIVA DI PRODUZIONE E LAVORO A RESPON SABILITA' LIMITATA`; row 403 is `CEMENTI MOCCIA SPA`. No cross-row rebinding is permitted there.
- At **793/794**, the source prints `S.R.L.` across the horizontal border as the terminal legal-form fragment of row 793. The reviewed names are therefore `ECOLOGIA LA VESUVIANA S.R.L.` for row 793 and `ECOLOGIA SAN VINCENZO S.A.S. DI MIELE EMILIA` for row 794.
- At **1209/1210**, the border fragment `S.R.L.` belongs to row 1209. The reviewed names are `GENERAL COSTRUZIONI S.R.L.` for row 1209 and `GENERAL SERVICE S.R.L.` for row 1210.
- At **1226/1227**, the border fragment `SERVIZI S.R.L.S.` completes row 1226. The reviewed names are `GESTIONE APPALTI E SERVIZI S.R.L.S.` for row 1226 and `GESTIONE HOTEL S.R.L.` for row 1227.

These are exact ordinal-and-text bindings. Any source drift in either side of a reviewed pair must fail closed; the production parser must not generalise them into a fuzzy cross-row repair rule.

Identifier evidence remains 2,298 eleven-digit values, 261 sixteen-character alphanumeric values and 12 raw-only values. The raw-only set includes ten-digit values, `CHE-101,989.651`, the source value `011117840767` and `ZZVLR78S46F839J`; no alternative identifier is fabricated.

## Conservative semantic boundary

The listed population is positively identified by its dedicated publication, but membership evidence and current legal/status wording remain separate. Blank update/outcome text can support ordinary listed treatment. Source-positive update wording can support `renewal_update_in_progress`. Interdittiva/diniego/revocation evidence must not be collapsed into update status. Judicial control/administration, collaborative-prevention measures and other special notes require conservative reviewed treatment and raw evidence retention.

Applicant membership is positively established by the dedicated applicant publication. Rows with genuinely blank `ESITO` after exact continuation resolution are candidates for `pending`. Explicit diniego/interdittiva rows are candidates for the repository's reviewed adverse status. Continuation-only rows must not acquire a status from a fragment belonging to the preceding row.

## Remaining gates

Before admission to publication configuration the expansion still must establish:

1. exact fail-closed continuation bindings for the three reviewed applicant outcome spillovers and the three reviewed company-name border spillovers, with the 402/403 false alarm explicitly protected from rebinding;
2. a fail-closed parser family bound to both pinned SHA-256 values and the 11 September 2026 source edition;
3. exact parser status distributions, identifier coverage and exception counters across the complete sources, including reviewed semantics for the 48 listed special outcomes and 41 true applicant adverse outcomes;
4. parser semantic tests and repository CI;
5. canonical/public national integration and permanent browser/Pages gates.

No national-count increment or public-export state is asserted until those gates pass.
