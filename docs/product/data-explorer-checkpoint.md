# Dataset Explorer checkpoint — Cosenza end-to-end pilot

## Purpose

Before scaling ingestion across all territorial authorities, the project exposes the current stage as an **internal review product**. The checkpoint is meant to let the curator inspect not only parser output, but the whole data model actually populated by the pipeline and the source evidence from which it was reconstructed.

This is deliberately a checkpoint, not a final public portal.

## What the checkpoint has already corrected

The first Explorer showed that parser v1 was too poor: useful columns were trapped in raw text, and row detection depended on an 11-digit identifier. Parser v2 corrected those defects.

The next Explorer review exposed a second architectural problem: parsing populated only the source-observation layer, while many ontology/canonical tables remained empty even though the source contained enough information to populate them safely.

A third review exposed two usability/audit gaps: **Struttura dataset** reported table counts without letting the curator inspect the underlying rows, and the original PDFs were not directly attached to the row-level verification experience.

The address-normalisation validation work exposed a fourth product requirement: aggregate geocoding/normalisation metrics must be visible without conflating **operational state** with **empirical precision estimates**. The Explorer therefore now reconciles the full address population, provider/version provenance and candidate/accepted/not-found/error accounting against the underlying validation rows, while displaying the frozen reviewed gold standard as a separate evidence layer.

The current checkpoint therefore validates the full path:

```text
source bytes → parser family → record contract → semantic projection → resolution → canonical model → Explorer → independent source verification
```

The parser-family/semantic architecture is documented in [`../architecture/parser-families-and-semantic-pipeline.md`](../architecture/parser-families-and-semantic-pipeline.md). Original-source retention and verification are documented in [`../architecture/source-evidence-archive.md`](../architecture/source-evidence-archive.md).

## Current scope

The Explorer combines:

- the 106-authority national coverage registry;
- parser-family, source-binding and semantic-profile routing;
- the frozen 28 June 2026 and 3 August 2026 Cosenza captures;
- the exact original PDFs used by parser v2, verified by SHA-256;
- row-ordinal → original-PDF-page evidence locators for all 2,661 source observations;
- 2,661 parser-v2 source observations;
- the complete typed semantic projection;
- guarded entity/procedure resolution;
- canonical entities, White List relationships, relationship states and procedures;
- explicit unresolved/review items;
- real PostgreSQL table counts and population statuses;
- browsable previews and complete internal CSV exports for every object shown in **Struttura dataset**;
- source/parser/semantic/resolver provenance;
- source-backed address-normalisation operational metrics, full-row drill-down and the frozen substantive-review quality evidence.

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

### Address-normalisation quality baseline

The current Cosenza ANNCSU validation baseline is kept in two deliberately separate layers:

1. **operational run accounting** — generated from the reconstructed database plus full `address_results.csv`, including canonical population, attempted/accounted addresses, candidate/accepted/not-found/error/unprocessed counts, coordinate-bearing versus normalisation-only results, precision-code counts and provider/version provenance;
2. **frozen substantive-review evidence** — the versioned 7 September 2026 gold standard, reporting candidate coverage **48.07%**, population-weighted candidate precision **82.49%**, estimated validated end-to-end yield **39.65%**, `civic_access` **36/36 correct**, `street` **16/28 correct** and no-coordinate candidates **12/14 correct**.

The UI never treats those empirical precision estimates as permission to promote candidates. Production acceptance remains a separately displayed database/provider state.

## User-facing sections

The product uses the deliberately minimal, dense management-system visual language defined in `docs/product/ui-style.md`. The retro/1990s appearance remains intentional.

