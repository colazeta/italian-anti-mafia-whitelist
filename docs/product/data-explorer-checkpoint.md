# Data Explorer checkpoint — Cosenza pilot

## Purpose

Before scaling parsing across all territorial authorities, the project exposes the current validated stage as an **internal review product**. The aim is to let a curator inspect whether the data model, parser output, temporal comparison and provenance presentation are correct enough to replicate nationally.

This is deliberately a checkpoint, not a final public portal.

## Why the checkpoint mattered

The first Explorer immediately revealed that parser v1 was too poor: important source columns such as registered office, activities, application dates, listing date and nominal expiry were not structured. A deeper row-level audit then found that v1 also missed three real rows and produced one false positive per snapshot because row detection depended on an 11-digit numeric identifier.

This is exactly the kind of defect the checkpoint is intended to discover before national scale-out.

Parser v1 remains preserved as historical provenance. The current checkpoint uses **parser v2**, a lossless-first PDF-coordinate parser documented in [`../architecture/cosenza-parser-v2.md`](../architecture/cosenza-parser-v2.md).

## Current scope

The Explorer combines:

- the 106-authority national coverage registry;
- current verified-primary-page and source-series counts;
- the Cosenza historical-edition inventory;
- the frozen 28 June 2026 and 3 August 2026 Cosenza source captures;
- **1,327 + 1,334 = 2,661 parser-v2 source observations**;
- all seven source columns for each observation;
- observed listing dates and nominal expiry dates parsed from source `Esito` wording;
- aggregate snapshot differences;
- parser/content provenance and v1→v2 QA correction.

## User-facing sections

1. **Overview** — project-stage metrics and explicit v1→v2 parser QA correction.
2. **Osservazioni ricche** — searchable/filterable table exposing business name, registered office, source identifiers, requested activities, application dates, observed listing date, observed nominal expiry, source outcome and snapshot comparison.
3. **Confronto** — added/disappeared/common observations, changed records, source-status changes and field-coverage metrics.
4. **Copertura nazionale** — authority coverage and verified-source/source-series state.
5. **Provenance** — parser revision/configuration and frozen source byte identities.
6. **Metodo** — the lossless-first source-observation contract and separation from canonical facts.

The row detail drawer retains full raw source evidence and parsed multi-valued identifiers/dates so extraction can be inspected against the original row.

## Data classification

The versioned Explorer template is committed to Git. The real 2,661-row payload is **not** committed.

The private Cosenza workflow builds a self-contained v2 `index.html` only after:

1. official PDF byte/text identities match the frozen captures;
2. v1 is reproduced as the historical QA baseline;
3. v2 parsing completes;
4. v2 rows are persisted to PostgreSQL;
5. database checks prove 2,661 rows, 18,627 source field values, seven source fields, recovered false negatives and absence of the known v1 false positive.

The resulting artifact is named `data-explorer-preview-v2`. It is an internal review surface, not a release dataset.

## Review questions before national scale-out

The curator should specifically assess:

- whether all useful source columns now appear in the main table;
- whether listing/expiry dates are labelled clearly as source observations rather than canonical dates;
- whether multi-valued and malformed source identifiers are represented honestly;
- whether raw source evidence makes parser QA practical;
- whether the snapshot diff avoids implying that disappearance equals administrative removal;
- whether the Prefecture/source-edition navigation is the right product hierarchy;
- whether provenance and parser-version differences are sufficiently visible;
- whether any remaining source information is still trapped only inside raw text rather than structured explicitly.

Material feedback from this checkpoint should be resolved before large-scale parser implementation across additional Prefectures.
