# Open Italian Anti-Mafia White List Archive

A national, standardised, longitudinal and provenance-aware data infrastructure for the Italian Prefectures' anti-mafia White Lists.

## Start here

- **Want to see the data?** Read [`docs/data-access.md`](docs/data-access.md) and open [`data/catalog.csv`](data/catalog.csv).
- **Want to review the current product checkpoint?** See [`docs/product/data-explorer-checkpoint.md`](docs/product/data-explorer-checkpoint.md); the private live workflow builds the row-level Data Explorer v2 artifact.
- **Want to understand the current parser QA?** See [`docs/architecture/cosenza-parser-v2.md`](docs/architecture/cosenza-parser-v2.md).
- **Want to understand the project rules?** Read [`docs/project-rules.md`](docs/project-rules.md).
- **Want the documentation map?** Start from [`docs/README.md`](docs/README.md).
- **Want to understand the database?** See [`docs/architecture/`](docs/architecture/).
- **Want to contribute?** See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Current status

The last frozen database baseline is **schema 0.1.0**. The live development line is **0.1.1.dev0**, which adds operational metadata required by real source captures and versioned row-level parsing without silently redefining the frozen 0.1.0 semantics.

The project currently contains:

- the audited and corrected ERD and architecture documentation;
- a PostgreSQL 18 schema validated in GitHub Actions;
- versioned White List sector taxonomy support;
- source capture, content-addressed storage metadata and versioned parser infrastructure;
- entity/procedure resolution and evidence provenance;
- tri-temporal canonical state (`effective`, `observation`, `system` time);
- explicit lineage from canonical versions to processing activities;
- seed vocabularies and the current post-2020 White List sector scheme;
- a **106-authority** national territorial coverage registry;
- **34 verified primary pages** and **28 qualified source series** in the current source-registry baseline;
- an official national-index discovery parser and manual GitHub workflow;
- a real Cosenza content-capture pilot for the **28 June 2026** and **3 August 2026** editions;
- frozen Cosenza capture manifests with HTTP provenance, SHA-256 and structural fingerprints;
- a versioned parser history: v1 retained as a documented QA baseline and **v2 as the current lossless-first Cosenza parser**;
- **1,327 + 1,334 = 2,661** validated v2 source observations;
- seven persisted Cosenza source columns per observation: business name, registered office, secondary office, source identifiers, requested activities, application dates and outcome;
- observed listing dates and nominal expiry dates parsed from source `Esito` wording while remaining non-canonical observations;
- **18,627** v2 `SourceFieldValue` objects and zero canonical entities created by parsing;
- a readable `mart.cosenza_source_observations_v2` source-observation view;
- a versioned **Data Explorer v2 checkpoint UI** populated only after frozen-source identity checks and PostgreSQL QA pass;
- static repository-governance tests and PostgreSQL integration/constraint tests.

The project does **not** yet contain a complete national scrape or a public row-level company dataset. Row-level source observations belong to the internal database/archive until a reviewed release profile is approved; parsing does not itself establish canonical companies or administrative states.

## Where the data are

The repository intentionally distinguishes discovery data, capture metadata, internal database state and release-ready data.

```text
data/catalog.csv             inventory of persistent repository data and parser profiles
data/source_registry/        national source discovery and coverage research
data/captures/               immutable capture manifests + parser-validation profiles
PostgreSQL marts             row-level internal observations / later canonical data
Explorer workflow artifact  private curator checkpoint over validated row-level data
data/releases/               reviewed release products (no row-level release yet)
```

Raw source bytes are not committed to Git. Row-level parsed observations and canonical facts belong in the database/internal archive. A dataset appears in `data/releases/` only after explicit quality, provenance and dissemination review.

See [`docs/data-access.md`](docs/data-access.md) for the exact current contents and how to inspect them.

## Core invariants

