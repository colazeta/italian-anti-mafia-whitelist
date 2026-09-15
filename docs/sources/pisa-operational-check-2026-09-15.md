# Pisa White List operational check — 2026-09-15

## Scope

Evidence-first verification of the current public White List surfaces of the Prefettura di Pisa. This checkpoint establishes publication identity only. It does **not** yet claim immutable capture, parser validation, canonical integration, durable evidence, or public-export readiness.

## Official publication surface

Current official page:

- https://prefettura.interno.gov.it/it/prefetture/pisa/white-list-elenco-imprese-iscritte-e-richiedenti-iscrizione

The live official page was re-fetched on 15 September 2026 and returned HTTP 200. It explicitly distinguishes:

1. **Allegato A — Elenco Imprese Iscritte**: “Imprese iscritte nell'elenco dei fornitori, prestatori di servizi ed esecutori di lavori non soggetti a tentativo di infiltrazione mafiosa”.
2. **Allegato B — Elenco Richiedenti Iscrizione**: “Nuovo elenco delle imprese richiedenti l’iscrizione nell’elenco dei fornitori, prestatori di servizi ed esecutori di lavori non soggetti a tentativo di infiltrazione mafiosa”.
3. **Elenco Imprese in Aggiornamento**: a separate supplementary attachment for the renewal/update population.

The official page reports `Ultimo aggiornamento: Martedì 8 Settembre 2026, ore 12:14`. This is a page-level update marker. It must not be silently reinterpreted as a legal decision date or as an attachment-internal edition date.

## Current resources resolved from the official page

| Logical surface | Official resource | Page-advertised size | Observed PDF pages |
| --- | --- | ---: | ---: |
| listed | https://prefettura.interno.gov.it/sites/default/files/0/2026-09/iscritte.pdf | 165.29 KB | 6 |
| applicant | https://prefettura.interno.gov.it/sites/default/files/0/2026-09/richiedente-iscrizione.pdf | 66.73 KB | 1 |
| renewal/update supplementary list | https://prefettura.interno.gov.it/sites/default/files/0/2026-09/in-aggiornamento.pdf | 71.3 KB | 1 |

These URLs were obtained from the live official Pisa page rather than constructed from a predictable path.

## Preliminary source-shape reconnaissance

Document extraction was used only to understand the source model before parser implementation. These counts are **not yet publication gates** because the bytes have not yet been independently re-fetched and SHA-256 pinned by the repository workflow.

- `iscritte.pdf`: preliminary physical-row count **207**; the extracted status column is uniformly `ISCRITTA` (207).
- `richiedente-iscrizione.pdf`: preliminary physical-row count **18**; the extracted status column is uniformly `RICHIEDENTE_ISCRIZIONE` (18).
- `in-aggiornamento.pdf`: preliminary physical-row count **33**; the extracted status column is uniformly `IN AGGIORNAMENTO` (33).

The listed source has a tabular schema including Prefettura competente, application date, fiscal identifier, company name, registered office, sectors, status, request protocol, registration start and expiry dates. The applicant source has the same identity/application core with applicant status. The update source is a separate table with update status and protocol information.

## Source anomalies and fail-closed implications

The preliminary extraction exposes values that must be preserved and reviewed rather than corrected inferentially. In particular:

- the update document renders a series of application-date values as year `2012`; no correction to `2026` is permitted without source-level evidence;
- an update row renders `2711/2012` as a date token;
- protocol/date-like strings show extraction anomalies, including values such as `00314882_202310710`;
- the listed extraction contains at least one visibly malformed/split row around the 10 March 2026 area, so raw extracted row count alone is insufficient for parser acceptance.

Parser implementation must therefore be fail-closed and geometry/source-bound. It must not repair identifiers, dates, protocols, missing addresses or sector memberships by fuzzy inference.

## Population identity assessment

Positive official evidence is sufficient to identify the two mandatory logical populations:

- `listed`: positively identified through Allegato A;
- `applicant`: positively identified through Allegato B.

The separately published `in aggiornamento` attachment is also positively identified, but its relationship to the listed population must be handled explicitly during parser/integration design so that renewal/update observations are not duplicated or silently collapsed into Allegato A.

Accordingly, Pisa can move from a generic nationally discovered/source-identified target to a **source-verified, current-series-identified** expansion target once the status registries are updated. It must **not** move to captured, parser-valid, company-observations-loaded, canonical-integrated, durable-evidence-verified or public-export-enabled on the strength of this check alone.

## Next transactional step

1. Independently fetch all three official PDFs at least twice and pin byte length + SHA-256; require stable identity or explicitly document mutability.
2. Inspect page geometry/table boundaries and freeze physical/logical-row denominators, including malformed rows and continuation rules.
3. Implement a Pisa-specific fail-closed parser family/binding for listed, applicant and renewal/update surfaces.
4. Add semantic regression tests and only then promote source-series/coverage registries and national/public integration.
5. Before PR, remove any temporary validation mechanism and require a production-only diff plus the normal CI/public-portal gates.
