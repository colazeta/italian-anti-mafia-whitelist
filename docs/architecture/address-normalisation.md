# Address normalisation and geocoding

## Design goal

Address normalisation is derived, provenance-aware enrichment. It must never rewrite or launder the address published by a source authority.

The common production contract is:

```text
source-supported canonical address
        ↓
versioned provider / linkage process
        ↓
standard normalised fields + candidate coordinates
        ↓
validation / optional acceptance
        ↓
statistical geography
```

`core.address` remains immutable source-supported evidence. Provider output is stored in `geo.address_geocode_result` and exposed through `mart.address_normalisation`. `mart.address_geography` remains accepted-only.

## Provider order for Italian addresses

The Cosenza experiments support an official-first operating order:

```text
Italian source address
        ↓
exact municipality prefix against versioned Istat crosswalk
        ↓
ANNCSU exact ODONIMO / typed-street linkage
        ↓
exact civic/access linkage when available
        ↓
ANNCSU candidate normalisation / coordinates
        ↓
unresolved remainder → optional configurable geocoder fallback
```

Addresses that cannot be placed in an Italian municipality, including foreign addresses, can go directly to the configurable geocoder layer.

This is a provider-order decision, not a schema fork: ANNCSU and Nominatim-compatible providers persist through the same provider-neutral result contract.

## Why ANNCSU is primary for Italian addresses

ANNCSU is the national reference for municipal street and address registers maintained by Istat and the Agenzia delle Entrate. Its open-data service provides bulk regional/national datasets, so national enrichment does not require one remote geocoder request per White List row.

Operational advantages include:

- official municipality-certified street/address identities;
- free bulk acquisition;
- reproducible regional inputs with SHA-256 identities;
- local linkage after acquisition;
- no public-geocoder one-request-per-second bottleneck;
- explicit separation between linkage quality and the coordinate method published by ANNCSU.

A run records the ANNCSU provider version and CSV hash, Istat crosswalk version and hash, provider endpoint and linkage configuration hash.

## Conservative municipality resolution

The municipality is resolved only when the canonical source string begins with an exact official Istat municipality name after token-level case, diacritic and punctuation folding.

Allowed normalisation is deliberately narrow:

- case folding;
- diacritic folding;
- punctuation/token boundary equivalence;
- validation and removal of an explicit parenthetical province marker such as `(CS)`.

There is no edit distance, fuzzy municipality matching or inferred abbreviation expansion. A conflicting province marker is rejected. The source address is never changed; the split is derived linkage input only.

On the frozen Cosenza corpus this exact-Istat rule resolves the municipality prefix for 1,258 of 1,298 canonical addresses (96.92%).

## Conservative ANNCSU street identity

The production linker uses **ANNCSU `ODONIMO` only** as the provider street identity and display field. `DIZIONE_LINGUA1/2` are separate metadata fields and are never indexed or displayed as an odonym.

Street matching is exact after a small deterministic normalisation of road-type spelling. Road type remains part of identity.

Examples:

```text
C/da Padula       → contrada|padula
CONTRADA PADULA   → contrada|padula
S.S. 18           → ss|18
STRADA STATALE 18 → ss|18
Via Roma          → via|roma
Piazza Roma       → piazza|roma
```

The last two keys remain different. A source `Via Petraro` cannot silently match ANNCSU `Contrada Petraro` merely because the name token is the same.

A normalised `(Comune, typed-street-key)` must identify exactly one ANNCSU `PROGRESSIVO_NAZIONALE`. If multiple official street identities collapse to the same key, the result is ambiguous and no candidate is emitted.

No fuzzy/edit-distance street matching is used in the exact production layer.

## Civic linkage

A civic number is extracted only when it is a confident terminal civic token. An optional exponent such as `33/A` is preserved; ranges such as `63/65` are not silently reduced to one civic.

`SNC`/`SN` is represented as explicitly lacking a standard civic. Route numbers such as `S.S. 18` are not treated as house numbers.

When a confident civic exists, ANNCSU linkage requires exact number and exponent. An access result is direct only when the surviving `PROGRESSIVO_ACCESSO` / coordinate / provider-method identity is unique.

## Coordinate precision

ANNCSU coordinates are never generically labelled `rooftop`.

### `civic_access`

A unique exact ANNCSU access with a coordinate pair is represented as:

```text
precision = civic_access
coordinate_derivation = provider_civic_access
```

This means the coordinate belongs to the official civic-access/entrance record. ANNCSU `METODO` is retained in `provider_payload`; it is provider evidence, not a fabricated confidence score.

### `street`

When an exact unique street is established but the requested civic cannot provide a usable point, a street-level candidate may be produced if that exact ANNCSU street contains coordinate-bearing accesses. Its deterministic point is the median latitude/longitude of coordinate-bearing accesses for that exact official street:

