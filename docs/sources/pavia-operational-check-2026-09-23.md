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

The current governed archive path on `main` requires a repository-reviewed `SourceSeries` key and then performs durable provider storage plus content/capture-provenance readback before relational persistence or downstream parser eligibility. Lane B must therefore first materialise the reviewed Pavia source-series registry row, after which the main-only archive workflow can be invoked by an authorised workflow-dispatch surface. The payload must not be parsed from an unarchived temporary download.

## Candidate SourceSeries

The positively evidenced registered-company series should be represented as:

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

After the `pavia-listed` SourceSeries row is serially available on `main`, invoke the governed archive-first workflow against the exact official attachment resource. Accept the acquisition for parser work only after the emitted checkpoint confirms both durable ContentObject readback and durable capture-provenance readback; record relational persistence separately. Continue applicant discovery independently and conservatively.
