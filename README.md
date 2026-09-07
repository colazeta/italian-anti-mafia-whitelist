# Open Italian Anti-Mafia White List Archive

A national, standardised, longitudinal and provenance-aware data infrastructure for the Italian Prefectures' anti-mafia White Lists.

## Start here

- **See what data/model objects exist:** [`docs/data-access.md`](docs/data-access.md) and [`data/catalog.csv`](data/catalog.csv).
- **Understand geography and listed/applicant source completeness:** [`docs/architecture/geography-and-population-coverage.md`](docs/architecture/geography-and-population-coverage.md).
- **Understand parser families and automatic ontology population:** [`docs/architecture/parser-families-and-semantic-pipeline.md`](docs/architecture/parser-families-and-semantic-pipeline.md).
- **Understand original-source/PDF auditability:** [`docs/architecture/source-evidence-archive.md`](docs/architecture/source-evidence-archive.md).
- **Review the Dataset Explorer checkpoint:** [`docs/product/data-explorer-checkpoint.md`](docs/product/data-explorer-checkpoint.md).
- **Read project rules:** [`docs/project-rules.md`](docs/project-rules.md).
- **Documentation map:** [`docs/README.md`](docs/README.md).

## Current architecture

The frozen database baseline is **schema 0.1.0**; the live development line is **0.1.1.dev0**.

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
Geography enrichment / derived history / marts
        ↓
Dataset Explorer / reviewed releases
```

The project currently contains:

- an audited PostgreSQL 18 schema with tri-temporal canonical state;
- immutable source capture, SHA-256 content identity and parser provenance;
- **106** territorial authorities in the national universe;
- **34** independently verified primary White List pages;
- **28** qualified recurring source series;
- reusable parser families with deterministic source-series/fingerprint routing;
- stable parser record contracts and semantic profiles;
- automatic semantic projection and guarded canonicalisation;
- original-PDF evidence packaging with row→PDF-page locators in the current pilot;
- a data-driven model-population manifest and dense table-first Dataset Explorer;
- a provenance-aware geography model for coordinates, ISTAT administrative geography and versioned NUTS;
- a mandatory source-population completeness ledger requiring **both `listed` and `applicant`** populations for every authority/register scope before it can be considered source-complete.

## Validated Cosenza pilot

The current live pilot uses the frozen official editions **28 June 2026** and **3 August 2026**.

Parser v2 produces:

- **1,327 + 1,334 = 2,661** source observations;
- **18,627** parser-v2 `SourceFieldValue` rows;
- all seven observable source columns;
- **3,258** typed identifier observations;
- **2,663** establishment observations;
- **3,226** procedure observations;
- **8,710** requested-sector observations.

The semantic layer retains **600 explicit review/QA issues** rather than hiding uncertainty. Guarded canonicalisation currently materialises:

- **1,343** `LegalEntity` rows;
- **2,655** accepted entity resolutions and **6** unresolved observations;
- **3,248** ambiguity-safe canonical identifier observations;
- **1,298** distinct source-supported address objects;
- **2,657** establishments;
- **1,343** White List relationships;
- **2,655** relationship-state versions;
- **1,368** canonical procedures;
- **2,651** procedure versions;
- **3,614** requested procedure-sector links.

`whitelist.relationship_sector` remains empty by design because the combined Cosenza source proves requested activities, not independently the sectors represented on the relationship.

## Geography strategy

Source addresses remain immutable evidence. Geography is a downstream enrichment layer:

```text
source/canonical address
        ↓
geo.address_geocode_result
        ↓
geo.address_geographic_unit
        ↓
