# Address normalisation and geocoding

## Design goal

Address normalisation is a derived, provenance-aware enrichment step. It must never rewrite or launder the address published by the source authority.

The production contract remains provider-neutral:

```text
source-supported canonical address
        ↓
versioned provider / linkage process
        ↓
standard normalised address fields + candidate coordinates
        ↓
validation / optional acceptance
        ↓
statistical geography
```

`core.address` is immutable source-supported evidence. Derived provider output is stored in `geo.address_geocode_result` and exposed through `mart.address_normalisation`. `mart.address_geography` remains accepted-only.

## Evidence-based provider order

The Cosenza pilot changed the preferred operating order for **Italian** addresses.

```text
Italian source address
        ↓
exact municipality prefix against versioned Istat crosswalk
        ↓
ANNCSU exact typed-street linkage
        ↓
exact civic/access linkage when available
        ↓
ANNCSU candidate normalisation / coordinates
        ↓
unresolved remainder → optional configurable geocoder fallback
```

For addresses that cannot be placed in an Italian municipality, including foreign addresses, the configurable geocoder remains available directly.

This is a provider-order decision, not a schema fork: ANNCSU and Nominatim-compatible providers both persist through the common `geo.address_geocode_result` contract.

## Why ANNCSU is primary for Italian addresses

ANNCSU is the national reference for municipal street and address registers maintained by Istat and the Agenzia delle Entrate. Its open-data service provides regional and national bulk datasets, with monthly bulk updates and daily point/API updates. The bulk route therefore scales without per-address network calls.

For recurring national operation this has important advantages:

- official municipality-certified street/address identity;
- free bulk acquisition;
- no one-request-per-second geocoding bottleneck;
- versionable input files with reproducible SHA-256 identities;
- regional processing for bounded resource use;
- stable separation between linkage quality and the coordinate method published by ANNCSU.

The project uses the bulk regional indirizzario as the reproducible production input. A run records the ANNCSU dataset version, physical CSV hash, Istat crosswalk version/hash and linkage configuration hash.

## Conservative Italian municipality resolution

The municipality is resolved only when the canonical source string begins with an exact official Istat municipality name after token-level case, diacritic and punctuation folding.

Allowed normalisation is deliberately narrow:

- case folding;
- diacritic folding;
- punctuation/token boundary equivalence;
- validation and removal of an explicit parenthetical province marker such as `(CS)`.

There is no edit distance, fuzzy municipality matching or inferred abbreviation expansion. A conflicting explicit province marker is rejected. The source address is never changed; the split exists only as derived linkage input.

On the frozen Cosenza corpus this exact-Istat rule can split 1,258 of 1,298 canonical addresses (96.92%). The unresolved remainder remains explicit rather than guessed.

## Conservative ANNCSU street identity

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

The last two keys are intentionally different. A source `Via Petraro` cannot silently match ANNCSU `Contrada Petraro` simply because the name token is the same.

A normalised `(Comune, typed-street-key)` must identify exactly one ANNCSU `PROGRESSIVO_NAZIONALE`. If multiple official street identities collapse to the same normalised key, the result is ambiguous and no candidate is emitted.

No fuzzy/edit-distance street matching is used in the production exact layer.

## Civic linkage

A civic number is extracted only when it is a confident terminal civic token. The parser preserves an optional exponent such as `33/A` and does not silently reduce ranges such as `63/65` to one civic.

`SNC`/`SN` is represented as explicitly lacking a standard civic. Route numbers such as `S.S. 18` are not treated as house numbers.

When the source has a confident civic, the ANNCSU match requires exact number and exponent. An exact access identity is used only when the surviving `PROGRESSIVO_ACCESSO`/coordinate/provider-method identity is unique.

## Coordinate precision

ANNCSU coordinates are not generically labelled `rooftop`.

### `civic_access`

When a unique exact ANNCSU access has a coordinate pair, the result is labelled:

```text
precision = civic_access
coordinate_derivation = provider_civic_access
```

