# Where to see the data

This page is the authoritative human-readable guide to the data currently available in the project.

## Short answer

Start with [`../data/catalog.csv`](../data/catalog.csv) for persistent repository artifacts and the private **Dataset Explorer** for the actual reconstructed database population, source evidence and source-coverage controls.

The current layers are:

1. [`../data/source_registry/`](../data/source_registry/) — national source discovery plus parser/binding/semantic-profile registries.
2. [`../data/captures/`](../data/captures/) — immutable capture manifests and safe diagnostics.
3. **PostgreSQL `source.*`** — capture, parse runs, parsed records and raw source values.
4. **PostgreSQL `semantic.*`** — typed ontology-level observations and review items.
5. **PostgreSQL `core.*` / `whitelist.*`** — guarded canonical entities, relationships, procedures and states.
6. **PostgreSQL `geo.*`** — derived geocoding candidates/results and versioned geographic-unit assignments.
7. **PostgreSQL `mart.*`** — curator/statistical read surfaces, including `mart.address_geography`.
8. **Dataset Explorer audit package** — private browser with per-table CSVs and preserved original source documents.
9. [`../data/releases/`](../data/releases/) — deliberately reviewed public/reuse products. There is no row-level public White List release yet.

## National source and parser registry

`data/source_registry/` currently includes 106 territorial authorities, 34 independently verified primary White List pages, 28 qualified recurring source series, parser families, parser bindings, semantic profiles and 11 dated Cosenza editions identified for historical recovery.

### Mandatory two-population coverage

Source discovery now has a separate completeness invariant. For every verified authority/register scope the project requires two logical populations:

```text
listed
applicant
```

They may be physically separate or represented by one combined `listed_and_applicant` source.

The command:

```bash
white-list-source-population-coverage
```

builds a deterministic ledger with statuses such as:

- `COVERED_SEPARATE_SERIES`;
- `COVERED_COMBINED_SERIES`;
- `UNRESOLVED_REQUIRES_REVIEW`.

Missing discovery is never interpreted as “not published”. At the current 34 verified-page / 28 source-series baseline the ledger contains **35 register/discovery scopes**: **12 complete**, **23 unresolved/incomplete**. Bologna contributes a second scope because ordinary and post-sisma registers are treated separately.

The **Copertura nazionale** tab of the internal Explorer shows this matrix directly.

## Cosenza source/semantic/canonical population

The current parser-v2 profile records:

- 1,327 source observations on 28 June 2026;
- 1,334 on 3 August 2026;
- 2,661 v2 parsed observations;
- 18,627 v2 `SourceFieldValue` rows;
- 913 observed listing dates;
- 428 observed nominal expiry dates.

Automatic downstream processing currently materialises:

- 2,661 entity observations;
- 3,258 identifier observations;
- 2,663 establishment observations;
- 3,226 procedure observations;
- 8,710 requested procedure-sector observations;
- 600 explicit semantic QA/review issues;
- 1,343 `core.legal_entity` rows;
- 1,298 distinct source-supported address objects;
- 1,343 White List relationships;
- 1,368 canonical procedures;
- 3,614 requested `procedure_sector` links.

`whitelist.relationship_sector` is still zero by design because the current Cosenza combined source proves requested activities, not independently the sectors represented/listed on the relationship.

## Geography: what is modeled and what is actually populated

Geography is deliberately downstream from source/canonical address evidence. The project does **not** overwrite the source address with geocoder output.

The implemented model includes:

- `geo.geographic_unit` — versioned ISTAT administrative / NUTS reference units;
- `geo.address_geocode_result` — provider-specific candidates/results with latitude, longitude, precision, confidence and processing provenance;
- `geo.address_geographic_unit` — address assignments to municipality, province/metropolitan city/autonomous province, region and NUTS;
- `mart.address_geography` — wide statistical surface exposing source address, coordinates, geocoding metadata and versioned territorial classifications.

The intended fields include:

`latitude · longitude · precision · municipality code/name · province-level code/name/type · region code/name · NUTS1/2/3 code/name/version`

The preferred primary source for Italian civic coordinates is **ANNCSU**, with **ISTAT/SITUAS** for administrative units and versioned NUTS for European statistical geography. External geocoding is a labelled fallback.

**Current status:** the schema and relational integrity tests are implemented, but the 1,298 Cosenza canonical addresses have **not yet been bulk-geocoded/enriched**. The public ANNCSU massive-download page is available, but its current download endpoint rejects the automated GitHub runner. This blocker is tracked explicitly; the Explorer therefore shows geography objects as `NOT_YET_POPULATED` / `NOT_YET_PROCESSED`, not as completed data.

See [`architecture/geography-and-population-coverage.md`](architecture/geography-and-population-coverage.md).

## Dataset Explorer: inspecting actual tables

Every object in **Struttura dataset** can be opened in the internal audit build. The generic inspector shows:

- qualified PostgreSQL table name;
- actual row count;
- column names and SQL types;
- the first 50 deterministic rows;
- a complete internal CSV export.

This applies to source, semantic, canonical and geography objects, including zero-row objects with explicit reasons.

## Original source documents and independent verification

The Cosenza audit package contains the exact original PDFs used by parser v2. Before packaging, live bytes are verified against frozen SHA-256 identities.

For each edition the Explorer exposes:

- preserved PDF;
- SHA-256;
- page count;
- official resource URL;
- parser row → PDF-page locator.

Opening a Cosenza row provides **Verifica indipendente**, allowing a reviewer to compare parser output with the exact original document page.

See [`architecture/source-evidence-archive.md`](architecture/source-evidence-archive.md).

## Useful database/query surfaces

Raw Cosenza parser-v2 observations:

```sql
SELECT *
FROM mart.cosenza_source_observations_v2
ORDER BY edition_code, record_locator
LIMIT 50;
```

Statistical geography surface:

```sql
SELECT *
FROM mart.address_geography
LIMIT 50;
```

Current geography rows will be empty until the enrichment pipeline is run; that is an explicit state, not a hidden failure.

## Local reconstruction

```bash
cp .env.example .env
make db-up
make db-apply
make db-test
python -m pip install -e '.[database]'
```

Semantic/canonical ingestion:

```bash
white-list-semantic-pipeline \
  --dsn "$DATABASE_URL" \
  --series-code cosenza-combined
```

Source-population completeness:

```bash
white-list-source-population-coverage \
  --output-json source_population_coverage.json \
  --output-csv source_population_coverage.csv
```

Model population:

```bash
white-list-model-population \
  --dsn "$DATABASE_URL" \
  --output model_population.json
```

Internal table bundle:

```bash
white-list-table-bundle \
  --dsn "$DATABASE_URL" \
  --output-dir explorer-audit \
  --preview-limit 50
```

## What does not exist yet

There is still no durable hosted PostgreSQL instance, completed bulk geography enrichment, final public row-level browser or permanent source-document object store. The current database is reproducibly reconstructed in workflows and the audit Explorer remains private/retention-bound.

## Interpretation warning

Do not infer administrative removal from disappearance between editions. Do not equate nominal expiry with loss of legal effect. Do not convert requested sectors into listed relationship sectors without independent source evidence. Do not treat an unresolved listed/applicant source target as evidence that the population is not published. Do not present a centroid/locality geocode as an exact civic coordinate.
