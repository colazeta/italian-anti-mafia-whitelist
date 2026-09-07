# Project rules

These rules make the archive readable, reproducible and safe to extend. They are normative for repository changes.

## 1. One concept, one layer

The project separates seven different things that must never be conflated:

1. **Source discovery** — where a White List source exists and what type of publication it is.
2. **Source capture** — what exact resource was retrieved, when, with which HTTP metadata and byte identity.
3. **Parsed source observations** — what records and raw values were observed in captured content.
4. **Semantic projection** — typed ontology-level observations produced from a declared parser record contract.
5. **Resolution / canonical administrative data** — resolved entities, relationships, sectors, procedures and temporal states.
6. **Derived data** — reproducible longitudinal events or analytical views generated from canonical/source history.
7. **Release data** — reviewed outputs intentionally prepared for reuse or publication.

A file or table must have a single primary role in one of these layers.

## 2. Repository placement

```text
README.md                   project entry point
CONTRIBUTING.md             contribution workflow

docs/                       human documentation
  README.md                 documentation index
  project-rules.md          this file
  data-access.md            where data can be seen
  architecture/             durable architecture decisions and audits
  data-dictionary/          semantic definitions
  sources/                  source methodology and source-specific notes
  releases/                 frozen release documentation

data/
  catalog.csv               machine-readable inventory of persistent data artifacts
  source_registry/          source discovery + parser-family/binding/semantic-profile registry
  captures/                 immutable capture manifests and safe aggregate diagnostics
  releases/                 reviewed, intentionally released data products

db/                         PostgreSQL schema, seeds, migrations/patches and DB tests
src/white_list_archive/     acquisition, parser families, semantic projection, resolution, persistence and export code
explorer/                   versioned Dataset Explorer templates
tests/                      Python/static governance and source-registry tests
.github/workflows/          automated verification and acquisition workflows
```

Raw source bytes and row-level working extracts are not committed to Git unless a later, explicit storage and dissemination decision says otherwise. Original source bytes belong in a dedicated evidence-storage backend or a bounded internal evidence package, not in the source-code repository by default.

## 3. Source facts and evidence are immutable

- Never overwrite raw source values to make them fit the canonical schema.
- Byte identity is SHA-256-addressed.
- A new parser produces a new parse run; it does not rewrite an earlier parse.
- Source captures retain acquisition time and available HTTP metadata.
- A URL is not a document identity; the same URL may serve different editions over time.
- When legally and operationally permitted, the exact original bytes used by a production parser should be preserved as first-class evidence.
- Preserved source bytes must be linked to their `ContentObject` identity and verified against the recorded SHA-256 before they are used as parser evidence.
- A durable storage locator is not valid merely because a workflow downloaded a file once. Storage status must distinguish ephemeral/bounded copies from durable evidence storage.
- GitHub Actions artifacts are evidence packages for review, not a substitute for permanent archival storage.
- Git is not the default binary archive. Durable production bytes should live in immutable/content-addressed object storage, with the database preserving identity and storage lineage.
- Parser output should retain a physical source locator where reliable (for example PDF page, table, row or bounding box) so an independent reviewer can return to the original evidence.
- Physical locators are provenance metadata, not administrative identifiers; never invent greater locator precision than the parser can reliably establish.

See [`architecture/source-evidence-archive.md`](architecture/source-evidence-archive.md).

## 4. Parser-family and semantic-projection rules

- Do not create one parser merely because a source has a different URL.
- Do not use an unversioned universal parser that silently handles incompatible layouts.
- Physical extraction implementations are organised as **parser families**.
- A parser family may cover multiple source series only after explicit validation of schema/layout compatibility.
- Explicit `SourceSeries -> ParserFamily` bindings take precedence; exact validated schema fingerprints may allow family reuse; otherwise selection must fail rather than guess.
- Every production parser family declares a stable **record contract** and a field-locator namespace.
- Physical parsers do not write canonical ontology tables directly.
- A versioned semantic profile/projector maps a record contract to ontology-level observations.
- Two physically different parsers may reuse one semantic projector when they emit the same semantic record contract.
- If a source contains a concept not represented by the ontology, record it as unmapped/requires-review. Do not silently mutate the canonical ontology.
- Conservatism applies to inference, not to ontology population: safely typed source facts should reach the semantic layer automatically.

## 5. No inferred administrative event without evidence

- Absence from one edition is not administrative removal.
- Nominal expiry is not automatically loss of legal effect.
- A source `Esito` label is not automatically a canonical legal-effect status.
- A change between editions is first an observational fact. Administrative interpretation belongs in a separate, evidence-backed layer.
- Unknown dates remain unknown. Do not invent start dates or replace unknown periods with artificial unbounded ranges.
- A source listing date that predates a later application date may describe an earlier relationship state; it must not become the decision date of that later procedure.

## 6. Identity rules

