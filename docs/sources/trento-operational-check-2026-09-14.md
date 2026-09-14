# Trento White List operational check — 2026-09-14

## Scope

This note records the current official Commissariato del Governo per la Provincia di Trento White List publication boundary, the byte-level source provenance and the finite parser denominators established before national integration. The public-source treatment is evidence-first and remains separate from canonical hosted-database integration and durable-evidence verification.

## Official publication surface

The official Trento White List publication positively separates the registered-company and requesting-company populations. The two current official pages were revalidated on 14 September 2026:

- registered companies: `https://prefettura.interno.gov.it/it/prefetture/trento/white-list-elenco-imprese-iscritte`;
- requesting companies: `https://prefettura.interno.gov.it/it/prefetture/trento/white-list-elenco-imprese-richiedenti`.

The registered-company page currently exposes **“ELENCO IMPRESE ISCRITTE ALL'11 SETTEMBRE 2026”** and reports page update time 11 September 2026 at 11:04. The requesting-company page exposes **“ELENCO IMPRESE RICHIEDENTI AL 10 SETTEMBRE 2026”** and reports page update time 10 September 2026 at 13:47. These are separate positive population anchors; the applicant population is not inferred from absence or search failure.

A temporary GitHub Actions capture gate performed two independent GETs of each official attachment on 14 September 2026. Each pair was byte-identical, both resources had a valid PDF magic header, and `pdfinfo` confirmed the page counts below. Initial byte capture completed successfully in run `34890395921`. The exhaustive normalised finite-source audit then completed successfully in run `34891229900`. The temporary workflow remains diagnostic only and must be removed before any production PR.

## Current registered-company source

- Positive-evidence anchor: `ELENCO IMPRESE ISCRITTE ALL'11 SETTEMBRE 2026`
- Reference date: **2026-09-11**
- Resource URL: `https://prefettura.interno.gov.it/sites/default/files/86/2026-09/imprese-iscritte-11-settembre-2026.pdf`
- Media type: `application/pdf`
- Size: **7,663,549 bytes**
- SHA-256: `b831570c01220b8709ebf9c4dbdfe856aba37a21c46353cf7bc9eedb5965c8af`
- PDF pages: **289**
- The second independent GET returned the same bytes and SHA-256.

### Finite table boundary

The exact PDF extraction boundary is now frozen:

- **3,208 physical table rows**;
- raw table widths: **3,169 seven-column rows + 39 nine-column rows**;
- page geometry: **281 one-table pages, 7 two-table pages and one zero-table page**;
- two-table pages: `69, 116, 147, 244, 246, 248, 261`;
- page 289 is the sole zero-table trailing page;
- **10 source headers**, one for each statutory White List section;
- **6 blank table rows**;
- **172 continuation fragments**, all reviewed as source continuation rows and stitched column-by-column into the preceding logical row;
- **3,020 logical statutory-section rows** after stitching.

The 39 nine-column rows are a source-table geometry artefact in which the registration-date region is split across three cells. The parser accepts only that reviewed shape: at most one of those three cells may be nonblank and the remaining source columns must align exactly. It then maps the single positive registration-date value back to the seven-column logical schema. This is a geometry normalisation, not a repair of source content.

Several section transitions occur inside a PDF page. Section assignment is therefore table-aware rather than page-only. The frozen section starts are `(page, table)`: `I=(1,1)`, `II=(50,1)`, `III=(69,2)`, `IV=(116,2)`, `V=(147,2)`, `VI=(213,1)`, `VII=(244,2)`, `VIII=(246,2)`, `IX=(248,2)`, `X=(261,2)`.

The exact logical section-row denominators are:

| Section | Source rows |
| --- | ---: |
| I | 571 |
| II | 198 |
| III | 499 |
| IV | 322 |
| V | 700 |
| VI | 308 |
| VII | 9 |
| VIII | 17 |
| IX | 105 |
| X | 291 |
| **Total** | **3,020** |

### Listed status semantics and public-observation grouping

`AGGIORNAMENTO IN CORSO` is an explicit source marker. It is not reconstructed from expiry dates. Across the complete 3,020 section-row population the exact source-row distribution is:

- **1,507 `listed`** source rows with blank update marker;
- **1,513 `renewal_update_in_progress`** source rows with the explicit update marker;
- no other status typography.

The source repeats the same company across statutory sections. Public observations are therefore grouped conservatively by the positively extracted identifier evidence (or, only where no valid identifier exists, a name fallback), raw listing date, raw expiry date and source status. Every source membership and every raw name/address/identifier variant remains attached to the resulting record. This grouping produces **1,366 listed-series public observations**:

