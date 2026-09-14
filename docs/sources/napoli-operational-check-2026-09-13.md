# Napoli White List operational check — 2026-09-13

## Scope

Expansion work for the current public White List publications of the Prefettura di Napoli. This note records only source-positive facts observed from official publication surfaces and byte-level capture. The fail-closed parser and semantic regression suite are now validated on the pinned 11 September 2026 editions; public national integration remains a separate gate.

## Current official publication surfaces

The Prefettura publishes the two required populations on distinct official pages:

- listed companies: `https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-iscritte`;
- applicant companies: `https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-richiedenti`.

A live retrieval on 13 September 2026 exposed current attachments dated 11 September 2026:

- listed: `IMPRESE ISCRITTE WHITE-LIST 11_9_2026`, resource `https://prefettura.interno.gov.it/sites/default/files/79/2026-09/whitelistprefnapoli_11_settembre_26.pdf`;
- applicants: `WHITE-LIST RICHIEDENTI 11_9_2026`, resource `https://prefettura.interno.gov.it/sites/default/files/79/2026-09/ditterichiedenti_wl_11_settembre_26.pdf`.

The applicant page positively states that the published applicant list contains the references of all firms that submitted a formal request for White List registration. The listed page positively identifies its attachment as the list of firms registered in the Prefettura's White List. No population status is inferred from search absence or retrieval failure.

## Byte-level capture

The source-audit and parser-validation gates repeated each direct official-resource fetch twice. Both publications were valid `%PDF-1.7` payloads and each pair was byte-identical:

- listed: 3,081,398 bytes; SHA-256 `93a8635c0bd9b00587f9cc60c52752061bd239a7c16cb34b64a11e495a0ab4be`; 60 pages;
- applicants: 3,566,448 bytes; SHA-256 `053be2500b07a7da536c344aede12084dde9b7cf28b4717af99764cbd05e7e6b`; 215 pages.

`pdfinfo` and layout-text extraction succeeded for both byte-pinned publications. The extracted source itself is dated `Napoli, 11 settembre 2026`; the applicant document states that it covers complete applications received through 9 September 2026.

## Full-layout validation

A full-document audit used the pinned bytes and inspected every page through `pdfplumber` table extraction.

- listed: exactly one table on each of 60 pages; every extracted table row has nine cells; the numbered source rows form the exact, gap-free, non-duplicated sequence 1–2,259;
- applicants: exactly one table on each of 215 pages; every extracted table row has eight cells; the numbered source rows form the exact, gap-free, non-duplicated sequence 1–2,571.

Accordingly **2,259 listed source observations and 2,571 applicant source observations are frozen as the current source-row denominators**, for **4,830 source observations in total**. These denominators have now been reproduced by the fail-closed parser; they are not yet asserted as national public-record counts because national integration has not run.

## Semantic audit and spatial reconstruction

Plain table extraction exposed a small number of vertically misassigned cells. The first spatial reconstruction used table x-column geometry and numbered-row anchor midpoints. That method was useful diagnostically but is no longer accepted as the row-ownership primitive because a later audit against the physical PDF table-row boundaries demonstrated systematic cross-row contamination in long cells.

A 14 September 2026 row-bound audit therefore compared every numbered observation with the actual physical `pdfplumber` table-row geometry while retaining the same pinned bytes, x-column geometry and exact ordinal sequences. The physical table representation preserves materially more complete row ownership than the earlier inter-anchor midpoint reconstruction, but a few glyph lines straddle a horizontal border. Those exceptional fragments are handled only through exact reviewed bindings rather than a generic cross-row concatenation rule.

### Listed publication

The physical-row reconstruction yields all **2,259** numbered observations. Relative to the earlier midpoint reconstruction, **89 rows have a difference in one or more core cells**; inspection shows the midpoint method commonly truncated a long company name and prefixed the remainder to the following company. The physical-row representation is therefore the preferred basis for identity and core-field ownership, subject to exact exceptional review where a printed continuation visibly crosses a numbered-row boundary.

