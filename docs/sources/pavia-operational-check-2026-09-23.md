# Pavia White List operational check — 23 September 2026

## Scope

This note records source-discovery evidence for the ordinary provincial White List administered by the Prefettura — U.T.G. di Pavia. The original 23 September checkpoint performed no payload acquisition. A later shared Prefecture-robot run on canonical `main` has since durably archived five Pavia discovery resources under an unbound quarantine identity; that later preservation is recorded below and does not promote any Pavia source facts.

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

### Original 23 September checkpoint

No attachment bytes were downloaded by Lane B during the original checkpoint. There was therefore no bound `pavia-listed` capture, ContentObject, relational capture, ParseRun or observation snapshot.

### Quarantined discovery preservation observed on 27 September 2026

Canonical `main` now contains the shared Prefecture-robot acquisition path. Its Pavia robot still has `sources=[]`, `population_mapping_reviewed=false` and `publication_approved=false`; it therefore archived newly discovered Pavia resources under the unbound discovery/quarantine identity rather than guessing a SourceSeries or population.

The current safe robot state records the following durable discovery captures:

| Resource | Capture id | SHA-256 | Bytes |
| --- | --- | --- | ---: |
| White List landing page | `88f5c881-3cd1-4ee9-8dc9-7659e1789747` | `26a445ce3dfa077279e40e9edcef3d0a35189a515f132090ecdf2c8dc400723f` | 107955 |
| White List institution page | `19a5e08f-9c8b-45f4-b39a-9aeb263e54dc` | `51574548394bd53fc3d9ad82c2e4cac1d7f6249a37fdba86b972c250a946919f` | 78827 |
| application/procedure page | `24bdcb7b-5493-4464-a9bb-1793a3067e38` | `28d8ff5b761273d3ed414cbbdf12dbe20a1ed80b02e3bffabed3cdac4ee23538` | 90654 |
| listed-company page | `c3543071-c351-46f3-967d-59bd36f54c32` | `4d711300b8b30e93c07fa591ee4501bcd77705d5dbba83ebfb87e3bb0681da8b` | 78453 |
| official `WHITE LIST 02-04-2026` PDF | `d12f17e9-07f6-4b66-9b8a-42dc3d051b10` | `2ebff98846759ab6e5f96c93812f704502c505ad0bab31f6b1edd9628feddb0d` | 787637 |

The safe state exposes the later Pavia check at `2026-09-27T21:19:41.124002+00:00`, but it does not expose the individual immutable `captured_at` values for the five capture records. Those timestamps must therefore be read from the private CaptureCatalogue rather than inferred from the robot cycle time.

No relational capture row, ParseRun or persisted observation snapshot is evidenced for these discovery captures. Their source facts remain unaccepted.

### Temporal-provenance blocker

The later `capture`-mode check at `2026-09-27T21:19:41.124002+00:00` observed the same five byte identities and returned `captured_urls=[]`, retaining the original capture-id lists. The shared robot implementation currently skips `archive_payload` when the resource's `archived_sha256` already equals the newly observed SHA-256. That preserves the ContentObject correctly but does not create a distinct immutable capture/check record for the later observation.

This is incompatible with issue #163's temporal-identity contract: unchanged bytes may reuse the ContentObject, but a later acquisition/check must retain its own capture/check provenance. This is shared Lane A acquisition infrastructure and must not be patched in the Pavia branch.

The reviewed `pavia-listed` SourceSeries row remains materialised only on `parallel-expansion/pavia-2026-09-22`. It must reach canonical `main` through serial integration before the official listed PDF can be acquired under that reviewed identity. If the bound acquisition observes SHA-256 `2ebff988...` again, it should reuse the already durable ContentObject while creating new immutable `pavia-listed` capture provenance.

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

Serially integrate the reviewed `pavia-listed` SourceSeries row to canonical `main` without promoting Pavia as source-population complete. Keep the five existing discovery captures quarantined. Then acquire the exact official listed resource under `pavia-listed`; reuse an identical ContentObject if appropriate but create distinct immutable bound capture provenance. Parser/configuration lineage, relational persistence and persisted observations may proceed only after that preservation chain is independently verified. Separately, Lane A must correct unchanged-byte robot checks so every later observation retains durable capture/check provenance. Continue applicant discovery independently and conservatively.
