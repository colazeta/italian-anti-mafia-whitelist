# Project rules

These rules make the archive readable, reproducible and safe to extend. They are normative for repository changes.

## 1. One concept, one layer

The project separates five different things that must never be conflated:

1. **Source discovery** — where a White List source exists and what type of publication it is.
2. **Source capture** — what exact resource was retrieved, when, with which HTTP metadata and byte identity.
3. **Parsed source observations** — what records and raw values were observed in captured content.
4. **Canonical administrative data** — resolved entities, relationships, sectors, procedures and states.
5. **Release data** — reviewed outputs intentionally prepared for reuse or publication.

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
  source_registry/          source-discovery and coverage research
  captures/                 immutable capture manifests and safe aggregate diagnostics
  releases/                 reviewed, intentionally released data products

db/                         PostgreSQL schema, seeds, migrations/patches and DB tests
src/white_list_archive/     acquisition, parsing, resolution, persistence and export code
tests/                      Python/static governance and source-registry tests
.github/workflows/          automated verification and acquisition workflows
```

Raw source bytes and row-level working extracts are not committed to Git unless a later, explicit storage and dissemination decision says otherwise.

## 3. Source facts are immutable

- Never overwrite raw source values to make them fit the canonical schema.
- Byte identity is SHA-256-addressed.
- A new parser produces a new parse run; it does not rewrite an earlier parse.
- Source captures retain acquisition time and available HTTP metadata.
- A URL is not a document identity; the same URL may serve different editions over time.

## 4. No inferred administrative event without evidence

- Absence from one edition is not administrative removal.
- Nominal expiry is not automatically loss of legal effect.
- A source `Esito` label is not automatically a canonical legal-effect status.
- A change between editions is first an observational fact. Administrative interpretation belongs in a separate, evidence-backed layer.
- Unknown dates remain unknown. Do not invent start dates or replace unknown periods with artificial unbounded ranges.

## 5. Identity rules

- Never use a name as a canonical identity key.
- Source identifiers are evidence, not infallible primary keys.
- Composite `CF/P.IVA` fields stay unresolved when the identifier scheme cannot be established.
- Entity and procedure resolution are explicit, reviewable processes with provenance.
- Stable project codes may support idempotent ingestion, but must be labelled as internal project identifiers and never presented as administrative identifiers.

## 6. Taxonomy rules

- White List section notation is version-dependent.
- A notation such as `I` or `X` must always be interpreted through a `SectorSchemeVersion`.
- Stable sector concepts are distinct from section numbers.
- White List listed sectors are administrative list associations, not NACE classifications and not necessarily the exclusive legal-effect scope of White List registration.

## 7. Temporal rules

Keep the time dimensions separate:

- `effective_time` — when an administrative/canonical fact applies;
- `source_reference_time` — what date/period a source claims to describe;
- `capture_time` — when the resource was retrieved;
- `system_time` — when the archive recorded a canonical version.

Uncertainty must be represented as uncertainty, including lower/upper bounds and precision where appropriate.

## 8. Provenance rules

- Canonical facts can have multiple supporting or contradicting source items.
- Do not use a single source FK as the entire provenance model for important canonical facts.
- Every transformation that matters for reproducibility must be attributable to a processing activity or exact code revision.
- Derived events must carry a derivation rule/version and input lineage.

## 9. Data publication rules

The internal archive and a public release are separate products.

- `data/source_registry/` may contain research metadata about sources.
- `data/captures/` may contain capture manifests and safe aggregate diagnostics.
- Row-level source or canonical data are not automatically public merely because the original administrative source was public.
- `data/releases/` contains only outputs deliberately approved for release.
- Publication/reuse decisions must account for personal-data fields, sole traders, licensing and transformation needs.

## 10. Documentation and catalog coupling

A pull request must update documentation when it changes semantics, storage, workflow or release state.

Every persistent `.csv` or `.json` under `data/` must be listed in `data/catalog.csv`, except the catalog itself. Each catalog entry states the data layer, scope, status and release class.

## 11. Change workflow

Substantive changes should follow:

`research/evidence -> branch -> implementation -> tests -> documentation -> PR -> CI -> merge -> post-merge verification`

Schema changes additionally require:

- a documented semantic reason;
- relational/constraint tests where enforceable;
- compatibility or development-release notes;
- no silent reinterpretation of already frozen release semantics.

## 12. Definition of done

A change is not complete merely because code runs. It is complete when:

- the relevant tests pass;
- provenance is preserved;
- the data catalog is current;
- documentation explains how the new object is interpreted and where it lives;
- no unresolved empirical assumption has been silently converted into a fact;
- post-merge CI on `main` is green.
