# Padova White List source check - 14 September 2026

## Scope

This note records the official-source verification and fail-closed parser evidence for the Prefettura di Padova ordinary White List. Publication integration is permitted only for the exact byte-pinned editions and frozen populations documented below.

## Official publication surfaces

### Registered companies

- Authority: Prefettura - Ufficio Territoriale del Governo di Padova
- Official series page: https://prefettura.interno.gov.it/it/prefetture/padova/white-list-elenco-imprese-iscritte
- Page label: `White List - Elenco imprese iscritte`
- Attachment label: `ELENCO IMPRESE ISCRITTE`
- Current attachment URL exposed by the official page: https://prefettura.interno.gov.it/sites/default/files/75/2026-08/elenco-imprese-iscritte.pdf
- Displayed attachment size: 1.35 MB
- Official page last-updated timestamp observed on 14 September 2026: 17 August 2026, 10:24

The page and attachment label positively identify this resource as the registered-company population. The page timestamp is not treated as an in-document edition date unless the document itself confirms it.

### Companies requesting registration

- Authority: Prefettura - Ufficio Territoriale del Governo di Padova
- Official series page: https://prefettura.interno.gov.it/it/prefetture/padova/white-list-elenco-imprese-richiedenti
- Page label: `White List - Elenco imprese richiedenti`
- Attachment label: `ELENCO IMPRESE RICHIEDENTI`
- Current attachment URL exposed by the official page: https://prefettura.interno.gov.it/sites/default/files/75/2026-08/elenco-imprese-richiedenti.pdf
- Displayed attachment size: 335.7 KB
- Official page last-updated timestamp observed on 14 September 2026: 17 August 2026, 10:25

The dedicated official page and attachment label positively identify this resource as the applicant population. Applicant coverage is therefore evidenced by a dedicated publication rather than inferred from the listed-company resource.

## Cross-links and source relationship

The registered-company page links the dedicated applicant page, and the applicant page links the dedicated registered-company page. The Prefettura's White List landing page also exposes both series. This supports treating the two documents as the current ordinary White List source family for source-discovery purposes.

## Byte-level capture

A GitHub-hosted independent acquisition on 2026-09-14 12:03:26 UTC repeat-fetched each official PDF twice. Both pairs were byte-identical and passed a PDF magic-header check.

- Registered-company PDF: 1,411,878 bytes; SHA-256 `d140451c7a091e7df497f49465177ba012422917d2031c24df676e76dd909289`.
- Applicant PDF: 343,755 bytes; SHA-256 `b2cce4c2d34db016a7b84ac83f71032acdf319c020e1bf881d923ef1d45601a3`.

These hashes pin the exact bytes acquired by the expansion workflow. They do not by themselves establish page count, row count, field semantics, or completeness.

## Parser validation and population boundary

The dedicated Padova parser validation run `34849190341` completed successfully on 14 September 2026 against two independent acquisitions of each official source. The repository CI run `34849190491` on the same head also completed successfully.

The byte-pinned listed PDF contains 105 pages and exactly 831 physical company rows after one repeated header per page is excluded. The parser yields 581 `listed` and 250 `renewal_update_in_progress` observations. Two exact non-calendar expiry values (`46581,00` and `8807/2026`) are retained as raw source evidence while the normalised expiry is left blank; one chronology inversion printed by the source for GEROTTO FEDERICO SRL is preserved without correction.

The byte-pinned applicant PDF contains 17 pages and exactly 174 physical company rows. The parser yields 174 `pending` observations. Applicant row 113 recovers the visibly printed name `NON SOLO ZANZARE SRL` through an exact full-row binding because table extraction loses the company-name cell. Applicant rows 38 and 39 for `CLEAN SRL` are two genuinely distinct physical source rows with identical content and remain two observations; no deduplication is applied.

Across both populations the parser produces exactly 1,005 distinct record locators. Strict identifier extraction accepts only positively evidenced 11-digit VAT/fiscal identifiers or 16-character fiscal codes (including source whitespace normalisation inside explicit slash-delimited components); raw identifier text is retained separately. Section membership is accepted only when the numbered physical section cell contains its own expected section number.

## Publication boundary

The two official series positively establish both listed and applicant populations for the current Padova ordinary White List. The parser is therefore approved for public-source observation integration only when source SHA-256, page counts, row denominators, table width/header invariants, status counts and reviewed exception populations all match the frozen values above. Any drift fails closed. Canonical hosted-database integration and independent durable-evidence verification remain separate controls and are not asserted by this source-parser validation.
