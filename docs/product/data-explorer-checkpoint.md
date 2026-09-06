# Dataset Explorer checkpoint — Cosenza end-to-end pilot

## Purpose

Before scaling ingestion across all territorial authorities, the project exposes the current stage as an **internal review product**. The checkpoint is meant to let the curator inspect not only parser output, but the whole data model actually populated by the pipeline.

This is deliberately a checkpoint, not a final public portal.

## What the checkpoint has already corrected

The first Explorer showed that parser v1 was too poor: useful columns were trapped in raw text, and row detection depended on an 11-digit identifier. Parser v2 corrected those defects.

The next Explorer review then exposed a second architectural problem: parsing populated only the source-observation layer, while many ontology/canonical tables remained empty even though the source contained enough information to populate them safely.

The current checkpoint therefore validates the full path:

```text
source → parser family → record contract → semantic projection → resolution → canonical model → Explorer
```

The parser-family/semantic architecture is documented in [`../architecture/parser-families-and-semantic-pipeline.md`](../architecture/parser-families-and-semantic-pipeline.md).

## Current scope

The Explorer combines:

- the 106-authority national coverage registry;
- parser-family, source-binding and semantic-profile routing;
- the frozen 28 June 2026 and 3 August 2026 Cosenza captures;
- 2,661 parser-v2 source observations;
- the complete typed semantic projection;
- guarded entity/procedure resolution;
- canonical entities, White List relationships, relationship states and procedures;
- explicit unresolved/review items;
- real PostgreSQL table counts and population statuses;
- source/parser/semantic/resolver provenance.

## Current validated database population

The end-to-end live workflow currently yields:

### Source/parser layer

- 2,661 current parser-v2 observations;
- 18,627 v2 source-field values;
- seven source columns per row;
- legacy parser-v1 runs retained for reproducibility.

### Semantic layer

- 2,661 entity observations;
- 3,258 identifier observations;
- 2,663 establishment observations;
- 2,661 relationship observations;
- 3,226 procedure observations;
- 8,710 requested procedure-sector observations;
- 600 explicit QA/review issues.

### Resolution/canonical layer

- 1,343 canonical `LegalEntity` rows;
- 2,655 accepted entity resolutions;
- 6 deliberately unresolved entity observations;
- 3,248 ambiguity-safe canonical identifier observations;
- 1,298 address objects;
- 2,657 establishments;
- 1,343 White List relationships;
- 2,655 relationship-state versions;
- 1,368 canonical procedures;
- 2,651 procedure versions;
- 3,614 requested procedure-sector links.

The current source does not independently prove listed relationship sectors, so `whitelist.relationship_sector` correctly remains `0 / NOT_APPLICABLE_FROM_CURRENT_SOURCE` rather than being filled from requested activities.

## User-facing sections

The product uses the deliberately minimal, dense management-system visual language defined in `docs/product/ui-style.md`.

1. **Struttura dataset** — the full model as actually reconstructed in PostgreSQL, with table name, row count, layer, status and reason for zero/unresolved states.
2. **Dati Cosenza** — dense searchable source-observation table with all parser-v2 fields.
3. **Confronto snapshot** — observational comparison between editions with strict removal/registration guardrails.
4. **Copertura nazionale** — authority and source-series discovery coverage.
5. **Pipeline / provenance** — selected parser family, schema fingerprint, record contract, semantic projector, field mappings and canonicalisation result.
6. **Metodo** — source → semantic → canonical separation and parser-family strategy.

## Why “empty” now has a meaning

The Explorer no longer hard-codes whether a model object is populated. The live workflow generates a `model_population` manifest directly from PostgreSQL.

Every object receives a status such as:

- `POPULATED`;
- `POPULATED_WITH_UNRESOLVED_EDGE_CASES`;
- `POPULATED_WITH_REVIEW_ITEMS`;
- `REQUIRES_RESOLUTION`;
- `REQUIRES_REVIEW`;
- `NOT_APPLICABLE_FROM_CURRENT_SOURCE`;
- `NOT_YET_PROCESSED`;
- `NOT_YET_POPULATED`.

This prevents a zero-row table from being presented as though the project simply forgot to populate it.

## Data classification

The versioned Explorer template is committed to Git. Row-level source, semantic and canonical data are not committed as a public release.

The private workflow builds the self-contained `data-explorer-preview-v2` artifact only after:

1. frozen official source identity checks;
2. parser-v2 persistence;
3. parser-family/record-contract selection;
4. semantic projection;
5. guarded canonicalisation;
6. chronology/ambiguity/sector semantic assertions;
7. a second pipeline run proving idempotence;
8. database population export.

## Review questions before national scale-out

The curator should now assess:

- whether the complete dataset structure is understandable without reading SQL;
- whether source, semantic, resolution and canonical layers are visually distinct enough;
- whether the reason attached to every empty/unresolved object is useful;
- whether canonical entity/relationship/procedure concepts match the intended ontology;
- whether the parser-family → record-contract → semantic-projector routing is visible enough for audit;
- whether any Cosenza fact is still mapped to the wrong semantic object;
- whether the automatic resolver is appropriately conservative;
- whether additional ontology concepts are needed before expanding to another source family.

Large-scale parser rollout should follow this reviewed architecture rather than the earlier source-only ingestion path.
