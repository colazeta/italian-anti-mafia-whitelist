# Udine operational source check — 10 September 2026

## Current official publication

The official Prefettura di Udine White List landing page was independently re-resolved from a GitHub-hosted runner on 10 September 2026 with HTTP 200. It positively exposes both current ordinary White List populations, both updated **09/09/2026**:

- **Elenco ditte iscritte nelle White List (aggiornato al 09/09/2026)** — 64-page PDF, SHA-256 `0bd74200cbe5d96b313f943a889acbfe1fe6278293516a76ad0702e28b293fba`.
- **Elenco dei fornitori che hanno chiesto di essere iscritti (aggiornato al 09/09/2026)** — 2-page PDF, SHA-256 `4ea03173171bda5df4a3abba120feae3842506f436f28f5c0604099388523971`.

Landing page: `https://prefettura.interno.gov.it/it/prefetture/udine/evidenza/white-list`.

The applicant document is explicitly headed as the list of companies requesting registration and its note excludes companies already registered. The applicant population is therefore established by positive source evidence rather than inferred from document structure or failed discovery.

## Reviewed logical-row boundary

The listed PDF is borderless, so the parser does not rely on generic table extraction. A dedicated geometry audit independently anchors company rows to the CF/P.IVA and date columns, excludes section headers, freezes page-level denominators and verifies all ten section transitions. The reviewed population is exactly **1,431 listed-population observations** across 64 pages. The current status distribution is **1,187 `listed` + 244 `renewal_update_in_progress`**; `In aggiornamento` is used only where that text occurs on the same source row.

The listed section distribution is: Sezione 1 = 250; Sezione 2 = 83; Sezione 3 = 281; Sezione 4 = 112; Sezione 5 = 327; Sezione 6 = 174; Sezione 7 = 1; Sezione 8 = 16; Sezione 9 = 37; Sezione 10 = 150. The reviewed section transitions are I at page 1, II at page 11, III at page 15, IV at page 26, V at page 31, VI at page 46, VII and VIII at page 54, IX at page 56 and X at page 58.

The applicant PDF yields exactly **19 observations** across two pages (17 + 2). All belong positively to the official requesting-company publication and are therefore mapped to `pending` without inferring a later legal outcome.

## Extraction exceptions and conservative treatment

One listed source identifier, for `TOSON & TOSON DI TOSON DANIELE & C. S.A.S.`, is published as the 12-digit raw value `000152050308`. The raw value is retained, but no normalised identifier is created. Identifier extraction is column-bound so 16-character words in legal names cannot be misclassified as identifiers.

`IMPERMEABILIZZAZIONI PALMA S.R.L.` has the source expiry string `269/01/2027`. It is retained verbatim in provenance and the normalised expiry date is deliberately blank. Any other unreviewed date typography or calendar-invalid date fails closed.

The final company on applicant page 1 is split across the page boundary: `MTL MESSAGGERIE TRASPORTI E` continues on page 2 as `LOGISTICA SOCIETA’ COOPERATIVA`. The parser reconstructs the complete legal name only at this exact reviewed coordinate and asserts the pre-repair source text before doing so. No general cross-page reconstruction heuristic is used.

Applicant activity codes are read only from the source activity-code column and restricted to the published legend (`A`–`I`, `L`). Unexpected codes fail closed.

## Publication boundary

The public archive uses these source-backed observations without claiming national legal-entity deduplication. Canonical hosted-database integration and independent durable-evidence verification remain separately governed under issue #16 and are not implied by this public-source validation.
