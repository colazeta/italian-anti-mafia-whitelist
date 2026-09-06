# Contributing

The project treats code, data and documentation as one reproducible research system. Read [`docs/project-rules.md`](docs/project-rules.md) before making substantive changes.

## Standard workflow

1. Start from a current `main` branch.
2. Use a focused branch name (`feature/...`, `fix/...`, `research/...`, `docs/...`).
3. Keep source evidence and interpretation separate.
4. Add or update tests with the implementation.
5. Update the relevant documentation and `data/catalog.csv` in the same PR when persistent data change.
6. Open a PR with the empirical/technical reason for the change, not only a list of modified files.
7. Merge only after CI is green.
8. Verify the post-merge `main` run.

## Data changes

A PR adding or changing persistent data must state:

- source and source authority;
- acquisition/reference date where applicable;
- whether the artifact is discovery metadata, capture metadata, parsed observation, canonical data or a release;
- provenance/processing revision;
- whether the artifact includes row-level entities or personal-data fields;
- dissemination/release class;
- limitations or unresolved interpretations.

Every persistent CSV/JSON below `data/` must be listed in `data/catalog.csv`.

## Schema changes

Schema changes require:

- a semantic rationale;
- explicit treatment of unknown/missing values;
- tests for enforceable invariants;
- documentation of any change to temporal, identity, provenance or dissemination semantics;
- a development/release note when the frozen schema contract changes.

Do not weaken constraints simply to make an ingest succeed. If real data reveal a legitimate state not represented by the schema, model that state explicitly and document why.

## Parser changes

- Never overwrite earlier parser results.
- Keep raw source values immutable.
- Record parser/code revision and configuration needed for reproducibility.
- Treat source wording as source wording; canonical interpretation belongs downstream.
- Add a regression fixture/test for each new structural family or parser bug.

## Documentation changes

`docs/README.md` is the documentation index. Avoid orphan documents: new durable documentation should be linked from the appropriate index or parent document.

Use precise vocabulary consistently with the data model. In particular, distinguish source editions, captures, observations, administrative states and derived events.

## Release changes

A public/reusable dataset belongs in `data/releases/` only after the release gates in `data/releases/README.md` are satisfied. Raw public-source availability does not, by itself, establish that every row-level field should be bulk republished.
