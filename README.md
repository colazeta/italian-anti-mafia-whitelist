# Open Italian Anti-Mafia White List Archive

A national, standardised, longitudinal and provenance-aware data infrastructure for the Italian Prefectures' anti-mafia White Lists.

## Current status

This repository is a **pre-alpha implementation baseline**. It contains:

- the audited and corrected **ERD v0.2**;
- a PostgreSQL 18 bootstrap schema;
- versioned White List sector taxonomy support;
- source capture, content-addressed storage metadata and versioned parser runs;
- entity/procedure resolution and evidence provenance;
- tri-temporal canonical state (`effective`, `observation`, `system` time);
- explicit lineage from canonical versions to processing activities;
- seed vocabularies and the current post-2020 White List sector scheme;
- static repository tests and a PostgreSQL integration/constraint suite.

It does **not** yet contain a national scrape or production data. The PostgreSQL integration suite still requires execution against a live PostgreSQL 18 server before the database schema is tagged as a release.

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

## Repository layout

```text
db/                    PostgreSQL schema, seeds and integrity tests
docs/                  architecture and canonical data dictionary
src/white_list_archive future acquisition/normalisation pipeline
tests/                 repository-level static tests
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

Static tests currently verify repository structure and the audited SQL design invariants. The database integration suite additionally tests:

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

## Next implementation steps

1. Execute and pass the full suite on a live PostgreSQL 18 instance.
2. Backfill the historical sector schemes before 7 June 2020.
3. Build the national source registry for every Prefecture/competent authority.
4. Implement acquisition and content-addressed archiving.
5. Implement parsers per source schema version.
6. Introduce durable migration tooling before persistent production deployment.
7. Publish canonical current-state and history marts only after reuse/privacy review.
