## Purpose

<!-- Explain the empirical/technical reason for this change. -->

## Layer affected

- [ ] Source discovery / registry
- [ ] Source capture / content storage
- [ ] Parsing / source observations
- [ ] Entity or procedure resolution
- [ ] Canonical White List model
- [ ] Derived events / analytics
- [ ] Release / dissemination
- [ ] Documentation / infrastructure only

## Integrity checklist

- [ ] Source facts remain distinct from canonical interpretations.
- [ ] No unknown date/status/identifier has been silently guessed.
- [ ] Raw source values and immutable content identity are preserved.
- [ ] Temporal and provenance semantics remain explicit.
- [ ] Tests cover the new behaviour or data invariant.
- [ ] Relevant documentation was updated.
- [ ] Every new persistent CSV/JSON under `data/` is listed in `data/catalog.csv`.
- [ ] Row-level/personal-data dissemination implications were considered where relevant.
- [ ] Frozen release semantics are not silently reinterpreted.

## Evidence / validation

<!-- Source references, workflow runs, test results, or audit notes. -->

## Remaining limitations

<!-- State what this PR deliberately does not establish or solve. -->
