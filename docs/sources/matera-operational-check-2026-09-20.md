# Matera White List operational source check — 20 September 2026

## Scope

This note records the first-party evidence reviewed for adding the Prefettura di Matera to the public multi-Prefecture White List registry. The observation boundary is the current edition positively exposed by the Prefettura landing page on 20 September 2026. Both published series are labelled as updated to **31 July 2026**. The verification date is not interpreted as a company decision date or other legal-effect date.

## Official landing page

Official page: `https://prefettura.interno.gov.it/it/prefetture/matera/evidenza/white-list`

The page positively exposes two distinct resources:

- **Elenco imprese iscritte** — `Elenco imprese iscritte (aggiornato al 31 Luglio 2026)`;
- **Elenco richieste iscrizioni** — `Elenco richieste iscrizioni e richieste aggiornamento (aggiornato al 31 Luglio 2026)`.

The landing page reports `Lunedì 3 Agosto 2026, ore 12:24` as its last update. Applicant coverage is therefore based on positive official publication evidence. It is not inferred from search results, an absent attachment, or failure to retrieve another source.

## Byte-pinned resources

### Listed companies

Resource: `https://prefettura.interno.gov.it/sites/default/files/54/2026-08/iscritte-luglio-2026.xlsx`

Two independent cache-bypassed GETs on 20 September 2026 both returned HTTP 200 with exactly **25,946 bytes** and SHA-256:

`4a2a3fad0711f9d3c159d78c93210983b9f1699c2810d8154b60d8fc5d958d3f`

The workbook contains one sheet, `DPP1059056-20260722-WLIscrizion`, with an observed shape of **249 rows × 10 columns**: one header row and **248 source observations**. The sheet name contains a 22 July 2026 internal date marker, while the official landing label states that the published list is updated to 31 July 2026. Both facts are retained as provenance; the internal sheet-name marker is not promoted to the edition reference date.

All 248 source rows carry the explicit status `ISCRITTA`, yielding **248 `listed` observations**. Structured identifier coverage is **248/248**. Listing-date and expiry-date coverage are each **248/248**. Identifier and date cells frequently use the literal Excel-formula wrapper `="…"`; the parser removes only that exact wrapper and does not otherwise repair source text.

One reviewed row contains the note `Art. 34 bis d.lgs 159/2011 - Controllo giudiziario` repeated across spill columns, with one exact source cell carrying the same text followed by a final full stop. The parser preserves the exact observed note variants and accepts multiple variants only for this reviewed two-string punctuation family. Any different multi-note disagreement fails closed rather than being normalised fuzzily.

### Applicant and update-request companies

Resource: `https://prefettura.interno.gov.it/sites/default/files/54/2026-08/elenco-richiedenti-iscrizione.xlsx`

Two independent cache-bypassed GETs on 20 September 2026 both returned HTTP 200 with exactly **16,013 bytes** and SHA-256:

`e4dae926800d1c513e1274b8ae45267337987eaa5b62b1581cbbcc56f6da898c`

The workbook contains one sheet, `DPP1059056-20260731-WLIscrizion`, with an observed shape of **91 rows × 7 columns**: one header row and **90 source observations**. The source status column contains exactly:

- 41 `RICHIEDENTE_ISCRIZIONE` → **41 `pending` observations**;
- 49 `IN_AGGIORNAMENTO` → **49 `renewal_update_in_progress` observations**.

Structured identifier coverage is **90/90**, and application-date coverage is **90/90**. Most date cells use the exact Excel literal-formula wrapper described above; **2 rows use true Excel date cells** and are converted only through their explicit date value. Requested-section tokens, where present, are accepted only from the reviewed `SEZ_I` … `SEZ_X` vocabulary. No status, date, section or identifier is inferred from neighbouring rows.

## Validated candidate boundary

The production parser validation run recaptured both resources twice at the approved digests and produced **338 unique source-backed observations**:

- 248 `listed`;
- 41 `pending`;
- 49 `renewal_update_in_progress`.

Structured identifiers are present for **338/338 observations**. All 338 record locators are unique. Application-date coverage is 90/90 for the applicant/update series; listing-date and expiry-date coverage are each 248/248 for the listed series.

From the currently live Palermo baseline of **68,717 records / 64 published Prefectures / 66 registers / 64 mapped Prefectures**, the intended Matera national candidate boundary is therefore:

**69,055 records / 65 published Prefectures / 67 registers / 65 mapped Prefectures.**

This candidate count is not a live claim until the national registry build, repository tests, pull-request gates, merge and post-merge GitHub Pages deployment all succeed.

## Fail-closed parser boundary

`src/white_list_archive/parsers/matera_openxml.py` freezes and validates:

- the exact single-sheet workbook names;
- workbook shapes of 249×10 and 91×7;
- exact reviewed header sequences;
- 248 listed-source rows and 90 applicant/update-source rows;
- authority code `MT` on every row;
- nonblank source identity fields;
- listed status vocabulary restricted to `ISCRITTA`;
- applicant/update status vocabulary restricted to `RICHIEDENTE_ISCRIZIONE` and `IN_AGGIORNAMENTO`;
- complete explicit listed, expiry and application dates;
- exact handling of `="literal"` cells and true Excel dates without speculative repair;
- reviewed requested-section tokens;
- the single reviewed judicial-control note punctuation-variant family;
- the exact 248/41/49 public status boundary and unique observation locators.

Any workbook-shape, denominator, status vocabulary, date, section or unreviewed note-variant drift stops publication rather than being silently accommodated.
