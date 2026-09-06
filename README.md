# Open Italian Anti-Mafia White List Archive

A national, standardised, longitudinal and provenance-aware data infrastructure for the Italian Prefectures' anti-mafia White Lists.

## Start here

- **Want to see the data/model population?** Read [`docs/data-access.md`](docs/data-access.md) and open [`data/catalog.csv`](data/catalog.csv).
- **Want to understand parser families and the automatic ontology pipeline?** Read [`docs/architecture/parser-families-and-semantic-pipeline.md`](docs/architecture/parser-families-and-semantic-pipeline.md).
- **Want to review the current Dataset Explorer checkpoint?** See [`docs/product/data-explorer-checkpoint.md`](docs/product/data-explorer-checkpoint.md); the private live workflow builds the full checkpoint artifact from the reconstructed PostgreSQL database.
- **Want to understand the current Cosenza parser QA?** See [`docs/architecture/cosenza-parser-v2.md`](docs/architecture/cosenza-parser-v2.md).
- **Want to understand the project rules?** Read [`docs/project-rules.md`](docs/project-rules.md).
- **Want the documentation map?** Start from [`docs/README.md`](docs/README.md).
- **Want to understand the database?** See [`docs/architecture/`](docs/architecture/).
- **Want to contribute?** See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Current status

The last frozen database baseline is **schema 0.1.0**. The live development line is **0.1.1.dev0**. It now implements the complete ingestion boundary from immutable source capture through semantic projection and guarded canonicalisation, without silently redefining the frozen 0.1.0 semantics.

The current architecture is:

```text
SourceSeries / SourceEdition
        ↓
Capture / ContentObject
        ↓
ParserFamily
        ↓
RecordContract
        ↓
SemanticProjector
        ↓
Resolution / guarded canonicalisation
        ↓
Canonical White List model
        ↓
Derived history / marts / Dataset Explorer
```

The project currently contains:

- an audited PostgreSQL 18 schema and documented ERD;
- tri-temporal canonical state (`effective`, `observation`, `system` time);
- source capture, content-addressed identity, parser and provenance infrastructure;
- a **106-authority** territorial coverage registry;
- **34 verified primary pages** and **28 qualified source series** in the current discovery baseline;
- a data-driven **parser-family registry**, source-series bindings and semantic-profile registry;
- exact schema-fingerprint routing with no guessed fallback parser;
- versioned parser record contracts that decouple physical source extraction from ontology semantics;
- versioned source-field → canonical-field mappings;
- automatic semantic projection into typed entity, identifier, establishment, White List relationship, procedure and requested-sector observations;
- guarded, auditable entity/procedure resolution and canonicalisation;
- an actual database-population manifest used by the Dataset Explorer instead of hard-coded “populated/empty” labels;
- a minimal, table-first Dataset Explorer designed as an administrative/data-management interface rather than a dashboard.

### Validated Cosenza end-to-end pilot

The current live pilot uses the frozen official editions **28 June 2026** and **3 August 2026**.

Parser v2 produces:

- **1,327 + 1,334 = 2,661** source observations;
- **18,627** v2 `SourceFieldValue` objects;
- all seven observable source columns persisted;
- **3,258** typed identifier observations;
- **2,663** establishment observations;
- **3,226** procedure observations;
- **8,710** requested-sector observations, all mapped to the current versioned White List sector taxonomy.

The semantic projector records **600 explicit QA/review issues** rather than hiding uncertainty:

- 569 parenthesized application-date observations;
- 2 unexpected identifier-shape observations;
- 29 cases where a published listing date predates a later/current application date and therefore cannot be promoted as that procedure's decision date.

The guarded canonicaliser currently materialises:

- **1,343** canonical `LegalEntity` rows;
- **2,655** accepted source-mention → entity resolutions;
- **6** entity observations deliberately left `requires_resolution`;
- **3,248** canonical identifier observations (ambiguous identifier values are quarantined from the canonical identifier layer);
- **1,298** distinct source-supported address objects;
- **2,657** establishment observations attached to resolved entities;
- **1,343** `WhiteListRelationship` rows;
- **2,655** relationship-state versions;
- **1,368** canonical procedure identities;
- **2,651** procedure versions;
- **3,614** canonical requested procedure-sector links.

`whitelist.relationship_sector` intentionally remains empty for the current Cosenza combined source: the source publishes **requested activities**, which belong to procedures. It does not independently prove which sectors are represented/listed on the canonical relationship.

Parser v1 remains preserved as immutable historical QA provenance. Parsing by itself still does not establish canonical facts; the **automatic downstream semantic/resolution stages** do so only where explicit versioned rules permit it.

The project does **not** yet contain a complete national scrape or a public row-level company release.

## Parser-family strategy

The project does **not** create a parser for every URL. It also does not use one universal parser.

