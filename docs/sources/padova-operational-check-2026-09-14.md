# Padova White List source check - 14 September 2026

## Scope

This note records the current official-source verification for the Prefettura di Padova ordinary White List. It is an evidence checkpoint only: no parser, row denominator, status distribution, or publication-completeness claim is established here.

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

## Current verification boundary

The two official HTML series pages were freshly resolved on 14 September 2026 and returned the resource links above. The repository already contained both Padova source-series mappings; this check re-confirms those mappings against the live official surface.

A second independent byte-level acquisition of the two PDF attachments was not completed in this checkpoint. Consequently:

- no SHA-256 is recorded yet;
- no page count or source-row denominator is claimed;
- no parser-family binding is selected yet;
- no record/status count is claimed;
- no national/public integration is enabled;
- no inference is made from any unavailable or uninspected content.

The next expansion step is to acquire each attachment repeatably, establish byte identity/content hashes, then perform visual/table-structure inspection before implementing a fail-closed parser for the listed and applicant series.

## Byte-level capture

A GitHub-hosted independent acquisition on 2026-09-14 12:03:26 UTC repeat-fetched each official PDF twice. Both pairs were byte-identical and passed a PDF magic-header check.

- Registered-company PDF: 1411878 bytes; SHA-256 `d140451c7a091e7df497f49465177ba012422917d2031c24df676e76dd909289`.
- Applicant PDF: 343755 bytes; SHA-256 `b2cce4c2d34db016a7b84ac83f71032acdf319c020e1bf881d923ef1d45601a3`.

These hashes pin the exact bytes reviewed by the expansion workflow. They do not by themselves establish page count, row count, field semantics, or completeness; those remain subject to visual/table-structure inspection and parser validation.
