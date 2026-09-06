# Data Explorer checkpoint — Cosenza pilot

## Purpose

Before scaling parsing across all territorial authorities, the project exposes the current validated stage as an **internal review product**. The aim is to let a curator inspect whether the data model, parser output, temporal comparison and provenance presentation are correct enough to replicate nationally.

This is deliberately a checkpoint, not a final public portal.

## Current scope

The Explorer combines:

- the 106-authority national coverage registry;
- current verified-primary-page and source-series counts;
- the Cosenza historical-edition inventory;
- the frozen 28 June 2026 and 3 August 2026 Cosenza source captures;
- the 1,325 + 1,332 validated parser-v1 source observations;
- aggregate snapshot differences;
- parser and content provenance.

## User-facing sections

1. **Overview** — project-stage and coverage metrics.
2. **Copertura nazionale** — searchable authority coverage and verified-source status.
3. **Cosenza** — snapshot totals and parser-status diagnostics.
4. **Osservazioni sorgente** — searchable/filterable row table with a detail drawer showing raw source block, extracted source fields, hashes and comparison classification.
5. **Confronto snapshot** — added/disappeared/common observations, changed records and diagnostic source-status transitions.
6. **Provenance** — parser revision/configuration and frozen source byte identities.
7. **Metodo** — the evidence → observation → resolution → canonical fact → derived event separation.

## Data classification

The versioned Explorer template is committed to Git. The real 2,657-row payload is **not** committed.

The GitHub Actions workflow builds a self-contained `index.html` using the validated row-level outputs and uploads it as a private workflow artifact named `data-explorer-preview`. The artifact is an internal review surface and is not a release dataset.

A second, sanitized build mode masks source identifiers and omits raw row blocks. CI uses this mode to validate the UI builder without exposing row-level source content.

## Review questions before national scale-out

The curator should specifically assess:

- whether source observations are visually distinct enough from canonical facts;
- whether the raw row block makes parser QA practical;
- whether extracted source name / identifier are correctly aligned to the row;
- whether status labels are clearly diagnostic rather than legal determinations;
- whether the snapshot diff avoids implying that disappearance equals administrative removal;
- whether the Prefecture-first navigation is the right product entry point;
- whether provenance is sufficiently accessible to support audit and correction.

Material feedback from this checkpoint should be resolved before large-scale parser implementation across additional Prefectures.