The physical outcome/update column contains **1,467 nonblank cells** and therefore 792 blank cells. Of the 1,467 physical nonblank values:

- **1,419** start with the source wording `iscrizione in aggiornamento`;
- **48** are other source-positive values requiring reviewed semantics.

The 48 non-prefix outcomes are not one semantic class. They include collaborative-prevention measures under art. 94-bis, judicial control/admission under art. 34-bis, judicial administration notes, interdittiva and diniego language, revocation language, a Council of State judgment reference and update variants not beginning with the exact canonical phrase. A blanket nonblank→`renewal_update_in_progress` rule is therefore prohibited.

The validated parser freezes the listed status distribution at:

- **792** `listed`;
- **1,423** `renewal_update_in_progress`;
- **12** `rejected_or_denied`;
- **3** `cancellation_related`;
- **29** `other_or_unknown`.

Identifier evidence is **2,068** eleven-digit values, **167** sixteen-character alphanumeric fiscal-code-shaped values and **24** other raw values. The 24 noncanonical values are preserved as raw-only evidence rather than padded or otherwise repaired.

Seven source-positive expiry cells are non-calendar validity terms referring to the duration of judicial administration. They are bound exactly by ordinal, company and raw source typography; `observed_expiry_date` remains empty rather than inventing a calendar date. One listed registration date is malformed in the source: ordinal 556, `DE LISIO COSTRUZIONI SRL`, identifier `04518100633`, raw value `14/0319`. The raw value is retained and `observed_listing_date` remains empty; the parser does not infer `14/03/2019`.

Four reviewed section-field anomalies are likewise source-bound. Invalid typography is not repaired into a different legal section: only positively valid tokens are retained and the original source text remains in provenance.

### Exact page-bottom recovery

A separate audit identified **17 listed page-bottom rows** where `pdfplumber`'s table grid omits the company cell and, on the last five affected pages, sometimes also the location and date cells even though the words are visibly present inside the same physical numbered row. The complete affected ordinal set is:

`1620, 1659, 1698, 1735, 1775, 1816, 1854, 1890, 1923, 1965, 2004, 2036, 2074, 2117, 2157, 2200, 2239`.

The audit re-fetched the listed PDF twice, required byte identity, exact size and approved SHA-256, then recovered each physical row using stable page-column bounds and word centroids. The production parser does **not** apply a generic page-bottom repair. Instead it freezes both the exact truncated `table.extract()` tuple and the exact independently recovered row for every affected ordinal. Parsing fails closed if the observed blank-row population changes, if any truncated tuple changes, or if the source bytes change.

Representative recovered rows include:

- 1620: `NEW HOUSE COSTRUZIONI DI MURDACA LUCA I.I.`, Napoli, `MRDLCU71A22F839W`, sections III–V, listing `19/10/16`, expiry `23/05/23`;
- 2074: `T-CYCLE INDUSTRIES S.R.L.`, Napoli, `07789361214`, section X, listing `12/06/23`, expiry `09/09/25`;
- 2157: `TRASPORTI F.C. S.R.L.S.`, Casoria, `08282961211`, section VI, listing `08/03/22`, expiry `13/11/25`;
- 2200: `VELTRANS DI VELLUSO GIOVANNI`, Giugliano in Campania, `VLLGNN80T20F839S`, section VI, listing `27/10/17`, expiry `09/12/26`;
- 2239: `WORK IN PROGRESS SRL`, Melito di Napoli, `08491491216`, section IV, listing `22/10/19`, expiry `16/09/22`.

This recovery is treated as reviewed extraction evidence, not semantic inference.

### Applicant publication

The physical-row reconstruction yields all **2,571** numbered observations. It exposes **44 physically nonblank `ESITO` cells**: **41 values contain explicit diniego/interdittiva wording and three additional cells contain continuation text printed across or immediately below the preceding adverse outcome**.

The three reviewed continuation bindings are frozen as follows:

