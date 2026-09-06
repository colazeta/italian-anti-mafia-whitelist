# Where to see the data

This page is the authoritative human-readable guide to the data currently available in the project.

## Short answer

Start with [`../data/catalog.csv`](../data/catalog.csv). It is the machine-readable inventory of every persistent CSV/JSON artifact committed under `data/`.

At the current project stage there are four useful access layers:

1. [`../data/source_registry/`](../data/source_registry/) — national source-discovery and coverage data.
2. [`../data/captures/`](../data/captures/) — immutable capture manifests and safe aggregate diagnostics from real source acquisitions.
3. **PostgreSQL marts** — row-level internal source observations and, later, canonical data.
4. [`../data/releases/`](../data/releases/) — intentionally released data products. This directory currently contains no row-level White List release.

## What is directly visible in GitHub

### National source registry

The source registry is directly viewable as CSV in GitHub and currently includes:

- `territorial_authorities.csv` — the national territorial-authority baseline (106 authorities);
- `verified_primary_pages.csv` — independently verified primary White List landing pages;
- `source_series_inventory.csv` — qualified recurring publication series;
- `pilot_source_profiles.csv` — source-structure/schema research for heterogeneous pilots;
- `cosenza_historical_editions.csv` — dated Cosenza editions identified for longitudinal recovery.

These are **source-discovery data**, not company observations.

### Cosenza capture pilot

`data/captures/cosenza/` currently contains:

- `combined_2026-06-28.json` — immutable metadata for the captured 28 June 2026 combined edition;
- `combined_2026-08-03.json` — immutable metadata for the captured 3 August 2026 combined edition;
- `diff_2026-06-28_2026-08-03.json` — aggregate observational comparison of the two editions.

The capture manifests expose provenance such as official resource URL, HTTP response metadata, UTC capture time, SHA-256, byte size, page count and structural schema fingerprint. The diff contains aggregate diagnostics only.

## Where the row-level Cosenza observations are

The parser extracts 1,325 source rows from the 28 June 2026 edition and 1,332 from the 3 August 2026 edition. Those row-level observations are intentionally **not committed as CSV/JSON under `data/` and are not a public release**.

The 0.1.1 development ingestion layer can persist them in PostgreSQL as:

`ParseRun -> ParsedRecord -> SourceFieldValue -> EntityMention`.

For parser v1, the persisted structured source fields are the source business name and source `Codice fiscale/Partita IVA` value; the full raw row block is also retained. Entity mentions remain unresolved and parsing does not create canonical companies.

A readable view is provided:

```sql
SELECT *
FROM mart.cosenza_source_mentions
ORDER BY edition_code, record_locator
LIMIT 50;
```

The view exposes edition, raw/normalised source name, source identifier, raw row text, record hash and parser/content provenance. It is a **source-observation view**, not the canonical White List dataset.

## How to inspect the database representation locally

Start a local PostgreSQL 18 database and apply the schema:

```bash
cp .env.example .env
make db-up
make db-apply
make db-test
python -m pip install -e '.[database]'
```

The frozen source/capture graph can be loaded with:

```bash
white-list-persist-capture-manifests \
  --dsn "$DATABASE_URL" \
  data/captures/cosenza/combined_2026-06-28.json \
  data/captures/cosenza/combined_2026-08-03.json
```

Row-level parsing requires the extracted parser outputs produced by the Cosenza capture workflow. `white-list-persist-parsed-records` then verifies the parser input hash against the frozen capture manifest before creating the ParseRun and source observations.

The live Cosenza workflow is designed to re-download the two official historical PDFs and first require exact agreement with their frozen URL, PDF SHA-256, text SHA-256, page count and structural fingerprint. If the official bytes have changed, the workflow refuses to attach the new parse to the old ContentObject.

## What is not yet a stable public data browser

There is not yet a hosted public row-level White List browser. GitHub is useful for the project catalog, source-registry CSVs, capture manifests and documentation, but it should not become the final user interface for the database.

The intended stable browsing model is:

1. **Data catalog** — inventory, coverage and release status of datasets.
2. **Database/API layer** — complete provenance-aware internal archive and query interface.
3. **Release/browser layer** — human-readable tables and downloadable CSV/Parquet/JSON products after dissemination review.

A future website/dashboard should consume reviewed release products or a read-only API. It should make source observations, canonical administrative interpretation and public-release status visually distinct.

## Release status

`data/releases/` is reserved for versioned release-ready outputs. There is currently no row-level company release there. Public availability in a Prefecture source does not, by itself, imply that every field should automatically be republished in bulk without reuse/privacy review.

## Interpretation warning

Do not infer an administrative registration/removal event solely from appearance or disappearance between source editions. Do not treat a parsed source `Esito` as a canonical legal-effect determination. Those distinctions are part of the project’s core modelling rules.
