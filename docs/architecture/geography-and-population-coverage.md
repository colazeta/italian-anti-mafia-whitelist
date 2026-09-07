# Geography enrichment and source-population completeness

This design is introduced before national parser scale-out because both geography and population completeness affect the meaning of the final dataset.

## 1. Address normalisation and geography are derived enrichment

A Prefecture publishes an address string. The archive preserves that source-supported value in the source/semantic/canonical address chain.

Routine address normalisation and stricter geographic enrichment are separate downstream layers:

```text
source address
   ↓
canonical address
   ↓
configurable geocoder
   ↓
geo.address_geocode_result
   ├─→ mart.address_normalisation
   └─→ accepted coordinate only
            ↓
      geo.address_geographic_unit
            ↓
      mart.address_geography
```

The source address remains unchanged even when a geocoder returns a cleaner address or a later official territorial crosswalk improves the classification.

The production normalisation design is documented in `docs/architecture/address-normalisation.md`.

## 2. Standard normalised and statistical geography fields

`mart.address_normalisation` is designed to expose the current provider-normalised form of an address, including where available:

- normalised address label;
- street name;
- house/civic number;
- postal code;
- locality;
- level-2 and level-1 administrative names;
- country name/code;
- candidate coordinates and precision;
- provider endpoint/version/data timestamp and attribution/licence.

`mart.address_geography` is deliberately stricter. It exposes coordinates only from an accepted result and can additionally expose:

- ISTAT municipality code + name;
- province / metropolitan-city / autonomous-province code + name + type;
- ISTAT region code + name;
- NUTS 1 code + name + version;
- NUTS 2 code + name + version;
- NUTS 3 code + name + version.

This separation allows routine normalisation to stay simple without weakening the evidential standard of the statistical geography layer.

## 3. Versioning of territorial classifications

Territorial classifications change and must be treated as versioned reference data.

For Italian administrative units the authoritative reference is ISTAT/SITUAS. The current project crosswalk uses the Istat state effective **21 February 2026** and retains current/historical municipality-code variants, Belfiore/cadastral code and NUTS 2021/2024 fields. Historical reconstruction can use SITUAS where the geography effective at an earlier observation date is required.

For European statistical geography the current reference is **NUTS 2024**. The archive stores NUTS level and version separately from Italian administrative codes.

## 4. Geocoding result model

`geo.address_geocode_result` is candidate-based rather than a single pair of columns on `core.address`.

Each result can record:

- provider, endpoint and version;
- provider data-update timestamp;
- provider result id when available;
- exact query text;
- candidate rank;
- accepted/candidate/rejected/not-found/error status;
- latitude/longitude;
- spatial precision (`address`, `rooftop`, `parcel`, `street`, `postal_code`, `locality`, `admin`, `centroid`, `unknown`);
- matched/normalised address fields;
- provider attribution/licence;
- original provider candidate payload;
- processing activity and system time.

Only one current `accepted` geocode may exist for an address. Candidate and rejected results remain auditable.

The archive does **not** assume that every address-level result is rooftop-level. For example, a Nominatim house/building result can be an address point or an object centroid and is therefore conservatively labelled `address`.

## 5. Administrative/statistical assignments

`geo.geographic_unit` stores versioned reference units using:

- `scheme_code` (for example `ISTAT_ADMIN`, `NUTS`);
- `scheme_version`;
- level;
- code;
- name;
- parent unit;
- effective period.

`geo.address_geographic_unit` then links an address to one or more units using an explicit assignment method:

- point-in-polygon;
- geocoding-provider response;
- official crosswalk;
- text match;
- manual review.

This supports both a spatial workflow and a deterministic official-code workflow.

## 6. Geocoding provider strategy and long-term feasibility

No provider is hard-coded into the ontology or database schema.

The first implementation is Nominatim-compatible because it provides free/open address search and a structured GeocodeJSON output. The endpoint is runtime configuration and can be switched between a public, managed or self-hosted Nominatim implementation without changing downstream tables.

The OSM Foundation public endpoint is **not** treated as recurring national infrastructure. It is allowed only through explicit opt-in for a deliberate small one-off pilot and the client enforces policy-aware throttling and persistent caching. Scheduled national operation must use a managed or self-hosted endpoint.

This means recurring geocoding costs and traffic scale mainly with new/changed canonical addresses rather than with the full historical archive.

ANNCSU and Istat remain optional downstream official validation/enrichment sources. Their availability does not block routine address normalisation.

## 7. Mandatory White List source populations

The second invariant is source completeness.

For the ordinary White List publication model we expect two logical populations:

1. `listed` — entities already represented in the White List publication;
2. `applicant` — entities that have submitted an application / are in the procedural population.

The physical publication can represent them in different ways:

```text
A) listed.pdf      + applicants.pdf
B) listed HTML     + applicants HTML
C) one combined PDF/table containing both
D) comprehensive listed list + sector files + applicant list
```

Physical separation does not change the logical requirement.

## 8. The two-target completeness ledger

`white-list-source-population-coverage` builds a coverage ledger from:

- `verified_primary_pages.csv`;
- `source_series_inventory.csv`.

For every verified authority/register scope it creates exactly two mandatory target rows:

```text
listed
applicant
```

Coverage status can be:

- `COVERED_SEPARATE_SERIES`;
- `COVERED_COMBINED_SERIES`;
- `UNRESOLVED_REQUIRES_REVIEW`.

A register scope is `source_population_complete = true` **only when both target populations are covered**.

This means that finding the listed-company PDF never allows the discovery workflow to declare the Prefecture complete if the applicant population has not also been accounted for.

## 9. Combined publications

A source series with `population_scope = listed_and_applicant` satisfies both logical targets.

Example: the current Cosenza combined source is one physical series but covers both logical populations. It must not be duplicated into two fake physical sources.

## 10. Missing is not “not published”

If the registry currently knows only a listed series, the applicant target becomes:

`UNRESOLVED_REQUIRES_REVIEW`

It does **not** become `NOT_PUBLISHED`.

That distinction is essential: failure to discover a source is not evidence that the authority does not publish the population.

An explicit `NOT_PUBLISHED_CONFIRMED` state should only be introduced later if supported by evidence and a defined review rule.

## 11. Multiple registers/regimes

Completeness is assessed per register/regime, not merely per authority.

Bologna demonstrates why: the ordinary provincial White List and the post-earthquake regime are distinct scopes. Discovering both populations for the ordinary register cannot silently satisfy the special-register coverage requirement.

## 12. Current baseline effect

With the current 34 verified authority pages and 59 inventoried source series, the deterministic coverage generator creates **35 register/regime scopes**.

At the current inventory stage:

- **30 scopes** account for both `listed` and `applicant`;
- **5 scopes** remain incomplete/unresolved: Bari, Crotone, Milano, Sassari and Udine.

These numbers are a discovery-progress metric, not a statement that applicants are absent in the unresolved authorities.

## 13. Scale-out rule

Before a source family is considered production-ready for a Prefecture/register:

1. resolve the relevant register/regime scope;
2. account for `listed`;
3. account for `applicant`;
4. identify whether they are separate or combined;
5. inventory all physical source series;
6. bind each series to a validated parser family;
7. validate that parser output preserves the population role;
8. only then mark source-population coverage complete.

This rule is enforced by tests so that national scale-out cannot regress into “we found one White List file, therefore this Prefecture is done”.