1. **Struttura dataset** — the full model as actually reconstructed in PostgreSQL, with table name, row count, layer, status and reason for zero/unresolved states. Every row is now clickable: the inspector shows the SQL schema, the first 50 real rows and a link to the complete internal CSV export for that object.
2. **Dati Cosenza** — dense searchable source-observation table with all parser-v2 fields. Opening a row also exposes **Verifica indipendente**, linking to the preserved original PDF at the reconstructed source page and showing the evidence SHA-256.
3. **Confronto snapshot** — observational comparison between editions with strict removal/registration guardrails.
4. **Copertura nazionale** — authority and source-series discovery coverage.
5. **Pipeline / provenance** — selected parser family, schema fingerprint, record contract, semantic projector, field mappings, canonicalisation result and an **Archivio evidenza — documenti originali** block for each captured edition.
6. **Validazione indirizzi** — deterministic substantive-review queue with provider output, source/PDF evidence links, manual decisions, weighted precision and export/import of the review state.
7. **Qualità indirizzi** — table-first operational quality view that reconciles the 1,298-address population against the full validation rows, exposes provider/version/run provenance, separates coordinate-bearing from normalisation-only candidates, shows production accepted state independently from the frozen empirical gold standard, and links to the complete address-results CSV plus the substantive-review queue.
8. **Metodo** — source → semantic → canonical separation, parser-family strategy and evidence-chain rules.

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

This prevents a zero-row table from being presented as though the project simply forgot to populate it. The new table inspector also makes the positive case auditable: a non-zero count can now be opened and inspected rather than merely trusted.

## Original-source evidence package

The internal Explorer artifact now packages the exact official PDFs used by the live parser after frozen-content verification.

For each edition it exposes:

- preserved local PDF copy;
- original official resource URL;
- page count;
- SHA-256 identity;
- row → page locators derived from the same physical layout used by parser v2.

The workflow fails if the packaged PDF does not hash to the frozen capture identity or if the expected parser rows do not have page locators.

This makes row-level verification possible without depending on the Prefettura URL continuing to serve the same bytes later.

The current GitHub artifact has bounded retention and is therefore **not yet the final durable evidence archive**. Long-term production storage should use immutable/content-addressed object storage while retaining the same `ContentObject` identity and provenance chain.

## Data classification

The versioned Explorer template is committed to Git. Row-level source, semantic and canonical data are not committed as a public release.

The private workflow builds the `data-explorer-preview-v2` audit package only after:

1. frozen official source identity checks;
2. parser-v2 persistence;
3. parser-family/record-contract selection;
4. semantic projection;
5. guarded canonicalisation;
6. chronology/ambiguity/sector semantic assertions;
7. a second pipeline run proving idempotence;
8. database population export;
9. complete internal table exports for all model objects;
10. original-PDF packaging and row-to-page locator generation;
11. hash/coverage validation of the evidence package;
12. address-normalisation validation against the full reconstructed `core.address` population;
13. deterministic reconciliation of address quality metrics against `address_results.csv`;
14. embedding of the frozen reviewed gold-standard estimates without changing production acceptance state.

The resulting CSVs and PDFs are internal audit materials. They are not automatically public release products.

## Review questions before national scale-out

The curator should now assess:

- whether the complete dataset structure is understandable without reading SQL;
- whether opening any **Struttura dataset** object makes its actual content sufficiently transparent;
- whether source, semantic, resolution and canonical layers are visually distinct enough;
- whether the reason attached to every empty/unresolved object is useful;
- whether row → original PDF page is sufficient for independent parser QA or whether some parser families should later expose bounding boxes/table-cell locators;
- whether canonical entity/relationship/procedure concepts match the intended ontology;
- whether the parser-family → record-contract → semantic-projector routing is visible enough for audit;
- whether any Cosenza fact is still mapped to the wrong semantic object;
- whether the automatic resolver is appropriately conservative;
- whether operational address-quality metrics reconcile transparently enough with the underlying rows;
- whether empirical precision evidence and production acceptance state remain unmistakably separate;
- whether additional ontology concepts are needed before expanding to another source family.

Large-scale parser rollout should follow this reviewed architecture rather than the earlier source-only ingestion path.