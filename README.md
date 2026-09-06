# Open Italian Anti-Mafia White List Archive

A national, standardised, longitudinal and provenance-aware data infrastructure for the Italian Prefectures' anti-mafia White Lists.

## Start here

- **Want to see the data?** Read [`docs/data-access.md`](docs/data-access.md) and open [`data/catalog.csv`](data/catalog.csv).
- **Want to understand the project rules?** Read [`docs/project-rules.md`](docs/project-rules.md).
- **Want the documentation map?** Start from [`docs/README.md`](docs/README.md).
- **Want to understand the database?** See [`docs/architecture/`](docs/architecture/).
- **Want to contribute?** See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Current status

The last frozen database baseline is **schema 0.1.0**. The live development line is **0.1.1.dev0**, which adds operational metadata required by the first real source captures without silently redefining the frozen 0.1.0 semantics.

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
- a validated aggregate observational diff between those two editions;
- an idempotent PostgreSQL importer that persists the Cosenza source graph;
- static repository governance tests and PostgreSQL integration/constraint tests.

The project does **not** yet contain a complete national scrape or a public row-level company dataset. Row-level Cosenza parser output exists in the ingestion workflow but has not yet been promoted to durable `ParsedRecord` / `SourceFieldValue` persistence or a reviewed release product.

## Where the data are

The repository intentionally distinguishes discovery data, capture metadata, internal database state and release-ready data.

```text
data/catalog.csv             inventory of persistent repository data
data/source_registry/        national source discovery and coverage research
data/captures/               immutable capture manifests + aggregate diagnostics
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

## Repository layout

```text
README.md                   project entry point
CONTRIBUTING.md             contribution workflow

docs/                       documentation index, rules, architecture, sources and dictionary
data/                       catalogued persistent research/capture/release artifacts
db/                         PostgreSQL schema, seeds and integrity tests
src/white_list_archive/     acquisition, parsing, persistence and normalisation code
tests/                      code, registry and repository-governance tests
.github/workflows/          CI and reproducible acquisition workflows
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

## Inspect the Cosenza capture graph locally

```bash
python -m pip install -e '.[database]'
white-list-persist-capture-manifests \
  --dsn "$DATABASE_URL" \
  data/captures/cosenza/combined_2026-06-28.json \
  data/captures/cosenza/combined_2026-08-03.json
```

The importer is idempotent: importing the same frozen manifests repeatedly must not duplicate the logical source graph.

## Validation status

GitHub Actions validates both the repository and PostgreSQL 18 model. The suite covers, among other things:

- temporal overlap and historical correction rules;
- taxonomy-version and sector-membership consistency;
- parser/schema consistency and source-value immutability;
- entity/procedure resolution uniqueness;
- content identity and capture provenance;
- idempotent Cosenza manifest persistence;
- data-catalog and documentation governance.

## Next implementation steps

1. Persist Cosenza row-level `ParsedRecord`, `SourceFieldValue` and `EntityMention` objects with a genuine `ParseRun`.
2. Apply the validated Cosenza schema family across the identified historical editions and construct the first longitudinal observation history.
3. Continue resolving and verifying the remaining national source pages and source series.
4. Add durable content-addressed raw-byte storage and promote `ContentObject.storage_status` from `ephemeral` to `durable` only when real storage exists.
5. Backfill historical sector schemes before 7 June 2020.
6. Add source-schema families/parsers for additional Prefectures.
7. Build reviewed current-state/history marts and a stable data-browser/export layer.
8. Publish versioned release products only after reuse/privacy review.