```text
precision = street
coordinate_derivation = median_of_anncsu_street_access_coordinates
```

The access count used for the derivation is stored in the payload. This result is explicitly street-level, never address/civic precision.

An exact street can also be represented without coordinates when ANNCSU contains no usable coordinate pair for that street. Such a candidate cannot enter accepted geography.

## Cosenza experiments

### Nominatim baseline

The full free-form Nominatim baseline attempted all 1,298 canonical Cosenza addresses without runtime errors but matched only 447 (34.44%). Of those matches, 435 were street-level and only six were address-level.

A paired 200-address experiment then compared raw free-form, Nominatim structured search and comma-recomposed free-form search. None materially improved validated coverage after municipality/street consistency checks. Query-syntax tuning was therefore stopped rather than adding increasingly opaque heuristics.

### Strict ANNCSU benchmark

A strict exact-only benchmark established that official bulk linkage was viable without fuzzy matching. It also exposed two important safeguards that were subsequently enforced in production:

- road type must remain part of street identity;
- only ANNCSU `ODONIMO`, not `DIZIONE_LINGUA1/2`, may define or label the street.

### Production smoke on frozen Cosenza inputs

The final production pipeline was executed end-to-end against:

- the frozen 1,298 Cosenza canonical addresses;
- Istat municipality crosswalk version `2026-02-21`;
- ANNCSU Calabria indirizzario version `2026-08-03`;
- hash-verified copies of both reference inputs.

Observed production results:

- canonical addresses attempted: **1,298 / 1,298**;
- ANNCSU candidates: **624 (48.07%)**;
- terminal provider-specific `not_found`: **674 (51.93%)**;
- runtime/provider errors: **0**;
- unprocessed: **0**;
- `civic_access` candidates: **309**;
- `street` candidates: **260**;
- exact normalised candidates without a coordinate precision: **55**;
- candidates with latitude/longitude: **534 / 624 (85.58%)**;
- candidates with a source-supported/exact house number retained: **364 / 624 (58.33%)**;
- automatically accepted ANNCSU results: **0**.

Among the 260 street-precision candidates, 225 carry the deterministic street median coordinate and 35 expose exact street normalisation without a coordinate. The 55 precision-null candidates correspond to an exact unique civic/access linkage for which ANNCSU does not provide a usable coordinate and the exact street has no usable coordinate fallback.

These figures are measurements, not hard-coded quality thresholds. They establish the baseline to validate manually before any acceptance policy or recall-oriented second stage is introduced.

## Candidate-by-default policy

Neither ANNCSU nor Nominatim output is promoted automatically to geographic truth.

Successful exact ANNCSU linkage is persisted as `candidate`. Every attempted non-candidate terminal outcome is persisted as provider-specific `not_found`, with the exact resolution reason in `provider_payload`.

Here `not_found` means **no usable ANNCSU candidate under the exact linkage policy**, not that the real-world address does not exist.

This gives complete accounting while preserving distinctions such as:

- exact candidate;
- ambiguous street or civic linkage;
- no exact street;
- municipality not exactly resolvable;
- address outside the regional input;
- other terminal reasons.

Candidate coordinates never leak into `mart.address_geography`.

## Standard fields and provenance

The provider-neutral result can expose:

```text
normalised address label
street name
house number
postal code
locality
administrative units
country name / code
latitude / longitude
coordinate precision
```

It also preserves:

```text
provider name / endpoint / version / data date
provider result identifier
query/source text
candidate rank
attribution / licence
provider / derivation payload
processing activity / configuration hash
```

ANNCSU identifiers, `METODO`, matching policy, coordinate derivation and Istat/cadastral linkage stay in provider payload rather than leaking into the canonical address schema.

## Licensing

ANNCSU public data are published under **CC-BY 4.0**. ANNCSU provider attribution and licence are stored with derived results and must be retained in downstream publication.

Nominatim/OpenStreetMap-derived output continues to carry the applicable OpenStreetMap/ODbL attribution and licensing requirements when that provider is used.

## Long-term feasibility

The official-first design removes the need for a national per-row public-geocoder batch.

For Italian addresses the scalable path is:

1. acquire each required ANNCSU regional bulk file once per provider version;
2. acquire/version the Istat municipality crosswalk;
3. link locally with deterministic exact rules;
4. cache provider-version results in PostgreSQL;
5. validate candidates before acceptance;
6. send only unresolved/foreign cases to a configurable fallback when justified;
7. benchmark any future normalising/fuzzy stage against a frozen manual validation set before adoption.

National growth therefore scales primarily with bulk regional file acquisition and local processing, rather than the number of geocoder API calls.

The public OSMF Nominatim service remains appropriate only for controlled small experiments. If a recurring fallback geocoder becomes material, the same database contract can use a managed or self-hosted endpoint.
