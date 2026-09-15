# Lodi operational source check — 15 September 2026

## Scope

This note records the source boundary used for the Lodi public-source expansion. It is an evidence note, not a claim that Lodi is already integrated or live on the public portal.

## Official landing page

- Authority: Prefettura di Lodi.
- Official White List page: `https://prefettura.interno.gov.it/it/prefetture/lodi/evidenza/white-list`.
- The page positively exposes two separate populations:
  - `White list – Elenco imprese iscritte`;
  - `White List - Elenco delle imprese richiedenti l'iscrizione`.
- Both links point to separately published tabs of the same Google Sheets publication controlled from the official Prefecture page.
- The official page body currently contains a stray textual reference to `Prefettura di Potenza`. This is treated as an editorial carry-over only: the official URL, page identity and the two linked publication labels are Lodi. It is not used as source identity evidence.

## Listed population

Approved raw export:

`https://docs.google.com/spreadsheets/d/e/2PACX-1vSTOZ3x5FBo4IanDtISccAnqZmVLPmGhEYaj0YrDn4aP6ZpwY8kzpiHhAX0i26IwipgD6bvsWhSigwz/pub?gid=0&single=true&output=csv`

Two independent bounded GETs on 15 September 2026 returned byte-identical exports.

- SHA-256: `ad64ab8669084bc31b80938a384b41849be4db28b448e9b2c0ce199f6af1d6ec`.
- Size: 36,372 bytes.
- Physical CSV rows: 324.
- Width: exactly 7 columns on every physical row.
- Positively identifiable section-membership rows: 291.
- Section memberships: I 44; II 24; III 47; IV 18; V 55; VI 54; VII 6; VIII 1; IX 3; X 39.
- Source-row statuses: 254 ordinary listed rows; 37 rows explicitly marked as being updated.
- Conservative grouping by positive identifier + listing date + expiry date + source status yields 169 public listed observations: 146 `listed` and 23 `renewal_update_in_progress`.
- The parser must retain all source memberships and address/name/identifier variants rather than silently collapsing their provenance.

The source is a mutable current Google Sheet and does not expose a reliable edition date. `2026-09-15` is therefore the project observation/capture date for this approved byte boundary, not an inferred publication date. The page's own older modification date is not substituted for the source edition date.

## Applicant population

Approved raw export:

`https://docs.google.com/spreadsheets/d/e/2PACX-1vSTOZ3x5FBo4IanDtISccAnqZmVLPmGhEYaj0YrDn4aP6ZpwY8kzpiHhAX0i26IwipgD6bvsWhSigwz/pub?gid=245180329&single=true&output=csv`

Two independent bounded GETs on 15 September 2026 returned byte-identical exports.

- SHA-256: `55aeab7e809cb90cc1ebd1ad9c1f08db78e91648a2c2e1a2b603188c77846228`.
- Size: 1,388 bytes.
- Physical CSV rows: 8.
- Width: exactly 7 columns on every physical row.
- Positively identifiable applicant observations: 4, with four distinct positive identifiers.
- Source outcomes: two explicit denials and two `IN ISTRUTTORIA` observations.
- The two denial rows expose decision dates in the source text: 17 June 2021 and 17 November 2022 respectively. They are not inferred from application dates.

The four source observations are:

1. C.F. S.r.l. — identifier `03554730790` — application 2 March 2021 — explicit denial dated 17 June 2021.
2. PAOLO GOMME TRASPORTI S.r.l. — identifier `02155610187` — application 26 October 2021 — explicit denial dated 17 November 2022.
3. EAL COMPOST S.r.l. — identifier `12220770155` — application 6 November 2025 — `IN ISTRUTTORIA`.
4. M.B. IMPIANTI S.r.l.s. — identifier `13973560967` — application 7 September 2026 — `IN ISTRUTTORIA`.

The applicant sheet is therefore positively published and non-empty. No applicant status or completeness conclusion is derived from search failure.

## Candidate source boundary

The evidence-backed candidate boundary is 173 public observations: 169 listed-series observations plus 4 applicant-series observations. This number remains a parser/integration candidate until the complete parser, repository tests and national publication gates succeed.

The source-validation mechanism used during expansion is temporary and must be removed before a production-only pull request. Durable-evidence and canonical hosted-database promotion remain separate controls and are not implied by public-source validation.
