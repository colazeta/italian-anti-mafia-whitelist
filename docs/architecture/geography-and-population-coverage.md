# Geography enrichment and source-population completeness

This design is introduced before national parser scale-out because both geography and population completeness affect the meaning of the final dataset.

## 1. Geography is derived enrichment, not a rewrite of the source

A Prefecture publishes an address string. The archive preserves that exact source-supported value in the source/semantic/canonical address chain.

Geocoding and statistical territorial classification happen downstream:

```text
source address
   ↓
canonical address
   ↓
geo.address_geocode_result
   ↓
geo.address_geographic_unit
   ↓
mart.address_geography
```

The source address remains immutable even when a later geocoder or official territorial crosswalk improves the location.

## 2. Statistical geography fields

The wide `mart.address_geography` surface is designed to expose, where available:

- latitude;
- longitude;
- coordinate precision;
- geocoding provider/version/confidence;
- ISTAT municipality code + name;
- province / metropolitan-city / autonomous-province code + name + type;
- ISTAT region code + name;
- NUTS 1 code + name + version;
- NUTS 2 code + name + version;
- NUTS 3 code + name + version.

This is deliberately richer than storing a generic `city` string because the intended uses include statistical aggregation, spatial joins and longitudinal research.

## 3. Versioning of territorial classifications

Territorial classifications change and must be treated as versioned reference data.

For Italian administrative units the authoritative reference is ISTAT/SITUAS. As of the current development date, ISTAT reports its administrative-unit codes updated to **21 February 2026** and explicitly notes the 2026 Sardinian territorial recoding. A municipality/province/region code must therefore carry the applicable scheme version/effective period rather than being treated as timeless.

For European statistical geography the current reference is **NUTS 2024**, applied from the first reference quarter of 2024. The archive stores NUTS level and NUTS version separately from Italian administrative codes.

Reference sources:

- ISTAT, “Codici statistici delle unità amministrative territoriali: comuni, città metropolitane, province e regioni”.
- Eurostat, “NUTS 2024”.

## 4. Geocoding result model

`geo.address_geocode_result` is candidate-based rather than a single pair of columns on `core.address`.

Each result records:

- provider and provider version;
- provider result id when available;
- candidate rank;
- accepted/candidate/rejected/not-found/error status;
- latitude/longitude;
- spatial precision (`rooftop`, `parcel`, `street`, `postal_code`, `locality`, `admin`, `centroid`, `unknown`);
- confidence;
- matched address;
- processing activity and system time.

Only one current `accepted` geocode may exist for an address. Candidate and rejected results remain auditable.

The archive does **not** assume that every provider coordinate is rooftop-level. A municipality centroid can be useful statistically, but must be labelled as `centroid`/`locality`, never presented as an exact business location.

## 5. Administrative/statistical assignments

`geo.geographic_unit` stores versioned reference units using:

- `scheme_code` (e.g. `ISTAT_ADMIN`, `NUTS`);
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

## 6. Geocoding provider strategy

No provider is hard-coded into the ontology.

The production ingestion layer should expose a provider interface and cache every attempted result. Provider-specific licensing, rate limits and redistribution constraints belong to acquisition/configuration policy rather than to the canonical address model.

A national run should prefer reproducible/bulk-suitable services or controlled infrastructure; it should not silently depend on a public endpoint intended only for light interactive use.

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

With the current 34 verified authority pages and 28 inventoried source series, the deterministic coverage generator creates **35 register/discovery scopes** (Bologna contributes a second special-regime scope).

At the current inventory stage:

- 12 scopes already account for both populations;
- 23 remain incomplete/unresolved and therefore cannot be counted as source-series complete.

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
