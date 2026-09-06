# Where to see the data

This page is the authoritative human-readable guide to the data currently available in the project.

## Short answer

Start with [`../data/catalog.csv`](../data/catalog.csv). It is the machine-readable inventory of every persistent data artifact/profile committed under `data/`.

At the current project stage there are five access layers:

1. [`../data/source_registry/`](../data/source_registry/) — national source-discovery and coverage data.
2. [`../data/captures/`](../data/captures/) — immutable capture manifests, parser-validation profiles and safe aggregate diagnostics.
3. **PostgreSQL marts** — row-level internal source observations and, later, canonical data.
4. **Data Explorer checkpoint** — a private self-contained browser generated from validated Cosenza data for curator review before national scale-out.
5. [`../data/releases/`](../data/releases/) — intentionally released data products. There is currently no row-level public White List release.

## What is directly visible in GitHub

### National source registry

The source registry currently includes:

- `territorial_authorities.csv` — 106 territorial authorities;
- `verified_primary_pages.csv` — 34 independently verified primary White List landing pages;
- `source_series_inventory.csv` — 28 qualified recurring source series;
- `pilot_source_profiles.csv` — observed source/schema heterogeneity;
- `cosenza_historical_editions.csv` — 11 dated Cosenza editions identified for longitudinal recovery.

These are source-discovery data, not company observations.

### Cosenza capture and parse profiles

`data/captures/cosenza/` contains the frozen source captures and two generations of parser evidence.

Parser v1 is retained as a historical QA baseline. Its validated profile has 1,325 + 1,332 = 2,657 observations, but the curator checkpoint demonstrated that v1 missed three real rows and emitted one false positive in each snapshot.

The current parser-v2 profile is:

`parsed_profile_v2_2026-06-28_2026-08-03.json`

It records the validated result:

- **1,327** source observations on 28 June 2026;
- **1,334** on 3 August 2026;
- **2,661** `ParsedRecord` / unresolved `EntityMention` objects in total;
- **18,627** `SourceFieldValue` objects;
- seven persisted source columns per row;
- 913 observed listing dates parsed from source `Esito` wording;
- 428 observed nominal-expiry dates parsed from source `Esito` wording;
- zero canonical entities created by parsing.

The profile also records the v1→v2 QA correction, parser/configuration revision, source hashes, ParseRun codes and workflow/artifact provenance. It does not contain the row-level names or identifiers themselves.

## What parser v2 structures

For each Cosenza row, v2 retains these source fields:

1. Ragione sociale
2. Sede legale
3. Sede secondaria
4. Codice fiscale / Partita IVA — including multiple, malformed or ambiguous published values
5. Attività per cui è richiesta l’iscrizione
6. Data/e di presentazione dell’istanza
7. Esito

V2 additionally parses source-level annotations from `Esito`, including observed listing date, observed nominal expiry, renewal-request and update-in-progress signals.

These are **source observations**. An observed listing date is not automatically the canonical administrative registration date; an observed expiry date is not automatically a legal loss-of-effect date.

## Where the actual row-level Cosenza observations are

Row-level observations are intentionally not committed as CSV/JSON under `data/` and are not a public release.

V2 persists them in PostgreSQL as:

`ContentObject → ParseRun → ParsedRecord → SourceFieldValue → EntityMention`.

The readable v2 view is:

```sql
SELECT *
FROM mart.cosenza_source_observations_v2
ORDER BY edition_code, record_locator
LIMIT 50;
```

It exposes the seven source columns, parsed identifier/date/outcome JSON, raw source row, content identity and parser provenance.

The old `mart.cosenza_source_mentions` view remains available only for parser-v1 provenance comparison.

## Internal Data Explorer checkpoint

Before parsing additional Prefectures at scale, the project builds a private Explorer from v2.

The current v2 Explorer shows:

- national coverage and source-series state;
- the explicit v1→v2 QA correction;
- all 2,661 Cosenza source observations;
- registered/secondary office;
- multi-valued source identifiers;
- requested activities;
- application dates;
- observed listing date;
- observed nominal expiry;
- full source outcome;
- source-level snapshot changes;
- raw row evidence and parser/content provenance.

The live workflow builds the internal HTML only after the official PDFs match their frozen byte/text identities, v2 is persisted to PostgreSQL and all v2 database QA checks pass. The artifact is called `data-explorer-preview-v2`.

See [`product/data-explorer-checkpoint.md`](product/data-explorer-checkpoint.md) and [`architecture/cosenza-parser-v2.md`](architecture/cosenza-parser-v2.md).

## Local database

Start PostgreSQL 18 and apply the schema:

```bash
cp .env.example .env
make db-up
make db-apply
make db-test
python -m pip install -e '.[database]'
```

The source/capture graph is loaded with `white-list-persist-capture-manifests`. Parser-v2 outputs are generated with `white-list-cosenza-v2` and persisted with `white-list-persist-parsed-records-v2`.

The live workflow re-downloads the two official historical PDFs and refuses to attach a new parse to a frozen `ContentObject` if URL, PDF SHA-256, text SHA-256, page count or structural fingerprint differ.

## What does not exist yet

There is not yet a durable hosted PostgreSQL instance or a final public row-level White List browser. The GitHub Action database and internal Explorer artifacts are reproducible but ephemeral/private.

The intended stable model remains:

1. **Data catalog** — inventory and coverage.
2. **Durable database/API** — complete provenance-aware internal archive.
3. **Reviewed browser/releases** — searchable UI plus versioned CSV/Parquet/JSON exports after quality and dissemination review.

## Interpretation warning

Do not infer an administrative registration/removal event solely from appearance or disappearance between source editions. Do not treat source `Esito`, observed listing date or observed expiry date as canonical legal-effect facts without the separate canonicalisation/evidence step.