- **699 `listed`**;
- **667 `renewal_update_in_progress`**.

The group-size distribution across source section memberships is `{1: 696, 2: 234, 3: 160, 4: 114, 5: 91, 6: 37, 7: 29, 8: 5}`. Thirteen groups contain benign raw text variation across repeated section memberships, such as punctuation, spacing, `/` versus blank secondary-office notation or minor source spelling variation. Those variants are preserved as source evidence and are not silently normalised away.

### Reviewed listed-source anomalies

The exhaustive audit identified exactly one non-standard date cell and no chronology inversion:

- `(page 274, table 1, row 8)`, `F.I.R. S.A.S. DI F.I.R. SERVIZI S.R.L. SOCIETA’ BENEFIT`: listing date raw `14.04.206`. The raw value is preserved and the normalised listing date remains blank; no year is inferred.

Identifier treatment is similarly positive-evidence only. Exactly four listed section rows do not contain a single strict whole-cell 11-digit or 16-character identifier:

1. `(221,1,13)` `BUTTERINI PIETRO TRASPORTI S.R.L.` — raw `006281590229`; this is a 12-digit value and is **not repaired**, so the normalised identifier list is empty.
2. `(250,1,6)` `ASSOCIAZIONE SCUOLA MATERNA ROMANI – DE MOLL ...` — raw contains both `P.IVA 02785350220` and `C.F.85000750225`; both positively visible identifiers are retained.
3. `(260,1,4)` `SCUOLA MATERNA DON VITTORIO PISONI` — raw contains `C.F.84002830226` and `P.IVA 01157050228`; both are retained.
4. `(280,1,5)` `MODOLO IMPIANTI S.R.L.` — raw contains `P.I. 01731370225` and `C.F. 01191130218`; both are retained.

No identifier is reconstructed from a malformed value.

## Current requesting-company source

- Positive-evidence anchor: `ELENCO IMPRESE RICHIEDENTI AL 10 SETTEMBRE 2026`
- Reference date: **2026-09-10**
- Resource URL: `https://prefettura.interno.gov.it/sites/default/files/86/2026-09/imprese-richiedenti-10-settembre-2026.pdf`
- Media type: `application/pdf`
- Size: **384,118 bytes**
- SHA-256: `9f36797e3e11834c979f9b5f5d58d693e19fa2456c69ce5859628d4e56a056c0`
- PDF pages: **22**
- The second independent GET returned the same bytes and SHA-256.

The finite applicant boundary is:

- **117 physical table rows**;
- seven columns throughout;
- one header at `(1,1,1)`;
- one blank row at `(19,1,1)`;
- **17 reviewed continuation fragments**;
- **98 logical applicant rows** after stitching;
- **98/98 rows with one strict positive identifier**, all 98 identifiers unique;
- **98/98 blank `Esito` values** over the complete finite source population.

Because the complete current applicant population has been audited rather than sampled, all **98 applicant observations are defensibly classified `pending`**. This classification is based on the current source’s complete blank `Esito` field population, not on an assumption about what applicant lists usually contain.

All 98 rows contain explicit statutory section tokens in the activity field. Source-membership occurrences are: `I=34`, `II=10`, `III=16`, `IV=19`, `V=32`, `VI=12`, `VIII=3`, `IX=14`, `X=16`. The parser preserves the complete raw activity field and accepts activity splitting only when every source character is accounted for by chunks terminating in a positive `(Sezione …)` marker.

Exactly one applicant date cell has reviewed additional source text:

- `(12,1,3)` `ROMANI DE MOLL S.R.L. IMPRESA SOCIALE` — raw `29.06.2026 (integrata il 02.07.2026)`. The primary application date is the explicitly printed `29.06.2026`; the explicitly printed integration date `02.07.2026` is kept separately in source fields. The full raw cell is preserved.

## Candidate publication boundary

Subject to parser validation against the exact byte-pinned PDFs, Trento contributes a candidate **1,464 public observations**:

- **1,366 listed-series observations**;
- **98 applicant-series observations**.

No Trento record is yet part of the national public registry. Against the current live national baseline of 40,734 observations, the arithmetic candidate after a future successful national integration would be **42,198 observations**. That number is a candidate denominator only, not a live or integrated count.

## Control boundary

The production parser must continue to fail closed on source SHA-256, page count, table geometry, row denominators, section boundaries, continuation populations, status typography, anomaly populations and grouped observation counts. A source update requires a new reviewed boundary rather than permissive parsing.

No `NOT_PUBLISHED` state, legal status or completeness claim is inferred from failed search. Public-source validation does not promote either `canonical_integration_validated` or `durable_evidence_verified`; those remain separate controls.