A parser implementation represents a reusable **source family**. `data/source_registry/parser_families.csv` declares its physical implementation, schema fingerprints, field namespace, record contract and semantic profile. `parser_bindings.csv` assigns source series to validated families.

Selection is deterministic:

1. explicit validated `SourceSeries → ParserFamily` binding;
2. otherwise one exact validated schema-fingerprint match;
3. multiple matches require an explicit binding;
4. no match produces a controlled failure and a new-family review.

Different physical parsers can emit the same record contract and reuse the same semantic projector. This is how the parser library can grow with Prefecture heterogeneity without coupling the ontology to individual websites.

## Where the data are

```text
data/catalog.csv             persistent data / parser / semantic registry inventory
data/source_registry/        source discovery + parser families + bindings + semantic profiles
data/captures/               immutable capture manifests + safe validation profiles
PostgreSQL source.*          captures, parser runs, raw/parsed source observations
PostgreSQL semantic.*        typed semantic observations, issues and resolution decisions
PostgreSQL core/whitelist    guarded canonical entities, relationships, procedures and history
PostgreSQL provenance.*      evidence and transformation/resolution lineage
Explorer workflow artifact  private curator view of actual reconstructed database population
data/releases/               reviewed release products (no row-level release yet)
```

Raw source bytes are not committed to Git. Row-level source, semantic and canonical data belong to the internal database/archive until a reviewed dissemination profile approves a release.

## Core invariants

1. A source field value is append-only and is never overwritten.
2. A new parser version never overwrites an earlier parse.
3. Absence from a published list is not an administrative removal.
4. Nominal expiry does not automatically imply loss of legal effect.
5. A section notation such as `I` or `X` has meaning only inside a specific scheme version.
6. Requested sectors belong to procedures; listed sectors belong to the White List relationship.
7. Canonical facts can be supported by multiple source items.
8. Corrections to the canonical layer preserve prior system-time versions.
9. Open temporal intervals use true unbounded PostgreSQL range bounds, not the timestamp value `infinity`.
10. A source field value cannot combine a parsed record and field definition from different source-schema versions.
11. The internal archive and public release layer are distinct and publication policy is profile-specific.
12. Territorial source URLs are discovered or verified; they are never guessed from conventions.
13. Physical parser selection is explicit/fingerprint-driven; unknown schemas never silently fall back to a guessed parser.
14. Physical parsers emit record contracts and do not write the canonical ontology directly.
15. Safely typed source facts automatically populate the semantic layer.
16. Ambiguous identity evidence remains first-class semantic data instead of blocking unrelated safe facts or forcing a merge.
17. An ambiguous identifier is never promoted to a canonical identifier merely because another identifier resolves the same row.
18. A listing date that predates a later application cannot become the decision date of that later procedure.
19. Persistent repository data must be represented in the machine-readable data catalog.
20. Product surfaces must distinguish source, semantic, canonical and release layers.

## Repository layout

```text
README.md                   project entry point
CONTRIBUTING.md             contribution workflow

docs/                       documentation, rules, architecture, product and sources
data/                       catalogued research/capture/registry/release artifacts
db/                         PostgreSQL schema, seeds and integrity tests
explorer/                   minimal Dataset Explorer templates
src/white_list_archive/
  acquisition/              source discovery/capture
  parsers/                  reusable physical parser families + registry
  persistence/              immutable source persistence
  semantic/                 record-contract projection + guarded canonicalisation
  resolution/               reusable resolution components
  publishing/               population manifests / Explorer builders
tests/                      code, parser, registry and governance tests
.github/workflows/          CI and end-to-end live ingestion workflows
```

## Validation status

GitHub Actions currently verifies both deterministic CI and live official-source ingestion. The Cosenza live workflow performs, in order:

1. frozen source identity verification;
2. v1 historical parser reproduction;
3. v2 parsing and row-level persistence;
4. parser-family / record-contract / semantic-profile routing;
5. versioned field mapping;
6. semantic projection;
7. guarded canonicalisation;
8. semantic/canonical SQL assertions;
9. a second semantic-pipeline run proving idempotence;
10. export of actual database-population statuses;
11. generation of the private Dataset Explorer from that database state.

## Next implementation steps

1. Review the new full Dataset Explorer, including semantic/canonical table population and review statuses.
2. Apply the validated Cosenza parser family + semantic contract to additional historical Cosenza editions and test incremental identity stability.
3. Continue resolving the remaining national source pages/source series.
4. For each new source, first attempt reuse of an existing validated parser family; create a new family only for a genuinely different physical schema.
5. Reuse semantic record contracts/projectors whenever source semantics are equivalent.
6. Backfill historical sector schemes before 7 June 2020.
7. Add durable content-addressed source-byte storage.
8. Build a stable hosted read-only database/API and final Dataset Explorer.
9. Publish versioned release products only after reuse/privacy review.
