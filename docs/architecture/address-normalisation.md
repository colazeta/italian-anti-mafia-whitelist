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

For national recurring ingestion, one of the following must be configured:

```text
managed Nominatim-compatible endpoint
                OR
self-hosted Nominatim
```

The choice is operational, not architectural. The command remains:

```text
white-list-normalise-addresses \
  --dsn "$DATABASE_URL" \
  --endpoint "$GEOCODER_ENDPOINT"
```

Only new/unseen canonical addresses require network calls. Existing addresses remain cached until an explicit refresh is justified, so recurring costs scale with address churn rather than total database size.

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
