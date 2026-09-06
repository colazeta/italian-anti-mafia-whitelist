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

### `pilot_source_profiles.csv`

A deliberately heterogeneous pilot sample used to design source-series and parser taxonomy before attempting national parsing. It records publication models, populations, formats and historical-snapshot signals.

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
