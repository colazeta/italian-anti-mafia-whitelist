# Temporal archive audit — 22 September 2026

## Scope and result

Baseline: `main@4f47eac66da1191f7893904a971b1fe417ab4de8`.
Tracked remediation: [issue #163](https://github.com/colazeta/italian-anti-mafia-whitelist/issues/163).

The national temporal archive is **not yet demonstrated end to end**. The existing
R2 provider-compatibility gate remains passed; this audit does not relabel that
provider prerequisite as failed. Issue #16 separately retains the production
DB-promotion and independent restore controls.

## Verified defects and limitations

- `_acquire_source_input` retrieves current official URLs during national builds.
  Raw/semantic pinning then rejects a different currently served version. A
  frozen release must instead read its explicitly selected archived versions.
- The network retry wrapper clears the working directory. Source preservation
  must precede parser/release failure and workspace cleanup. This is a risk in
  the code, not proof of loss of a particular document.
- Public history is aggregate-only and its append workflow depends on successful
  publication. It is not the complete internal capture/observation archive.
- `_parse_source` replaces parser versions with generic `1`/`2` values on its
  general dispatch path. Actual parser, projector, configuration and code
  revisions need to remain traceable.
- `compare_releases` requires increasing complete reference dates and compatible
  parser signatures. Intraday and undated-source comparisons need a separate,
  explicitly labelled capture-time basis, not fabricated publication dates.
- Committed capture manifests currently cover Cosenza. That directory alone is
  neither a national preservation certificate nor proof that other stored
  evidence is absent. Reconcile known hashes against actual storage/catalogues.

## Focused correction in this change

`EvidenceStore.archive` previously checked some provenance only after storage
writes, and used the caller's mutable manifest throughout transport. Valid bytes
could therefore be uploaded without a usable capture receipt, or a receipt could
be relabelled by a concurrent caller metadata change.

The adapter now validates and snapshots JSON capture provenance before upload
and database promotion. Capture timestamps require a timezone; complete stated
reference dates are validated without replacing unknown dates. Source URLs must
be HTTPS without embedded credentials; content types reject control characters.
Readback pins scalar byte identity before invoking transport. Existing keys,
conditional creation, independent size/hash verification and privacy boundaries
are unchanged. Validation establishes metadata structure, not the truth of the
reported capture/publication date.

## Reproduction and test evidence

The tested baseline `storage/evidence.py` was materialised with exact Git blob
identity `e5c57b7fcf30314bad64a697bf29489f0d2d8800`. The existing test module was
also checked against blob `82a973734a22b6a277f138d43497e252f658db16`.

Before the correction, the new synthetic temporal suite produced **11 failures
and 14 passes**. After the correction, the new suite and the unchanged existing
storage tests produced **38 passes** locally:

```sh
PYTHONPATH=src python -m pytest -q \
  tests/test_evidence_store.py tests/test_evidence_temporal_regressions.py
```

These are application-level tests with protocol doubles and Boto3 Stubber. They
are not live R2, database, full national, deployment or independent restore tests.
The whole repository suite and exact-head CI must be checked separately.

## Conditions for national closure

Issue #163 remains open until capture-first persistence and immutable replay are
wired into the real pipeline, full historical observations and parser lineage
are recoverable, intraday/unknown-date semantics are explicit, and a frozen
release can be rebuilt while official URLs change or are unavailable. Missing
archived bytes must fail closed without replacing the previous public release.

Inventory and attempt recovery of known historical gaps before claiming complete
preservation. A hash or an aggregate transition is not a recoverable original.
Only versions actually acquired can be guaranteed retained; versions never
observed between polling runs cannot be invented. Preserve publication rights,
private evidence boundaries, existing locks and the prohibition on unapproved
new costs. No data migration, new storage resource or gate waiver is part of this
focused change.
