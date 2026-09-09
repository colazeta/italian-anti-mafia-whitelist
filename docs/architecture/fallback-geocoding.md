# Fallback geocoding operating contract

## Purpose

Fallback geocoding is the second-stage address-enrichment path used only when the official-first Italian ANNCSU path cannot provide a usable candidate, or when the source-supported country routing makes ANNCSU inapplicable.

It is not a replacement for ANNCSU and it does not rewrite `core.address`.

## Eligibility

A canonical address is eligible for exactly one of three auditable reasons:

1. `source_foreign` — current `geo.address_country_assessment.route_code = 'foreign_fallback'`; the source-supported ISO alpha-2 country is passed to the provider as a country filter.
2. `country_unresolved` — current route is `unresolved_fallback`; no country filter is invented.
3. `anncsu_not_found` — current route is `italian_anncsu`, a current ANNCSU `not_found` result exists, and no current ANNCSU `candidate` or `accepted` result exists. The fallback request is constrained to Italy and stores the exact upstream ANNCSU result id.

An address with a current ANNCSU candidate is never eligible merely to search for a more convenient alternative.

## Provider contract

Production fallback uses a configurable **managed or self-hosted Nominatim-compatible HTTPS endpoint**. The recurring fallback runner never enables the public OSMF Nominatim service.

The provider must expose `/status` with at least a software/database version or data-update timestamp. This identity is persisted with every run and is part of the cache decision.

The same source-supported address string is sent to the provider unchanged. Hidden preprocessing, fuzzy rewriting and provider-specific address mutation are outside this stage.

## Result policy

Fallback matches are always persisted as `candidate`. There is no automatic-acceptance option in the fallback runner. `mart.address_geography` therefore remains accepted-only and fallback output cannot enter geographic truth without a later separately validated promotion decision.

Country-constrained searches fail closed if the provider returns candidates outside the requested country.

`mart.address_normalisation` exposes:

- provider and provider version;
- `routing_stage_code = 'fallback'`;
- the explicit `routing_reason_code`;
- the upstream ANNCSU result id where applicable;
- the fallback run id.

Within the same result status, official ANNCSU output ranks ahead of fallback output in the normalisation mart.

## Cache and refresh semantics

Current fallback `candidate` and `not_found` results are reused only when all of the following remain unchanged:

- provider endpoint;
- provider software/database version;
- provider data-update timestamp.

Provider `error` results are not treated as durable cache hits.

Consequently:

- a same-version rerun performs no search requests for already resolved/not-found eligible addresses;
- a new eligible address causes only that address to be queried;
- a provider version/data update causes the currently eligible population to be refreshed;
- a successful refresh closes previous current fallback results for that address, including results from an older endpoint;
- previously current fallback results are expired when their address no longer satisfies the eligibility contract.

The operational evidence is persisted in `geo.fallback_geocode_run` and `geo.fallback_geocode_run_item`.

## Validation gate

The repository workflow `Fallback geocoding validation` runs against a deterministic local Nominatim-compatible endpoint rather than the public OSMF service. Its end-to-end fixture covers:

- an ANNCSU-not-found address in Calabria;
- an ANNCSU-not-found address in Toscana;
- a source-explicit French address;
- a country-unresolved address;
- a newly added Toscana address;
- same-version cache reuse;
- provider-version refresh;
- stale-result expiration after a routing change;
- zero automatic acceptance.

This validates orchestration and provenance semantics without treating a test geocoder as empirical evidence of real-world fallback precision. Any future preprocessing/fuzzy stage must still be evaluated against the frozen Cosenza and Pistoia reviewed gold standards.
