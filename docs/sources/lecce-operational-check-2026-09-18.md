# Lecce White List operational source check — 2026-09-18

## Official source evidence

The current official Prefettura di Lecce White List landing page is:

- `https://prefettura.interno.gov.it/it/prefetture/lecce/evidenza/white-list`

Two independent captures of the landing page were byte-identical at 136,532 bytes (SHA-256 `1b411f046563a7b68105f280188dffaaa529cf7126b4f22889b104f02481b288`). The page positively exposes two current official attachments, both labelled as updated 9 September 2026:

- listed: `https://prefettura.interno.gov.it/sites/default/files/49/2026-09/elenco-white-list-per-categoria-aggiornato-9-settembre-2026.pdf`
- applicants: `https://prefettura.interno.gov.it/sites/default/files/49/2026-09/elenco-richiedenti-iscrizione-aggiornato-9-settembre-2026.pdf`

The date `2026-09-09` is used only as the current source-edition/reference boundary. It is not inferred to be a company decision, registration or legal-effect date.

## Capture and population boundary

Two independent captures of each attachment were byte-identical.

| population | bytes | pages | raw SHA-256 | physical rows | public observations |
| --- | ---: | ---: | --- | ---: | ---: |
| listed-side | 1,614,758 | 78 | `acbe7b735107d48735bc8d01902fc73d49f00e6d8d6ef11dc0c1f9dfd344765d` | 1,783 sector rows | 825 |
| applicants | 278,031 | 10 | `9d94226065ea80c35a140da93c74ed404ceea79018a725f755768b1a55a30124` | 90 | 90 |

The listed PDF repeats companies across ten statutory sections. Following the existing grouped-sector methodology, rows are grouped only when the complete source identity/date/status tuple is identical; identifier-only collapsing is explicitly not used because the source contains conflicting identifier/name combinations. The 1,783 section rows therefore yield 825 source-backed listed-side observations.

The listed-side status denominator is:

- 582 `listed`;
- 243 `renewal_update_in_progress`, based only on reviewed source-explicit variants of the `AGGIORNAMENTO ...` text.

Two long judicial-control notes are preserved as source outcome text but do not themselves state renewal/update and therefore do not trigger that status. No legal effect is inferred from those notes beyond their literal source content.

The applicant PDF contains exactly 90 observations. It exposes company name, registered office, identifier field and application date, but no decision/outcome column. All 90 are therefore represented as `pending` on positive applicant-population evidence; no denial, acceptance or other legal status is inferred.

The combined Lecce public boundary is **915 observations**: 582 listed + 243 renewal/update + 90 pending.

## Source defects preserved without inference

The listed source contains 804/825 observations with at least one structured identifier, 20 observations with a non-empty raw identifier that does not satisfy the repository's strict identifier syntax, and one genuinely blank identifier (`BRI.ECO S.r.l.`). One source-layout defect shifts BRI.ECO's dates one column left because the identifier cell is blank; the parser contains an exact page/table-row repair guarded by the full reviewed row value.

Six listed section rows contain malformed date typography. Their raw text is preserved while the canonical date remains blank:

- `CONE S.r.l.` expiry `16/101/2026`;
- `G.M.T. SUD S.r.l.` listing `09-apr`;
- `SITE - Società Impianti Telefonici Elettrrici S.r.l.` listing `0 9/09/2026`;
- `FALP COSTRUZIONI S.R.L.` listing `2 8 / 0 8 /2026`;
- `FALP COSTRUZIONI S.R.L.` listing `2 8 / 0 8 / 2 026`;
- `ECOMETAL SOCIETA' COOPERATIVA` expiry `14//04/2025`.

All 90 applicant observations contain at least one strict structured identifier. Nineteen source cells contain both a 16-character codice fiscale and an 11-digit partita IVA; both are retained when syntactically valid.

## Parser and fail-closed boundary

`src/white_list_archive/parsers/lecce_tables.py` freezes the reviewed source structure:

- exactly 78 listed pages and the reviewed per-page company-row denominator;
- exactly 1,783 listed section rows and the reviewed ten-section distribution;
- exactly 825 grouped listed-side observations;
- the exact reviewed status vocabulary and the six malformed-date exceptions;
- exactly 10 applicant pages with per-page row counts `[9, 10, 10, 10, 10, 10, 10, 9, 9, 3]`;
- exactly 90 applicant observations;
- the `09/09/2026` source-update marker on every source page.

Unexpected layouts, row denominators, status/note values, malformed-date variants or source-edition markers fail closed rather than being normalised into a plausible-looking result.

## Governance boundary

This check establishes current official-source identity, population completeness for the two positively published series, capture provenance and parser semantics. It does not by itself assert independent durable-evidence storage or hosted canonical-database integration; those remain separately governed. No `NOT_PUBLISHED` conclusion is drawn from failed requests or search behaviour.
