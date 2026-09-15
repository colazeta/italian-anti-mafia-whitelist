# Pisa White List operational check — 2026-09-15

## Scope

Evidence-first verification and parser preparation for the current public White List surfaces of the Prefettura di Pisa. This note records the official publication identity, repeated byte capture and reviewed source geometry. It does **not** by itself claim canonical integration, durable-evidence verification or public-export readiness.

## Official publication surface

Current official page:

- https://prefettura.interno.gov.it/it/prefetture/pisa/white-list-elenco-imprese-iscritte-e-richiedenti-iscrizione

The live official page was re-fetched on 15 September 2026 and returned HTTP 200. It explicitly distinguishes:

1. **Allegato A — Elenco Imprese Iscritte**: “Imprese iscritte nell'elenco dei fornitori, prestatori di servizi ed esecutori di lavori non soggetti a tentativo di infiltrazione mafiosa”.
2. **Allegato B — Elenco Richiedenti Iscrizione**: “Nuovo elenco delle imprese richiedenti l’iscrizione nell’elenco dei fornitori, prestatori di servizi ed esecutori di lavori non soggetti a tentativo di infiltrazione mafiosa”.
3. **Elenco Imprese in Aggiornamento**: a separate supplementary attachment for the renewal/update population.

The official page reports `Ultimo aggiornamento: Martedì 8 Settembre 2026, ore 12:14`. The repository uses 2026-09-08 as the source reference boundary for these current attachments while retaining the important caveat that this is a **page-level update marker**. It is not silently reinterpreted as an enterprise decision date, registration date or legal-effect date.

## Current byte-pinned resources

The attachment URLs were resolved from the live official Pisa page rather than constructed from a predictable path. Each resource was fetched independently twice on 15 September 2026. The two GETs for each resource were byte-identical before the digest below was accepted.

| Logical surface | Official resource | SHA-256 | Bytes | Pages |
| --- | --- | --- | ---: | ---: |
| listed | https://prefettura.interno.gov.it/sites/default/files/0/2026-09/iscritte.pdf | `30eea93e542aea6ceb13bcfd4e3f1358e1c3f9cfb274b23e738dfb304b1dea23` | 169257 | 6 |
| applicant | https://prefettura.interno.gov.it/sites/default/files/0/2026-09/richiedente-iscrizione.pdf | `ed3bbf19670dbed899f6386836f4723898e4c20f9315e4d4297156fd1dcd6b12` | 68334 | 1 |
| renewal/update supplementary list | https://prefettura.interno.gov.it/sites/default/files/0/2026-09/in-aggiornamento.pdf | `8658cd2e6048c44de18687b3933980778dd36bbf3721cd944063f61c0e2ceedb` | 73013 | 1 |

The current parser is intentionally byte-addressed: a changed byte length or digest must stop the edition-specific parse until the new source is reviewed.

## Reviewed source geometry and denominators

Repository-local `pdfplumber` extraction in the same dependency family used by the parser gives the following stable physical source boundary:

- `iscritte.pdf`: **398** data rows after 6 repeated headers; every data row has width 10 and exact source status `ISCRITTA`;
- `richiedente-iscrizione.pdf`: **18** data rows after 1 header; every data row has width 7 and exact source status `RICHIEDENTE_ISCRIZIONE`;
- `in-aggiornamento.pdf`: **33** data rows after 1 header; every data row has width 8 and exact source status `IN_AGGIORNAMENTO`.

The current source-observation boundary is therefore **449 physical company observations**: 398 listed, 18 applicant and 33 renewal/update. These are source-surface observations, not a claim about unique legal entities across time.

The listed table carries Prefettura competente, application date, fiscal identifier, company name, registered office, sectors, status, request protocol, observed registration start and expiry dates. The applicant table carries the identity/application core and applicant status. The renewal/update table is a separate supplementary source carrying identity/application fields, registered office, sectors, update status and protocol.

## Identity and overlap audit

Strict identifier handling accepts only an 11-digit Italian fiscal/VAT shape or a 16-character alphanumeric Italian fiscal-code shape. It does not remove punctuation or whitespace to manufacture a valid identifier.

Current reviewed coverage is:

- listed: **397/398** observations with a strict identifier;
- applicant: **18/18** with a strict identifier;
- renewal/update: **33/33** with a strict identifier.

The sole listed observation without a source identifier is **ROHDE NIELSEN A/S**. The source field is genuinely blank and is preserved as blank; no foreign or Italian identifier is inferred.

Within each surface there are no duplicate strict identifiers. Across the three current surfaces there are also **zero strict-identifier overlaps** (`listed ∩ applicant = 0`, `listed ∩ renewal/update = 0`, `applicant ∩ renewal/update = 0`). This supports ingesting the separately published update surface without silently duplicating a current Allegato A or Allegato B observation.

## Date review and fail-closed implications

All current application-date values extracted from the three byte-pinned resources are valid calendar dates in `dd/mm/yyyy` form. The prior reconnaissance artefacts that appeared to show year `2012` or malformed date-like tokens were extraction artefacts from a different document-reading path and are **not** source anomalies. They are not carried forward as evidence.

The parser therefore fails on any new date typography or invalid calendar date rather than repairing it. It also fails on page count, table count, header count, row width, row denominator, status lexeme, byte identity, unexpected strict-identifier loss or within-surface identifier duplication.

Conservative source treatment also applies to addresses and sectors: source values such as `-`, blank sector cells and `SEZ_*` labels are preserved rather than expanded or geocoded inferentially.

## Population identity assessment

Positive official evidence identifies both mandatory logical populations:

- `listed`: Allegato A, 398 current observations;
- `applicant`: Allegato B, 18 current observations.

The official page additionally publishes the 33-row `in aggiornamento` attachment as a distinct supplementary current surface. Its source status is mapped only to the existing semantic status `renewal_update_in_progress`; the source lexeme and separate provenance remain explicit. The integration design treats it as supplementary evidence for the listed/renewal side of the same ordinary Pisa White List register, not as a new legal register.

## Parser checkpoint

A Pisa-specific parser has been implemented with three explicit entry points (`pisa_listed`, `pisa_applicants`, `pisa_renewal_update`) and byte/geometry/status/identifier/date gates. Semantic regression tests freeze the current edition boundaries. A branch-only validation workflow repeat-fetches the three official resources before executing the parsers and the repository test suite.

This temporary workflow is an expansion-validation mechanism only. It must be removed before a production PR. Pisa must not be promoted to canonical/public integration until that source/parser gate is green and a separate fail-closed national candidate transaction validates the resulting registry denominators.

## Next transactional step

1. Complete the fresh-capture parser validation and full repository test run.
2. If green, update source-series/coverage evidence and bind the three approved parser entry points into the public national registry without weakening its recursive publication contract.
3. Execute a fail-closed national candidate build and freeze the resulting national/Pisa denominators only after the actual build succeeds.
4. Remove all branch-only workflows/helpers before PR; require a production-only diff and the normal CI/public-portal gates.
