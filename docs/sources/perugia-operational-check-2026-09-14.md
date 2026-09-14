# Perugia White List operational check — 2026-09-14

## Scope

This note records the current official Prefettura di Perugia White List publication boundary and the completed source-structure audit used to design a fail-closed parser. It does not yet claim parser validation, company-observation loading or national/public integration.

## Official publication surface

- Official landing page: `https://prefettura.interno.gov.it/it/prefetture/perugia/evidenza/white-list`
- The official page was directly fetched twice from GitHub Actions on 14 September 2026. Both responses were byte-identical: 118,868 bytes, SHA-256 `9de2ef541d81f5af9905d999fa95e17fdbf05ec8ef8ddcc8a3ce17f055b935d0`.
- The current official page positively exposes two separately labelled populations, both explicitly dated **3 September 2026**:
  - registered companies: “Elenco delle imprese iscritte alle white list al 3 Settembre 2026”;
  - requesting companies: “Elenco delle imprese richiedenti l'iscrizione alle white list al 3 Settembre 2026”.
- The official page reports `Ultimo aggiornamento` as 4 September 2026.

The source capture was produced by GitHub Actions run `34872232759` (`Perugia source capture`), artifact `perugia-source-capture-1` / artifact id `10359622134`. The temporary capture workflow was removed after the successful transaction; it is not part of the branch's production diff.

## Current registered-company source

- Positive-evidence anchor text: `Elenco delle imprese iscritte alle white list al 3 Settembre 2026`
- Resource URL: `https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-delle-imprese-iscritte-white_list_perugia_0.pdf`
- Media type: `application/pdf`
- Size: **2,279,077 bytes**
- SHA-256: `c9cd39452fb2f751c2b9e105c10ecf0b9e57569006138af7f766d6851748029f`
- PDF pages: **224**
- `pdftotext -layout` lines: 8,221
- Extracted-text SHA-256: `aa4f444cdbeff8829863969a0f3a03970d861ba91ebe010928b525741ac26b2c`
- An independent second GET returned exactly the same byte length and SHA-256.

### Listed structure audit

`pdfplumber` table extraction over the byte-pinned PDF yields **1,909 physical table rows**. The complete finite decomposition is:

- 10 repeated table-header rows;
- 37 completely blank source rows;
- 8 reviewed cross-page continuation fragments;
- **1,854 statutory-section rows** after stitching those continuations.

The ten section boundaries are positively observed at pages 1, 30, 42, 89, 106, 156, 194, 196, 198 and 205. The 1,854 source rows distribute as follows: I 257; II 106; III 402; IV 138; V 441; VI 251; VII 12; VIII 9; IX 66; X 172.

The source status field contains 684 exact `SI` values in `Aggiornamento in corso`; the remaining 1,170 section rows are listed rows without that marker. Under the same observation rule already used for sectioned White Lists — group repeated section memberships only when company identity, source registration/expiry semantics and source status agree — the audited candidate collapses to **1,016 listed-series company observations**: **674 `listed` + 342 `renewal_update_in_progress`**. This is a parser-design denominator, not yet a public count: it remains subject to a successful fail-closed parser-validation run before integration.

The sectioned source contains seven reviewed date-field anomalies, all preserved rather than silently corrected:

- p17 r5, INNOCENZI FRANCO: expiry `1 8/11/2026`;
- p37 r2, MARCA S.R.L.: registration `1°/10/2021`;
- p66 r3, IMPRESA EDILE LONGARI DUE: registration `13/11/20258`;
- p104 r8, WILSIDER SPA: registration `07/04/2026/`;
- p162 r5, BRUNELLI GIAN PAOLO S.R.L.: expiry field `BRUSTENGHI 31/03/2026`;
- p184 r5, SCHIAVOLINI NATASCIA: a visible source-column corruption places `Autotrasporto per conto di terzi` in the registration-date column and shifts `02/10/2025` and `01/10/2026` one column to the right; the parser must not reinterpret those shifted values as registration/expiry dates;
- p199 r8, RISTORANTE ALBERGO LE MURA S.R.L.: a second source row has both registration and expiry fields blank.