This means the coordinate belongs to the official civic-access/entrance record represented by ANNCSU. The ANNCSU `METODO` value is retained in `provider_payload`; it is provider evidence, not a fabricated confidence score.

### `street`

When an exact unique street is established but the requested civic cannot provide a usable point, a street-level candidate may be emitted if that exact ANNCSU street contains coordinate-bearing access rows. Its point is the deterministic median latitude/longitude of the coordinate-bearing accesses for that exact official street:

```text
precision = street
coordinate_derivation = median_of_anncsu_street_access_coordinates
```

This fallback is deliberately labelled `street`, not address/civic precision. The number of access coordinates used is recorded in the payload.

If the exact ANNCSU street contains no usable coordinate pair, normalised street identity may still be exposed as a candidate with no coordinate. It cannot enter accepted geography.

## Cosenza evidence

The first full Nominatim free-form baseline processed all 1,298 canonical Cosenza addresses without runtime errors but matched only 447 (34.44%); 435 of those matches were street-level and only six were address-level. A 200-address paired experiment found no material validated improvement from Nominatim structured search or comma-recomposed free-form search.

The exact-only official benchmark was therefore tested against frozen Istat and ANNCSU inputs. Under the strict road-type-preserving policy, before any street-coordinate fallback:

- canonical addresses: 1,298;
- exact Istat municipality prefix: 1,258;
- exact unique typed ANNCSU street: 635 (48.92% of all addresses);
- exact unique civic access: 368 (28.35%);
- exact unique civic access with ANNCSU coordinate pair: 313 (24.11%);
- exact civic but ANNCSU coordinate missing: 55;
- exact civic ambiguity: 4;
- no fuzzy matching.

These figures are measurements, not hard-coded success thresholds. They establish a high-precision baseline on which future, separately validated recall improvements can be tested.

## Candidate-by-default policy

Neither ANNCSU nor Nominatim results are automatically promoted to geographic truth by normalisation.

The ANNCSU enrichment pipeline persists successful exact linkage as `candidate`. Every attempted terminal non-match is also persisted as a provider-specific `not_found`, with the exact resolution reason retained in `provider_payload`. Here `not_found` means **no usable ANNCSU candidate under this exact linkage policy**, not a claim that the real-world address does not exist.

This guarantees complete run accounting while preserving the distinction between:

- exact candidate;
- ambiguous linkage;
- no exact street;
- municipality not exactly resolvable;
- address outside the regional dataset;
- other terminal reasons.

Acceptance is a later validation policy. Candidate coordinates never leak into `mart.address_geography`.

## Standard normalised fields and provenance

The provider-neutral result can expose:

```text
normalised address label
street name
house number
postal code
locality
admin unit level 2
admin unit level 1
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
original or derived provider payload
processing activity / configuration hash
```

ANNCSU-specific identifiers, `METODO`, matching policy, street-coordinate derivation and Istat/cadastral linkage details remain in `provider_payload` rather than leaking into the canonical address schema.

## Licensing

The ANNCSU public consultation explicitly states that ANNCSU data are available under **CC-BY 4.0**. Provider attribution and licence are stored with ANNCSU results and must be preserved in downstream publication.

Nominatim/OpenStreetMap-derived output continues to carry its applicable ODbL attribution/licensing requirements when that provider is used.

## Long-term feasibility

The national architecture does not require a national per-row public-geocoder batch.

For Italian addresses the scalable path is:

1. acquire each required ANNCSU regional bulk file once per provider version;
2. acquire/version the current Istat municipality crosswalk;
3. link locally with deterministic exact rules;
4. cache provider-version results in PostgreSQL;
5. send only unresolved/foreign cases to a configurable fallback provider when justified;
6. compare any future fuzzy/normalising stage against a frozen validation sample before adoption.

ANNCSU bulk datasets are updated monthly, so refresh cost is dominated by regional file acquisition and local matching rather than the number of White List rows. This remains feasible when the archive expands from Cosenza to the national Prefecture population.

The public OSMF Nominatim service remains suitable only for controlled small experiments. If a recurring fallback geocoder becomes material, use a managed or self-hosted endpoint without changing the database contract.
