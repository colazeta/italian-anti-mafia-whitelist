# National ANNCSU regional orchestration

Status: implemented behind regression and multi-region live validation gates.

## Purpose

The national White List archive must not treat address enrichment as one national geocoding request stream. ANNCSU publishes official bulk address datasets by region (with separate autonomous-province datasets for Bolzano and Trento). The archive therefore derives the smallest provider-input set required by the current, defensibly Italian canonical address population and processes those files locally.

Public OSMF Nominatim is not part of recurring national bulk processing.

## Planning contract

`white-list-anncsu-national` starts from `core.address` and the current `geo.address_country_assessment` produced by the source-country routing layer.

Only addresses whose current route is `italian_anncsu` are eligible. The versioned Istat municipality crosswalk is then used again to establish the exact municipality, region and, where necessary, autonomous-province scope. No fuzzy municipality inference is introduced by the orchestrator.

For each exact municipality assignment the orchestrator chooses one ANNCSU bulk dataset. A plan contains:

- total canonical address count;
- current `italian_anncsu` count;
- assignable and unassigned Italian-route counts;
- required region/dataset codes and address counts;
- a deterministic plan SHA-256 based on the regional assignment and source-address fingerprints, not the raw address strings.

An Italian-route address that cannot be mapped to one exact regional dataset fails closed into the plan's unassigned accounting. It is not converted into an ANNCSU `not_found` result.

## Provider-input cache

Each required dataset is acquired through the existing official ANNCSU bulk client. The client validates ZIP integrity and provider schema, derives the provider version from the official CSV member name, computes physical SHA-256 identities for both ZIP and CSV, and refuses silent replacement by different bytes.

The national cache is organised by dataset code and retains versioned manifests and physical files. Before reuse, both cached ZIP and CSV are re-hashed against their manifest. The latest valid provider version present in the cache is selected unless `--refresh-provider-inputs` is requested.

A provider refresh is limited to regions in the current plan. If the refreshed provider version is unchanged, existing same-version address results are skipped. If the provider version changes, the region is reprocessed under the new version. If only new addresses are introduced under an unchanged version, only those addresses are processed.

## Regional enrichment contract

The orchestrator does not call the single-region pilot against the full national address table. It passes each regional run an explicit address-id scope. This prevents addresses belonging to another region from being misclassified as `outside_dataset_region` and then recorded as provider `not_found`.

Within the scoped set, the existing audited linkage policy is unchanged:

1. exact Istat municipality prefix;
2. exact canonical typed-street/ODONIMO key;
3. exact civic number and exponent where confidently present;
4. street-coordinate fallback only under the existing ANNCSU policy;
5. every provider attempt becomes either `candidate` or provider-specific `not_found`;
6. candidates remain candidates and are never automatically accepted geography.

The regional worker aborts if a planned address resolves outside the assigned regional dataset.

## Provenance and accounting

`geo.anncsu_orchestration_run` records the national plan identity, Istat version/SHA, refresh mode, population accounting and run status.

`geo.anncsu_region_run` records, per required provider dataset:

- region and autonomous-province scope when applicable;
- ANNCSU dataset code, provider version and endpoint;
- ZIP and CSV SHA-256;
- whether provider bytes were acquired, reused or refreshed;
- planned, processed and same-version-skipped addresses;
- candidate and `not_found` counts;
- success/failure status.

Database constraints require `candidate + not_found = processed` and `processed + skipped = planned` for every regional row.

## Validation gates

Unit and database tests cover the dataset map, fail-closed mapping, cache integrity and run-accounting constraints.

Production readiness additionally requires a live GitHub-hosted multi-region run using current SHA-pinned official White List sources. The gate must demonstrate at least two regions, reuse the same cached provider inputs on a second pass, add a new address without reprocessing the existing population, and verify the resulting provider-version/hash provenance in PostgreSQL.

The regional dataset-code catalogue is also probed against the official ANNCSU endpoint in the live gate. A code is accepted only when the official endpoint returns a ZIP signature.