There are 37 section rows whose identifier cell is not itself positive evidence for a strict 11-digit VAT/fiscal identifier or 16-character fiscal code after whitespace-only joining. Those raw identifier cells must remain preserved, but no identifier may be invented or corrected from them. Three listed rows have an empty identifier cell. The source therefore requires conservative identifier extraction rather than generic typo repair.

## Current requesting-company source

- Positive-evidence anchor text: `Elenco delle imprese richiedenti l'iscrizione alle white list al 3 Settembre 2026`
- Resource URL: `https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-delle-imprese-richiedenti-l-iscrizione_0.pdf`
- Media type: `application/pdf`
- Size: **1,897,032 bytes**
- SHA-256: `003e2ee6614302b1a1f8a504baae2b0c5d38752c70cfb509f693e1b4c1374f14`
- PDF pages: **184**
- `pdftotext -layout` lines: 7,840
- Extracted-text SHA-256: `ef6fe093d28d3725bb517387b7b823e70f0b920fe0f03d6b1978513ac71836b5`
- An independent second GET returned exactly the same byte length and SHA-256.

### Applicant structure audit

The applicant PDF yields **1,292 physical table rows**. The exhaustive page/row audit identifies:

- 1 table-header row;
- 23 completely blank source rows;
- 54 reviewed page-leading continuation fragments;
- one reviewed p6 r6 fragment whose activity/outcome text belongs to the following page's GALLANO S.R.L. row;
- one genuine source row at p160 r8 whose company-name cell is blank but whose address, identifier, activities and application date are populated;
- **1,213 logical applicant-series rows** after stitching only those positively identified continuations.

The source must **not** be mapped mechanically to `pending`. Its `esito` column contains a large historic outcome population. The audited row-level distribution is:

- **1,036 explicit completed positive outcomes** (`Iscritta/Iscrizione in data …` or a completed `Rinnovo …` outcome), which should map to `listed` rather than to an ongoing-renewal class;
- **176 rows with no displayed outcome**, which can map to `pending` as source observations;
- **1 row with only the bare outcome value `25/03/2026`**, which remains `other_or_unknown` because the source does not label what that date represents.

Application-date typography is also finite and reviewed. Seven logical rows have an empty application-date field. The non-standard populated values are: `04.01.2023` (a parseable dot-separated calendar date), `0389625054 9` (identifier-like text occupying the date cell), `07/03/20225` (one source typo), and `1°/04/2025` (three rows). The latter three non-standard classes must be preserved raw and left without an inferred normalised application date. Three positive outcome strings also lack a safely parseable labelled date (`Rinnovo iscrizione in data`, `Iscritta in data 1°/10/2021`, `Iscritta in data 1°/12/2025`); their positive outcome status is explicit, while the normalised decision date must remain empty.

After continuation stitching, 1,186 of 1,213 logical applicant rows contain positive evidence for a strict identifier under whitespace-only joining; the remaining 27 must retain only their raw identifier field unless stronger source evidence is available.

## Parser-design boundary

The source-structure audit now establishes finite denominators and exception populations sufficient to implement a Perugia-specific fail-closed parser. The intended parser gate must bind to the exact two source SHA-256 values above and assert at minimum:

- listed: 224 pages; 1,909 physical rows; 1,854 section rows; the exact ten section denominators; 1,016 grouped candidate observations; 674 listed + 342 renewal/update-in-progress observations; seven reviewed date anomalies; strict identifier handling;
- applicants: 184 pages; 1,292 physical rows; 1,213 logical rows; the exact continuation population; 1,036 listed + 176 pending + 1 other/unknown outcome classification; the finite application-date exception population; one source row with an unpublished company name;
- no generic date repair, identifier repair, de-duplication or status inference beyond those source-bound rules.

Parser implementation, semantic tests, parser-family/source-registry binding, company-observation loading and national/public integration are **not yet completed** at this checkpoint. No Perugia record is public from this branch. No `NOT_PUBLISHED` or completeness conclusion is inferred from search failure.