mart.address_geography
```

The statistical mart is designed to expose, where supported:

`latitude · longitude · coordinate precision · municipality · province/metropolitan city/autonomous province · region · NUTS1 · NUTS2 · NUTS3 · classification versions · provenance`

The preferred Italian source strategy is **ANNCSU** for official address/civic matching and coordinates when available, **ISTAT/SITUAS** for versioned administrative units, and versioned **NUTS** for European statistical geography. External geocoding is a labelled fallback, not the default truth source.

The geography schema and integrity tests are implemented. The existing 1,298 Cosenza addresses have **not yet been bulk-enriched**: the public ANNCSU massive-download endpoint currently rejects the automated GitHub runner. This is tracked explicitly rather than represented as completed geography.

## Source completeness: never forget applicants

A White List publication can expose two logical populations physically in different ways:

- separate listed + applicant PDFs/tables;
- one combined source containing both;
- comprehensive + sector-specific listed files plus a separate applicant source.

The archive therefore requires exactly two logical source targets per authority/register scope:

```text
listed
applicant
```

A combined `listed_and_applicant` source satisfies both without creating fake duplicate source series. If only one population has been discovered, the other remains `UNRESOLVED_REQUIRES_REVIEW`; it is **never** interpreted as “not published”. Completeness is assessed per register/regime, so special registers such as Bologna post-sisma remain separate.

At the current 34-page / 28-series discovery baseline, the deterministic ledger contains **35 register/discovery scopes**: **12** currently account for both populations and **23** remain unresolved/incomplete. These are progress metrics, not evidence that applicant lists are absent.

## Parser-family strategy

The project uses neither one parser per URL nor one universal parser. A parser implementation represents a reusable physical **source family**. Selection is deterministic:

1. explicit validated `SourceSeries → ParserFamily` binding;
2. otherwise one exact validated schema-fingerprint match;
3. multiple matches require an explicit binding;
4. no match produces a controlled new-family review.

Different physical parsers can emit the same record contract and reuse the same semantic projector.

## Where the data are

```text
data/catalog.csv             persistent repository data inventory
data/source_registry/        source discovery + parser/binding/semantic registries
data/captures/               immutable capture manifests + safe diagnostics
PostgreSQL source.*          capture/parse/source observations
PostgreSQL semantic.*        typed semantic observations and review items
PostgreSQL core/whitelist    guarded canonical White List model
PostgreSQL geo.*             derived geocoding and versioned territorial assignments
PostgreSQL provenance.*      transformation/resolution/evidence lineage
PostgreSQL mart.*            curator/statistical read surfaces
Explorer workflow artifact  private auditable curator browser + table CSVs + source PDFs
data/releases/               deliberately reviewed release products
```

Raw/source evidence, internal row-level data and public releases are separate dissemination layers.

## Core invariants

1. Raw/source field values are append-only and never overwritten.
2. Parser versions never rewrite earlier parse runs.
3. Absence from an edition is not administrative removal.
4. Nominal expiry is not automatic loss of legal effect.
5. Sector notation is meaningful only inside its scheme version.
6. Requested sectors belong to procedures; relationship sectors require separate evidence.
7. Canonical facts can have multiple supporting/contradicting evidence items.
8. Canonical corrections preserve prior system-time versions.
9. Unknown dates remain unknown.
10. Internal archive and public release are separate products.
11. Territorial source URLs are verified/discovered, never guessed.
12. Unknown physical source schemas never fall back to a guessed parser.
13. Physical parsers emit record contracts; they do not write the ontology directly.
14. Safely typed source facts automatically reach the semantic layer.
15. Ambiguous identity evidence remains first-class reviewable data.
16. Ambiguous identifiers are not promoted merely because another identifier resolves the row.
17. Chronologically incompatible dates are not silently promoted into procedure decisions.
18. Original bytes used by a production parser should be preserved and hash-verifiable when permitted.
19. Geography enrichment never rewrites the source-supported address and always carries method/version/provenance.
20. Administrative and NUTS geography are versioned reference systems, not timeless labels.
21. Every verified authority/register scope must explicitly account for **listed + applicant** before source-population completeness can be true.
22. Missing applicant/listed discovery means unresolved, never automatically “not published”.
23. Persistent repository data must be represented in the machine-readable catalog.
24. Product surfaces distinguish source, semantic, canonical, geography and release layers.

## Repository layout

```text
docs/                       documentation, rules, architecture, product and sources
data/                       catalogued registry/capture/release artifacts
db/                         PostgreSQL schema, seeds and integrity tests
explorer/                   minimal Dataset Explorer templates
src/white_list_archive/
  acquisition/              source discovery/capture + population completeness
  parsers/                  reusable physical parser families
  persistence/              immutable source persistence
  semantic/                 semantic projection + guarded canonicalisation
  resolution/               reusable resolution components
  publishing/               model/table/evidence/Explorer exporters
.github/workflows/          CI and end-to-end live workflows
```

The project does **not** yet contain a complete national scrape, a durable hosted database, completed bulk geography enrichment, or a public row-level company release.
