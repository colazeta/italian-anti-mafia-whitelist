# Where to see the data

This page is the authoritative human-readable guide to the data currently available in the project.

## Short answer

Start with [`../data/catalog.csv`](../data/catalog.csv) for persistent repository artifacts and the private **Dataset Explorer** for the actual reconstructed database population.

The project now distinguishes seven access/data layers:

1. [`../data/source_registry/`](../data/source_registry/) — national source discovery plus parser-family/binding/semantic-profile registries.
2. [`../data/captures/`](../data/captures/) — immutable capture manifests, parser-validation profiles and safe aggregate diagnostics.
3. **PostgreSQL `source.*`** — capture, parse runs, parsed records and raw source values.
4. **PostgreSQL `semantic.*`** — typed ontology-level observations, projection issues and resolution decisions.
5. **PostgreSQL `core.*` / `whitelist.*`** — guarded canonical entities, relationships, procedures and temporal states.
6. **Dataset Explorer checkpoint** — private self-contained browser generated from the reconstructed PostgreSQL population.
7. [`../data/releases/`](../data/releases/) — deliberately reviewed public/reuse products. There is currently no row-level public White List release.

## What is directly visible in GitHub

### National source and parser registry

`data/source_registry/` currently includes:

- `territorial_authorities.csv` — 106 territorial authorities;
- `verified_primary_pages.csv` — 34 independently verified primary White List landing pages;
- `source_series_inventory.csv` — 28 qualified recurring source series;
- `pilot_source_profiles.csv` — observed source/schema heterogeneity;
- `parser_families.csv` — validated reusable physical parser families;
- `parser_bindings.csv` — source-series → parser-family assignments;
- `semantic_profiles.csv` — record-contract → semantic-projector assignments;
- `cosenza_historical_editions.csv` — 11 dated Cosenza editions identified for longitudinal recovery.

The parser registry implements a deliberate rule: **not one parser per URL and not one universal parser**. A parser family can serve multiple source series when the schema/layout is validated as compatible.

### Cosenza capture and parser profiles

Parser v1 remains a historical QA baseline. Parser v2 is current and structures all seven observable columns from the combined Cosenza source.

The current parser-v2 profile records:

- 1,327 source observations on 28 June 2026;
- 1,334 on 3 August 2026;
- 2,661 v2 parsed observations;
- 18,627 v2 `SourceFieldValue` rows;
- 913 observed listing dates;
- 428 observed nominal expiry dates.

These are still **source-layer results**. Parsing itself does not establish canonical facts.

## What happens automatically after parsing

The corrected workflow no longer stops at `ParsedRecord`.

```text
ContentObject
  → ParseRun / ParsedRecord / SourceFieldValue
  → parser-family record contract
  → semantic projection
  → entity/procedure resolution
  → guarded canonicalisation
  → population manifest / Dataset Explorer
```

On the currently validated Cosenza pair the semantic layer contains:

- 2,661 entity observations;
- 3,258 identifier observations;
- 2,663 establishment observations;
- 2,661 White List relationship observations;
- 3,226 procedure observations;
- 8,710 requested procedure-sector observations;
- 600 explicit projection QA/review issues.

The 600 review items are data, not silent parser failures:

- 569 parenthesized application-date observations;
- 2 unexpected identifier shapes;
- 29 cases where a published listing date predates a later/current application date and is therefore **not** promoted as that procedure's decision date.

## Current canonical population

The guarded resolver/canonicaliser currently materialises from those two Cosenza editions:

- 1,343 `core.legal_entity` rows;
- 2,655 accepted entity-mention resolutions;
- 6 entity observations deliberately left `requires_resolution`;
- 3,248 canonical identifier observations;
- 1,298 distinct source-supported address objects;
- 2,657 establishment observations on resolved entities;
- 1,343 `whitelist.white_list_relationship` rows;
- 2,655 relationship-state versions;
- 1,368 canonical procedure identities;
- 2,651 procedure versions;
- 3,614 requested `procedure_sector` links.

Three source identifier values are ambiguous across distinct source names. They remain available in `semantic.identifier_observation` but are quarantined from `core.entity_identifier`. A row can still be resolved through a second independent safe identifier without laundering the ambiguous value into the canonical layer.

`whitelist.relationship_sector` currently contains zero rows **by design**: the Cosenza combined source exposes activities requested in procedures, not independent evidence of sectors actually represented/listed on the White List relationship.

## Dataset Explorer: how to read empty tables

The Dataset Explorer now receives a `model_population` manifest generated directly from PostgreSQL after the pipeline completes. It does not hard-code whether a table is populated.

Each object has a real count and a status such as:

- `POPULATED`;
- `POPULATED_WITH_UNRESOLVED_EDGE_CASES`;
- `POPULATED_WITH_REVIEW_ITEMS`;
- `REQUIRES_RESOLUTION`;
- `REQUIRES_REVIEW`;
- `NOT_APPLICABLE_FROM_CURRENT_SOURCE`;
- `NOT_YET_PROCESSED`;
- `NOT_YET_POPULATED`.

Therefore a zero is interpretable. For example:

- `relationship_sector = 0` → `NOT_APPLICABLE_FROM_CURRENT_SOURCE` for this Cosenza publication model;
- `derived_event = 0` → `NOT_YET_PROCESSED`, because derived longitudinal events are intentionally run only after canonical history exists.

## Useful database query surfaces

For the raw/source parser-v2 layer:

```sql
SELECT *
FROM mart.cosenza_source_observations_v2
ORDER BY edition_code, record_locator
LIMIT 50;
```

For the canonical current-state layer, use the canonical marts such as `mart.current_whitelist` once the relevant semantic/canonical population has been reconstructed.

The Dataset Explorer is the preferred curator-facing surface because it shows the source rows together with the actual population/status of the full model.

## Local reconstruction

Start PostgreSQL 18 and install database dependencies:

```bash
cp .env.example .env
make db-up
make db-apply
make db-test
python -m pip install -e '.[database]'
```

After capture and parser-v2 persistence, the semantic/canonical stages are run with:

```bash
white-list-semantic-pipeline \
  --dsn "$DATABASE_URL" \
  --series-code cosenza-combined
```

Actual model population can then be exported with:

```bash
white-list-model-population \
  --dsn "$DATABASE_URL" \
  --output model_population.json
```

The live GitHub workflow performs both steps automatically, runs them a second time to prove idempotence, and only then builds the private Dataset Explorer.

## What does not exist yet

There is still no durable hosted PostgreSQL instance or final public row-level White List browser. The current database is reproducibly reconstructed in the workflow and the Explorer artifact is private/ephemeral.

The intended stable model remains:

1. **Data/source/parser catalog** — inventory, coverage, parser family and semantic-profile status.
2. **Durable database/API** — complete provenance-aware source, semantic and canonical archive.
3. **Reviewed browser/releases** — searchable UI plus versioned CSV/Parquet/JSON after quality and dissemination review.

## Interpretation warning

Do not infer administrative removal from disappearance between editions. Do not equate nominal expiry with loss of legal effect. Do not treat a source listing date as the decision date of a later application when chronology contradicts that interpretation. Requested sectors remain procedure semantics unless the source independently proves a relationship/listed-sector association.