- Never use a name as a canonical identity key.
- Source identifiers are evidence, not infallible primary keys.
- Composite `CF/P.IVA` fields preserve every source value and candidate scheme.
- An identifier observed against more than one distinct source name is ambiguous until resolved by stronger evidence.
- A row containing an ambiguous identifier may still be resolved through another independent, non-ambiguous identifier; the ambiguous identifier itself must remain semantic-only until separately resolved.
- Entity and procedure resolution are explicit, versioned, reviewable processes with provenance.
- Stable project codes may support idempotent ingestion, but must be labelled as internal project identifiers and never presented as administrative identifiers.

## 7. Taxonomy rules

- White List section notation is version-dependent.
- A notation such as `I` or `X` must always be interpreted through a `SectorSchemeVersion`.
- Stable sector concepts are distinct from section numbers.
- White List listed sectors are administrative list associations, not NACE classifications and not necessarily the exclusive legal-effect scope of White List registration.
- Requested activities belong to procedures. They must not be promoted to `relationship_sector` unless the source separately proves that the sector is represented/listed on the relationship.

## 8. Temporal rules

Keep the time dimensions separate:

- `effective_time` — when an administrative/canonical fact applies;
- `source_reference_time` — what date/period a source claims to describe;
- `capture_time` — when the resource was retrieved;
- `observation_time` — when the source supports an observed state;
- `system_time` — when the archive recorded a canonical version.

Uncertainty must be represented as uncertainty, including lower/upper bounds and precision where appropriate.

## 9. Provenance rules

- Canonical facts can have multiple supporting or contradicting source items.
- Do not use a single source FK as the entire provenance model for important canonical facts.
- Every transformation that matters for reproducibility must be attributable to a processing activity or exact code revision.
- Parser family, parser version, schema fingerprint, record contract, semantic projector and resolver version are part of transformation lineage.
- Where the source is a document, provenance should allow the reviewer to traverse from a parsed/canonical fact back to the exact `ContentObject` and a physical locator into the preserved original bytes.
- Derived events must carry a derivation rule/version and input lineage.

## 10. Data publication rules

The internal archive and a public release are separate products.

- `data/source_registry/` may contain research metadata about sources, parser families and semantic profiles.
- `data/captures/` may contain capture manifests and safe aggregate diagnostics.
- Row-level source, semantic or canonical data are not automatically public merely because the original administrative source was public.
- Internal preservation of original source bytes does not automatically authorize public redistribution of those bytes.
- `data/releases/` contains only outputs deliberately approved for release.
- Publication/reuse decisions must account for personal-data fields, sole traders, licensing and transformation needs.

## 11. Dataset Explorer rules

- The Dataset Explorer reads actual database-population counts/status where available; it must not hard-code the appearance that a layer is populated or empty.
- An empty object must state why: e.g. `NOT_APPLICABLE_FROM_CURRENT_SOURCE`, `NOT_YET_PROCESSED`, `REQUIRES_RESOLUTION`, or `NOT_YET_POPULATED`.
- Every model object shown in **Struttura dataset** should be inspectable at data level in the internal curator build: table schema, real preview rows and a complete internal export where practical.
- A row-level parser observation should expose the preserved original document and physical source locator when such evidence exists.
- The Explorer must display evidence identity (at minimum SHA-256 for preserved binary documents) rather than relying only on a mutable source URL.
- Source observations, semantic observations, canonical data and release status must remain visibly distinct.
- Internal table CSVs and preserved documents packaged with an Explorer are audit materials, not automatically public releases.
- The interface is dense, table-first and minimal; decorative dashboard conventions must not obscure the data model. The current retro/1990s management-system visual language is intentional unless explicitly redesigned.

## 12. Documentation and catalog coupling

A pull request must update documentation when it changes semantics, storage, parser-family routing, record contracts, semantic mapping, workflow or release state.

Every persistent `.csv` or `.json` under `data/` must be listed in `data/catalog.csv`, except the catalog itself. Each catalog entry states the data layer, scope, status and release class.

## 13. Change workflow

Substantive changes should follow:

`research/evidence -> branch -> implementation -> tests -> documentation -> PR -> CI -> merge -> post-merge verification`

Schema changes additionally require:

- a documented semantic reason;
- relational/constraint tests where enforceable;
- compatibility or development-release notes;
- no silent reinterpretation of already frozen release semantics.

A new parser family additionally requires:

- source-schema inventory/fingerprint;
- representative edge-case fixtures or live QA;
- declared record contract;
- parser-family registry entry;
- source-series binding or validated fingerprint compatibility;
- semantic-profile compatibility check;
- row recall/precision review before production use.

A production evidence-storage implementation additionally requires:

- content-addressed immutable object identity;
- integrity verification against `ContentObject.sha256`;
- explicit durable/ephemeral storage state;
- provenance from source capture to stored object;
- no silent overwrite of existing content;
- retention/backup policy separate from dissemination policy.

## 14. Definition of done

A change is not complete merely because code runs. It is complete when:

- the relevant tests pass;
- provenance is preserved;
- evidence bytes and physical locators are retained where the workflow claims auditability;
- the data catalog is current;
- documentation explains how the new object is interpreted and where it lives;
- parser-family/semantic-profile routing is explicit where applicable;
- no unresolved empirical assumption has been silently converted into a fact;
- post-merge CI on `main` is green.