1. A source field value is append-only and is never overwritten.
2. A new parser version never overwrites an earlier parse.
3. Absence from a published list is not an administrative removal.
4. Nominal expiry does not automatically imply loss of legal effect.
5. A section notation such as `I` or `X` has meaning only inside a specific scheme version.
6. Requested sectors belong to a procedure; listed sectors belong to the White List relationship.
7. Canonical facts can be supported by multiple source items.
8. Corrections to the canonical layer preserve prior system-time versions.
9. Open temporal intervals use true unbounded PostgreSQL range bounds, not the timestamp value `infinity`.
10. A source field value cannot combine a parsed record and field definition from different source-schema versions.
11. A sector scheme membership must match both the canonical sector and the White List regime of the relationship/register in which it is used.
12. The internal archive and public release layer are distinct and publication policy is profile-specific.
13. Territorial White List URLs are discovered or verified; they are never guessed from URL conventions.
14. Authority coverage, source-series discovery and company observations are separate layers.
15. Persistent repository data must be represented in the machine-readable data catalog.
16. A parsed source record is immutable and does not by itself establish canonical entity identity or White List legal effect.
17. Product surfaces must visually distinguish source observations from canonical facts and release status.
18. A parser is not production-ready merely because it identifies most rows: it must inventory and preserve the observable source schema, cardinality and representative edge cases before scale-out.

## Repository layout

```text
README.md                   project entry point
CONTRIBUTING.md             contribution workflow

docs/                       documentation index, rules, architecture, product, sources and dictionary
data/                       catalogued persistent research/capture/release artifacts
db/                         PostgreSQL schema, seeds and integrity tests
explorer/                   versioned checkpoint Data Explorer templates
src/white_list_archive/     acquisition, parsing, persistence, publishing and normalisation code
tests/                      code, parser, registry and repository-governance tests
.github/workflows/          CI and reproducible acquisition/product workflows
```

## Local database

Requires Docker with Compose:

```bash
cp .env.example .env
make db-up
make db-apply
make db-test
```

The compose file uses PostgreSQL 18. Complex temporal integrity is enforced with GiST exclusion constraints; taxonomy and cross-table semantic consistency are enforced through relational constraints and targeted validation triggers.

## Inspect Cosenza source observations

After loading the frozen capture graph and parser-v2 outputs, inspect the current source-observation mart with:

```sql
SELECT *
FROM mart.cosenza_source_observations_v2
ORDER BY edition_code, record_locator
LIMIT 50;
```

The legacy `mart.cosenza_source_mentions` view is retained only for parser-v1 provenance comparison.

## Validation status

GitHub Actions validates both the repository and PostgreSQL 18 model. The suite covers, among other things:

- temporal overlap and historical correction rules;
- taxonomy-version and sector-membership consistency;
- parser/schema consistency and source-value immutability;
- entity/procedure resolution uniqueness;
- content identity and capture provenance;
- idempotent Cosenza source/capture persistence;
- versioned v1/v2 ParseRun persistence;
- v2 row coverage and rich source-field persistence;
- known v1 false-negative/false-positive regression cases;
- zero implicit canonical entities created by parsing;
- Data Explorer generation;
- data-catalog and documentation governance.

The dedicated live Cosenza workflow re-downloads the two frozen official PDFs and refuses parsing/persistence unless source identities still match. It reproduces v1 as a historical QA baseline, runs/persists v2, validates v2 counts and edge cases in PostgreSQL, and only then generates the private full-row Data Explorer v2 artifact.

## Next implementation steps

1. Review the richer Cosenza Data Explorer v2 checkpoint and resolve material UI/parser/model feedback before national parser scale-out.
2. Apply the validated v2 Cosenza schema family across the identified historical editions and construct the first longitudinal observation history.
3. Continue resolving and verifying the remaining national source pages and source series.
4. Add durable content-addressed raw-byte storage and promote `ContentObject.storage_status` from `ephemeral` to `durable` only when real storage exists.
5. Backfill historical sector schemes before 7 June 2020.
6. Add source-schema families/parsers for additional Prefectures using the v2 lossless-first quality rule.
7. Build reviewed current-state/history marts and a stable hosted data-browser/API layer.
8. Publish versioned release products only after reuse/privacy review.
