# Pavia White List operational check — 23 September 2026

## Scope

This note records source-discovery evidence for the ordinary provincial White List administered by the Prefettura — U.T.G. di Pavia. It is a source-layer checkpoint only. No source payload was acquired, parsed, promoted to current data, or represented as durably archived by this check.

## Official source verification

The dedicated official Prefettura page positively exposes the registered-company population:

- page: `https://prefettura.interno.gov.it/it/prefetture/pavia/white-list-elenco-imprese-iscritte`
- official page title: `WHITE list - Elenco imprese iscritte`
- attachment label observed on the official indexed surface: `WHITE LIST aggiornata al 02-04-2026`
- displayed attachment size: `769.18 KB`
- page last-update marker: `2 April 2026, 14:58`

The separate official procedure page is:

- `https://prefettura.interno.gov.it/it/prefetture/pavia/iscrizione-white-list-antimafia`

It documents the application procedure and the use of PortaleWL for new applications, updates and renewals from 21 July 2025. It states that, after favourable checks, the Prefettura places the enterprise in the list published on its institutional site. This procedure page is not evidence that a public applicant list is published.

### Applicant-publication discovery recheck

A bounded official-domain discovery recheck on 23 September 2026 used Pavia-specific variants for `richiedenti`, `elenco imprese richiedenti`, `ditte richiedenti`, `in istruttoria` and White List applicant terminology. It again surfaced the Pavia procedure page and the dedicated registered-company page, but did not positively identify a Pavia page or attachment publishing the applicant population.

This is a discovery result only. A failed or incomplete search is not evidence that the Prefettura does not publish such a list, and it is not converted into `NOT_PUBLISHED`. The applicant target therefore remains explicitly unresolved until positive official evidence or another governed source-status determination is available.

## Population-completeness assessment

For the ordinary `WL-REGIME-L190-2012` scope:

- `listed`: **positively identified** through the dedicated official registered-company page above;
- `applicant`: **UNRESOLVED_REQUIRES_REVIEW**. No separate or combined public applicant population was positively identified in this check.

The absence of a discovered applicant publication is not treated as `NOT_PUBLISHED` and no completeness claim is made.

## Archive-first boundary

No attachment bytes were downloaded during this checkpoint. Consequently there is deliberately:

- no capture UUID;
- no capture timestamp;
- no SHA-256 or ContentObject identity;
- no durable content readback receipt;
- no durable capture-provenance readback receipt;
- no relational capture row;
- no ParseRun or persisted observation snapshot.

The current governed archive path on `main` requires a repository-reviewed `SourceSeries` key and then performs durable provider storage plus content/capture-provenance readback before relational persistence or downstream parser eligibility. The reviewed `pavia-listed` SourceSeries row is now materialised on `parallel-expansion/pavia-2026-09-22`; it must reach canonical `main` through serial integration before the protected main-only archive workflow can accept the first Pavia capture. The payload must not be parsed from an unarchived temporary download.

## Reviewed SourceSeries

The positively evidenced registered-company series is represented on the Lane B branch as:

- `source_series_key`: `pavia-listed`
- `authority_key`: `pavia`
- `regime_code`: `WL-REGIME-L190-2012`
- `population_scope`: `listed`
- `sector_scope`: `all`
- `publication_model`: `periodic_attachment`
- `series_url`: `https://prefettura.interno.gov.it/it/prefetture/pavia/white-list-elenco-imprese-iscritte`
- `resource_resolution_status`: `direct_series_page_resolved`
- `verified_date`: `2026-09-23`

Do not create a `pavia-applicants` series unless positive official evidence identifies such a publication or a combined source that actually exposes the applicant population.

## Next executable step

Serially integrate the reviewed `pavia-listed` SourceSeries row to canonical `main` without promoting Pavia as source-population complete. Once that row is on `main`, invoke the governed archive-first workflow against the exact official attachment resource. Accept the acquisition for parser work only after the emitted checkpoint confirms both durable ContentObject readback and durable capture-provenance readback; record relational persistence separately. Continue applicant discovery independently and conservatively.
