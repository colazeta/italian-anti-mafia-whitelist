# Catanzaro White List operational check — 2026-09-15

## Scope

Evidence-first verification and parser preparation for the current public White List surfaces of the Prefettura di Catanzaro. This note records official publication identity, repeated byte capture, reviewed source geometry and the edition-specific parser boundary. It does **not** by itself claim canonical database integration, durable-evidence verification or public-export readiness.

## Official publication surface

Current official page:

- https://prefettura.interno.gov.it/it/prefetture/catanzaro/provvedimenti-whitelist-elenchi

The live official page was re-fetched on 15 September 2026 and positively exposes two distinct current populations:

1. **Elenco ditte iscritte in White List al 10.09.2026**;
2. **Elenco ditte richiedenti in White List al 10.09.2026**.

The page itself reports `Ultimo aggiornamento: Giovedì 11 Settembre 2026, ore 10:01`, while the listed attachment explicitly states `Aggiornamento alla data del 10/09/2026` and both current attachment labels are tied to 10 September 2026. The repository therefore uses **2026-09-10** as the current source-edition/reference boundary. The page-level 11 September marker is retained as publication-surface metadata only; neither date is silently reinterpreted as an enterprise decision or legal-effect date.

## Current byte-pinned resources

The current official attachment URLs were resolved from the Prefettura publication surface. Each resource was fetched independently twice during branch validation on 15 September 2026; each pair of GETs was byte-identical before its digest was accepted.

| Logical surface | Official resource | SHA-256 | Bytes | Pages |
| --- | --- | --- | ---: | ---: |
| listed | https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elencoditteiscritteinwhitelistal10092026.pdf | `8578a1b2d3ef0e2d71f1133381082d63d131182fd1b74c456cffe708ed94df7f` | 619398 | 82 |
| applicant | https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elencoditterichiedentiiscrizioneinwhitelistal10092026.pdf | `8c5b0ea684b20f0893016e4a528bac57fb2b05c40aa9669340bdf7bd7dab115c` | 338826 | 46 |

The parser is intentionally byte-addressed: source byte-length or digest drift stops the edition-specific parse until the changed official resource is reviewed.

## Listed population: geometry and grouping

The listed PDF contains one seven-column table per page and 82 repeated table headers. After headers, the current source contains **1,556 section-membership rows** across the ten White List sections:

| Section | Membership rows |
| ---: | ---: |
| I | 254 |
| II | 108 |
| III | 394 |
| IV | 115 |
| V | 388 |
| VI | 146 |
| VII | 1 |
| VIII | 8 |
| IX | 18 |
| X | 124 |

Section assignment is read only from the page heading area. This avoids treating references such as a court `Sezione` in a company note as White List section evidence.

The parser conservatively groups section memberships only when company name, registered office, secondary office, raw identifier field, raw/parsed listing date, raw/parsed expiry date and semantic status agree after minimal source-text normalisation. The reviewed source has no duplicate observation within the same section under that rule. The 1,556 membership rows yield exactly **610 listed-side company observations**:

- **377** `listed`;
- **233** `renewal_update_in_progress`.

The renewal/update semantic status is assigned only where the official note positively contains a renewal/update/instruction marker (`rinnovo`, `aggiornamento`, `istruttoria`). Judicial-control notes are not reinterpreted as renewal status.

## Applicant population: geometry and denominator

The applicant PDF contains one five-column table per page. Across 46 pages there are 43 repeated headers plus one reviewed layout-marker row containing only the source asterisk. That marker is not a company observation and is excluded. All other positive non-header source rows are retained, yielding exactly **277 applicant observations**, all mapped to `pending`.

Two positive applicant rows have a blank source application date and one carries the malformed source string `1/8/12/2025`. They remain observations; the parser preserves those raw values and leaves the parsed application date blank rather than repairing or inferring a date. The otherwise sparse `publigraphic` source row is likewise retained as a distinct positive observation because the source gives a nonblank company name and there is no defensible evidence for silently merging it with the neighbouring `pubbligraphic sas` row.

## Identity handling

Identifier treatment is deliberately conservative. The raw source identifier field is always preserved. For structured identifiers the parser accepts only:

- an exact 11-digit numeric value; or
- an exact 16-character alphanumeric fiscal-code shape.

Whitespace introduced by PDF line wrapping may be removed before shape validation. Explicit source delimiters `/` and `;` may separate multiple values. Punctuation is not otherwise deleted to manufacture a valid identifier, and malformed concatenations without a source delimiter are not split inferentially.

Current strict-identifier coverage is:

- listed: **601/610** grouped observations;
- applicant: **272/277** observations.

Missing or malformed identifiers remain unfilled.

## Date anomalies and fail-closed treatment

Ordinary `dd/mm/yyyy` values are calendar-validated. The current byte-pinned edition also contains a finite reviewed set of raw date anomalies. These are preserved verbatim in provenance and emitted with a blank structured date, not corrected:

- listed-side listing field: `01/07/205`, `12/03//2026`, `05/0/05/2026`, `06/08/206`, `13/05/026`, and the special source marker `x`;
- listed-side expiry field: blank, `x`, `03/082027`, `06/08/207`, `10/06/207`, `17/112026`, `30/03//2027`, `03/092026`, `18/12/026`, `26/082026`, `21/112026`;
- applicant application field: blank and `1/8/12/2025`.

Any other date typography on this byte-pinned edition is an error. Dates appearing inside free-text judicial notes are never substituted for the dedicated date columns.

## Candidate source boundary

The current positively evidenced source boundary is therefore **887 company observations**:

- 610 listed-side observations (377 listed; 233 renewal/update in progress);
- 277 applicant observations (277 pending).

These are current source-surface observations, not a claim about unique legal entities across historical editions.

## Parser checkpoint

A Catanzaro-specific parser has been implemented with two explicit entry points (`catanzaro_listed`, `catanzaro_applicants`). It freezes source hashes, byte lengths, page/table geometry, membership and company denominators, section counts, status counts, identifier coverage and reviewed date exceptions. Semantic tests separately freeze the core evidence boundary.

A branch-only source-validation workflow is being used to repeat-fetch the official attachments and exercise the parser before any national integration. It is an expansion mechanism only and must be removed before a production pull request.

## Next transactional step

1. Execute the parser against fresh byte-identical official captures and run the semantic plus full repository test suites.
2. Only if green, bind the two source series and parser entry points into the national publication configuration and source/coverage registries.
3. Run a separate fail-closed national candidate transaction and freeze national/Catanzaro denominators from the actual successful build, not from arithmetic expectation.
4. Remove all branch-only workflows/helpers before PR and require a production-only diff plus normal CI/public-portal gates.
