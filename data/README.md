# Data directory

This directory contains **persistent, repository-tracked data artifacts**. It is not the complete internal archive and it is not a dumping ground for raw files.

Start with [`catalog.csv`](catalog.csv), which inventories every persistent CSV/JSON artifact in this directory and states its layer, scope, status and release class.

## Layers

### `source_registry/`

Research data about where White List information is published and how territorial sources are structured. These files describe authorities, verified source pages, recurring source series, source profiles and identified historical editions. They are not company-level White List observations.

### `captures/`

Immutable metadata about real source acquisitions plus safe aggregate diagnostics. Capture manifests include provenance and byte identity; raw PDFs and row-level working extracts are intentionally not committed to Git.

### `releases/`

Reserved for reviewed, versioned data products intentionally prepared for reuse. See [`releases/README.md`](releases/README.md). There is currently no row-level White List release in this directory.

## Where the rest of the data live

The complete architecture separates repository-tracked metadata from:

- immutable raw bytes in content-addressed object storage;
- row-level parsed observations in PostgreSQL;
- canonical resolved White List facts/states in PostgreSQL;
- release-ready exports in `data/releases/`.

The current Cosenza pilot has persisted its source/capture graph in PostgreSQL, while row-level `ParsedRecord` / `SourceFieldValue` persistence is the next ingestion milestone.

For a practical guide, read [`../docs/data-access.md`](../docs/data-access.md).

## Rule

Every persistent `.csv` or `.json` committed anywhere below `data/` must appear in `catalog.csv` (except `catalog.csv` itself). CI enforces this rule.
