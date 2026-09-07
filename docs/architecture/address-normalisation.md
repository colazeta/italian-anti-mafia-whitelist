# Address normalisation and geocoding

## Design goal

Address normalisation is a routine enrichment step, not a separate territorial-data project.

The production chain is:

```text
source-supported canonical address
        ↓
provider-agnostic geocoder interface
        ↓
standard normalised address fields + candidate coordinates
        ↓
optional acceptance for geography
        ↓
optional official ANNCSU / Istat validation and statistical enrichment
```

The geocoder never overwrites `core.address`. Provider output is stored in `geo.address_geocode_result` and exposed through `mart.address_normalisation`.

## Standard normalised fields

The provider-neutral projection currently stores:

```text
normalised address label
street name
house number
postal code
locality
admin unit level 2
admin unit level 1
country name
country code
latitude
longitude
coordinate precision
```

It also preserves:

```text
provider name
provider endpoint
provider software version
provider data-update timestamp
provider result identifier
query text
candidate rank
attribution
licence
original provider candidate payload
processing activity / configuration hash
```

Provider-specific fields that are not part of the common address contract remain in `provider_payload` rather than leaking into the canonical schema.

## Baseline query rule

The production baseline sends the source-supported canonical address to the provider **once and unchanged**. It does not attempt municipality parsing, fuzzy rewriting, abbreviation expansion or cascading retry heuristics.

A controlled pilot tested a lightweight syntactic retry on difficult Prefecture strings. It increased provider requests without recovering the failed examples, so it was deliberately excluded from production. Any future preprocessing must therefore demonstrate a measurable improvement on a representative validation sample before being introduced.

This keeps network cost predictable and makes geocoding quality attributable to the provider rather than to hidden address-rewriting logic.

## Nominatim-compatible first provider

The first implementation uses the Nominatim Search API with `format=geocodejson` and `addressdetails=1`. GeocodeJSON is preferred because Nominatim documents it as the more stable address-category representation.

The endpoint is runtime configuration. The database does not distinguish architecturally between:

- the OSM Foundation public Nominatim service;
- a managed third-party Nominatim-compatible service;
- a self-hosted Nominatim instance.

Changing provider infrastructure therefore does not require a database migration.

## Public OSMF Nominatim is a pilot route, not production infrastructure

As of 7 September 2026, the OSM Foundation public-service policy states that:

- the absolute maximum is 1 request per second;
- applications must send an identifying User-Agent or Referer;
- results must be cached for bulk use;
- periodic requests are considered bulk geocoding and are strongly discouraged;
- scripts running longer than a day or at regular intervals are restricted to 4 requests per minute;
- applications should be capable of switching provider without requiring a software update;
- larger or regular requirements should use a third-party provider or a self-hosted Nominatim instance.

Consequently the project enforces the following:

1. `nominatim.openstreetmap.org` requires an explicit `--allow-public-nominatim` opt-in.
2. The client enforces at least a 1-second interval on that endpoint.
3. The public endpoint refuses batches above 2,000 unique queries.
4. Existing `accepted`, `candidate` and `not_found` results are a persistent database cache and are skipped unless `--refresh` is requested.
5. Identical query strings are deduplicated within a run.
6. No scheduled/recurring project workflow may use the public OSMF endpoint.

The public endpoint is therefore suitable for a deliberate small one-off pilot such as Cosenza, but it is not a dependency of the national architecture.

## Long-term operating model

For national recurring ingestion the preferred operational order is:

```text
1. managed Nominatim-compatible endpoint
2. self-hosted Nominatim if volume, cost or control justify operating it
```

A managed endpoint is the default long-term assumption because it avoids running and updating a specialised PostgreSQL/PostGIS search stack. Self-hosting remains technically feasible: Nominatim explicitly supports regional/country OSM extracts and incremental updates. It is nevertheless a material infrastructure commitment. The official Nominatim documentation recommends roughly 128 GB RAM and at least 1 TB disk for a full-planet installation; country extracts substantially reduce the imported dataset, but their exact hardware requirement depends on scope and update strategy and should be benchmarked before committing to self-hosting.

The choice is operational, not architectural. The command remains:

```text
white-list-normalise-addresses \
  --dsn "$DATABASE_URL" \
  --endpoint "$GEOCODER_ENDPOINT"
```

Only new/unseen canonical addresses require network calls. Existing addresses remain cached until an explicit refresh is justified, so recurring costs scale with address churn rather than total database size.

## Pilot evidence

A one-shot, policy-compliant integration test against the public OSMF endpoint used three real address strings extracted from the Cosenza White List source. The complete path `core.address -> provider -> persistence -> mart.address_normalisation` succeeded with no provider/runtime errors.

The sample also showed why normalisation and acceptance must remain separate: one address produced street-level candidates, while two source strings produced no result, and **none** was automatically accepted as an address-level coordinate. The pipeline therefore proved technically viable without converting imperfect geocoder coverage into false precision.

## Acceptance policy

Normalisation and geographic acceptance are deliberately separate.

A provider result is automatically marked `accepted` only when:

- the provider returns exactly one candidate;
- the candidate is address/building level;
- a house number is present;
- latitude and longitude are present.

All other returned results remain `candidate`. `not_found` and `error` are explicitly represented. No artificial numerical confidence score is generated.

`mart.address_normalisation` exposes the best current result even when it remains a candidate. `mart.address_geography` continues to expose coordinates only from accepted results.

## Coordinate precision

Nominatim address/building results are labelled `address`, not `rooftop`. A Nominatim point can be an address point or the centroid of an OSM object, so claiming rooftop precision would be stronger than the source supports.

## Official Italian enrichment remains available

The ANNCSU and Istat acquisition work remains useful but becomes optional downstream validation/enrichment:

- ANNCSU can corroborate Italian civic-access coordinates or provide an official alternative;
- Istat can attach official municipality codes, administrative units and NUTS versions;
- SITUAS can support historical territorial reconstruction when required.

None of these sources blocks routine address normalisation.

## Licensing and provenance

Nominatim/OpenStreetMap output carries ODbL attribution/licensing requirements. The pipeline stores the provider attribution and licence alongside each result. Any public release or interface exposing derived OSM address data must preserve the applicable attribution and comply with the provider/data licence.
