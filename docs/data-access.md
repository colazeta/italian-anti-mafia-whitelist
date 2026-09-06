# Where to see the data

This page is the authoritative human-readable guide to the data currently available in the project.

## Short answer

Start with [`../data/catalog.csv`](../data/catalog.csv). It is the machine-readable inventory of every persistent CSV/JSON artifact committed under `data/`.

At the current project stage there are three useful places to look:

1. [`../data/source_registry/`](../data/source_registry/) — national source-discovery and coverage data.
2. [`../data/captures/`](../data/captures/) — immutable capture manifests and safe aggregate diagnostics from real source acquisitions.
3. [`../data/releases/`](../data/releases/) — intentionally released data products. This directory currently contains no row-level White List release.

## What is visible now

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

## What is not yet directly browseable in GitHub

The pilot parser extracted row-level source mentions from the two Cosenza PDFs (1,325 and 1,332 rows respectively), but those row-level working extracts are **not committed to Git and are not yet a stable data product**.

During the pilot they were generated inside GitHub Actions artifacts. That storage is operational/ephemeral and must not be presented as the durable archive or as the public dataset.

The PostgreSQL importer currently persists the source graph — authority, register, source series, editions, resources, content objects, captures and schema version — but row-level `ParsedRecord` / `SourceFieldValue` objects are the next ingestion milestone.

## How to inspect the database representation

For development, start a local PostgreSQL 18 database and apply the schema:

```bash
cp .env.example .env
make db-up
make db-apply
make db-test
```

Then install the database extra and load the frozen Cosenza capture manifests:

```bash
python -m pip install -e '.[database]'
white-list-persist-capture-manifests \
  --dsn "$DATABASE_URL" \
  data/captures/cosenza/combined_2026-06-28.json \
  data/captures/cosenza/combined_2026-08-03.json
```

This materialises the source/provenance graph in PostgreSQL. It does not yet materialise the 2,657 row-level source observations.

## Intended stable browsing model

The project will use three distinct interfaces rather than making the Git tree itself the final data browser:

1. **Data catalog** — inventory, coverage and release status of datasets.
2. **Database/API layer** — complete provenance-aware internal archive and query interface.
3. **Release/browser layer** — human-readable tables and downloadable CSV/Parquet/JSON products after dissemination review.

`data/releases/` is reserved for versioned release-ready outputs. A later website/dashboard can consume those release products or a read-only API without weakening the distinction between raw source evidence, canonical administrative interpretation and public dissemination.

## Interpretation warning

Do not infer an administrative registration/removal event solely from appearance or disappearance between source editions. Do not treat a parsed source `Esito` as a canonical legal-effect determination. Those distinctions are part of the project’s core modelling rules.
