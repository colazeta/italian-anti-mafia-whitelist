# Open Italian Anti-Mafia White List Archive

A national, standardised, longitudinal and provenance-aware data infrastructure for the Italian Prefectures' anti-mafia White Lists.

## Current status

The validated database baseline is **schema 0.1.0**. The project is now in the national source-registry phase. It contains:

- the audited and corrected **ERD v0.2**;
- a PostgreSQL 18 schema validated in GitHub Actions;
- versioned White List sector taxonomy support;
- source capture, content-addressed storage metadata and versioned parser runs;
- entity/procedure resolution and evidence provenance;
- tri-temporal canonical state (`effective`, `observation`, `system` time);
- explicit lineage from canonical versions to processing activities;
- seed vocabularies and the current post-2020 White List sector scheme;
- a 106-authority national territorial coverage registry;
- verified White List landing pages and heterogeneous pilot source profiles;
- an official national-index discovery parser and manual GitHub workflow;
- static repository tests and a PostgreSQL integration/constraint suite.

It does **not** yet contain a complete national scrape or production company data. Source coverage, historical source recovery and parser implementation are being built incrementally and must remain evidence-backed.

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

## Repository layout

```text
db/                    PostgreSQL schema, seeds and integrity tests
docs/                  architecture, source methodology and data dictionary
src/white_list_archive acquisition/normalisation implementation
tests/                 static and source-registry tests
data/source_registry/  territorial coverage and verified source research data
data/                   intentionally excludes raw production data
```

## Local database

Requires Docker with Compose:

```bash
cp .env.example .env
make db-up
make db-apply
make db-test
```

The compose file uses PostgreSQL 18. Complex tri-temporal integrity is enforced with GiST exclusion constraints; taxonomy and cross-table semantic consistency are enforced through relational constraints and targeted validation triggers.

## Validation status

The schema and seed set have been executed successfully against PostgreSQL 18 in GitHub Actions. The database integration suite tests:

- true unbounded range semantics;
- tri-temporal overlap rejection;
- historical system-time corrections;
- unknown-effective-period conflicts;
- taxonomy-version overlap;
- taxonomy membership containment;
- sector/scheme consistency;
- parser-version coexistence;
- field/schema consistency;
- raw-value/content identity immutability;
- entity/procedure resolution uniqueness over system time;
- current marts;
- derived-event input lineage.

The source-registry suite additionally checks the territorial coverage baseline, special authority types, verified-source referential integrity, pilot-source diversity and national-index parsing.

## National source discovery

The Ministry national White List index can be parsed with:

```bash
python -m pip install -e .
white-list-national-index --output national-white-list-index.csv
```

A manual GitHub Actions workflow, **Discover national White List index**, runs the same discovery and preserves the CSV as a workflow artifact. The index is a discovery/provenance source; canonical company observations must be traced to the territorial source content.

## Next implementation steps

1. Resolve and independently verify the primary White List landing page for all 106 territorial authority entries.
2. Enumerate every distinct source series exposed by each authority (listed companies, applicants, sectors, special registers and historical series).
3. Backfill historical sector schemes before 7 June 2020.
4. Recover historical source editions and fingerprint source-schema families.
5. Implement acquisition and content-addressed archiving for verified source series.
6. Implement parsers by source-schema family, beginning with the audited pilot models.
7. Introduce durable migration tooling before persistent production deployment.
8. Publish canonical current-state and history marts only after reuse/privacy review.
