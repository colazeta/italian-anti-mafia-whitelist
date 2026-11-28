# National source registry

This directory contains the research registry used to discover, classify and audit the public White List sources published by Italian territorial authorities.

The registry is deliberately split into layers.

## Files

### `territorial_authorities.csv`

Coverage universe for the national project. It contains one stable project key per territorial White List authority/jurisdiction and intentionally does **not** guess a White List URL.

Current baseline: 106 entries:

- 103 Prefetture – Uffici Territoriali del Governo;
- 2 Commissariati del Governo (Bolzano/Bozen and Trento);
- 1 special Valle d'Aosta case.

### `verified_primary_pages.csv`

White List landing pages that have been independently verified against an official public source. A URL enters this table only after verification; unverified URLs are not inferred from naming conventions.

Current research status: 34 of 106 authority landing pages independently resolved and verified.

### `pilot_source_profiles.csv`

A deliberately heterogeneous pilot sample used to design source-series and parser taxonomy before attempting national parsing. It records publication models, populations, formats and historical-snapshot signals.

### `source_series_inventory.csv`

Evidence-backed inventory of distinct recurring White List publications discovered inside verified authorities. A source series is more granular than an authority landing page: listed companies, applicants, sector-specific lists and special registers can all be separate series.

Current inventory: 59 source series across 34 verified authorities. The mandatory listed/applicant completeness ledger currently contains 35 register/regime scopes, of which 30 account for both logical populations and 5 remain explicitly unresolved.

The inventory demonstrates why one-row-per-Prefecture modelling is insufficient. Examples include:

- separate listed/applicant series;
- comprehensive plus per-sector series;
- combined listed/applicant publications;
- a distinct Bologna post-earthquake register;
- retained dated snapshot series;
- custom web applications.

## Discovery tooling

`white-list-national-index` parses the Ministry of the Interior national White List index and outputs the real destination links behind the `Visualizza` controls.

The national index is treated as a **discovery/provenance source**, not as a canonical company-record source. Company observations must ultimately be traced to the territorial publication or content object from which they were extracted.

## Rules

1. Never infer a local landing-page URL from a predictable path.
2. Preserve special territorial arrangements instead of forcing them into the ordinary Prefettura model.
3. Separate authority coverage from source-series discovery.
4. One authority can expose multiple source series (listed companies, applicants, sector lists, special registers, historical snapshots, etc.).
5. A source series can change schema and publication format over time.
6. Historical URLs and current URLs are both valuable but must be classified by source origin and capture time.
7. A source-series row is added only when its population/regime/publication identity is supported by public evidence.
8. A verified authority/register is not source-population complete until both `listed` and `applicant` populations are explicitly accounted for; failure to find one is not evidence that it is not published.

### Unreviewed official publication-page hints (22 November 2026)

`unreviewed_official_pages.csv` lists two dedicated official-domain HTML
pages per authority for **La Spezia, Oristano and Verona**. Their existence
and population labels are corroborated by the Ministry's publicly indexed
pages; direct web retrieval currently returns HTTP 403. The `observed_on`
field records the research observation, **not** an official source date.

The existing 106-authority robot reads these as extra bounded discovery
landing pages. They add no public population, parser binding, source edition,
data record or approval. Each hint must match the exact territorial URL
prefix of an already configured official baseline. An unknown authority,
off-origin URL, duplicate, invalid status or already selected authority
fails closed. Existing capture and retry budgets are unchanged.

Current authority coverage is not increased by adding hints. Only an exact
archival capture, independent byte/row QA, both-population review, a finite
intent and the sole publisher's five-asset live readback can do so. A 403
remains an access result rather than evidence that the publication is absent.

**28 November 2026 — Nuoro.** The Ministry's indexed [listed-company page](https://prefettura.interno.gov.it/it/prefetture/nuoro/white-list-elenco-imprese-iscritte) explicitly advertises an attachment labelled White List – Elenco imprese iscritte (314.37 KB in the index). It is an additional discovery-only seed, not a verified original or a source-edition date. The older official applicant page is explicitly historical and not updateable; no current applicant source is established. Keep that population unresolved and the authority mapping unreviewed. The existing host, territorial prefix, request/depth/time budgets and capture workflow are unchanged; do not infer absence from access failures. No public source or approval is added.