1. row 511 `CONSORZIO STABILE GOSERVICE S.C.A.R.L.` carries `DINIEGO DI ISCRIZIONE Provv. 0135353 del 05/07/2017 confermato con` and absorbs the exact row-512 fragment `provvedimento`; row 512 `CONSORZIO STABILE ICON S.C. A R.L.` has no independent adverse outcome;
2. row 879 `EDIL SAN MARCO SRL` carries `DINIEGO DI ISCRIZIONE Provv. 0132224 del 30/06/2017 confermato da` and absorbs the exact fragment `provv. 399217 del`; row 880 `EDIL SANT'ANNA S.R.L.` has no independent adverse outcome. The page-74 audit confirms that the official source genuinely ends at `del`; no missing date is reconstructed;
3. row 1259 `GIUGA ECOLOGY S.R.L.` carries `Provvedimento interdittivo prot.193574 dell'11/05/2026 sospeso con` and absorbs the exact row-1260 fragment `ordinanza TAR`; row 1260 `GIUGLIANO HOLDING S.R.L.` has no independent adverse outcome.

The reviewed company-name border bindings are 793/794, 1209/1210 and 1226/1227. Pair 402/403 is explicitly protected as a midpoint-only false alarm and is not rebound. These are exact ordinal-and-text bindings; any source drift fails closed.

The validated applicant status distribution is:

- **2,530** `pending`;
- **40** `rejected_or_denied`;
- **1** `other_or_unknown`.

The single `other_or_unknown` row is 1259, because the source says that the interdittiva was subsequently suspended by TAR order; it is not forced into a definitive adverse status.

Identifier evidence is **2,298** eleven-digit values, **261** sixteen-character alphanumeric values and **12** raw-only values. No alternative identifier is fabricated. Five reviewed section-field anomalies are source-bound with the same positive-token-only rule used for listed rows.

## Parser validation checkpoint

`napoli_tables.py` parser version 2 is bound to the two approved SHA-256 values, exact page counts, exact ordinal ranges and the reviewed exception populations above. It fails closed on source-byte drift, table/page/count drift, unreviewed date typography, unreviewed section values, changed page-bottom extraction, changed continuation/name boundaries and unexpected outcome populations.

The full Napoli parser-validation workflow completed successfully on 14 September 2026 after independently downloading each official PDF twice. It verified byte identity, exact sizes and hashes, parsed **2,259 listed + 2,571 applicants**, reproduced the exact status distributions and exception counters, checked representative page-bottom recoveries, retained raw `14/0319` with no inferred date, and required **4,830 distinct record locators**. Repository CI is also green with permanent semantic regression tests covering these fail-closed boundaries.

## Conservative semantic boundary

The listed population is positively identified by its dedicated publication, but membership evidence and current legal/status wording remain separate. Blank update/outcome text can support ordinary listed treatment. Source-positive update wording can support `renewal_update_in_progress`. Interdittiva/diniego/revocation evidence must not be collapsed into update status. Judicial control/administration, collaborative-prevention measures and other special notes require conservative reviewed treatment and raw evidence retention.

Applicant membership is positively established by the dedicated applicant publication. Rows with genuinely blank `ESITO` after exact continuation resolution are candidates for `pending`. Explicit diniego/interdittiva rows use the repository's reviewed adverse status. Continuation-only rows do not acquire a status from a fragment belonging to the preceding row.

## Remaining gates

The source/parser stage is complete for the pinned 11 September 2026 edition. Before Napoli can be admitted to the public national registry, the expansion still must:

1. reconcile the long-running Napoli branch with current `main` without mixing other Prefecture work into the expansion diff;
2. update the source-registry edition metadata from the older provisional Napoli edition to the verified 11 September 2026 sources;
3. resolve parser-family/source-series registry metadata using the repository's structural-fingerprint rules rather than inventing a fingerprint or weakening registry validation;
4. bind the two validated source series into the publication configuration and run the actual national build, treating its generated counts as authoritative rather than pre-computing a public total;
5. remove diagnostic workflows and temporary audit artefacts before review;
6. pass permanent repository, national-registry, browser, official-source-link and Pages gates before merge/live verification.

No national-count increment or public-export state is asserted until those gates pass.
