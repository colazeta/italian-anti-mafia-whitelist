# Legacy capture recovery migration

Issue #163 requires historical source versions to remain recoverable without inventing
capture provenance. A narrow exception exists when the project still possesses a
contemporaneous acquisition package that contains the exact original bytes and the
capture metadata recorded by the acquisition itself.

## Boundary

A legacy recovery migration is not a new acquisition and is not a reconstruction from
current rows, aggregate history or a known hash. It is allowed only when all of the
following agree before any governed-store write:

1. the repository legacy capture manifest;
2. the exact bounded evidence package and its reviewed package SHA-256;
3. the contemporaneous capture manifest inside that package; and
4. the exact original member bytes, verified by byte size and SHA-256.

The recovery runtime then sends those already verified historical bytes through the
normal archive-first boundary. ContentObject write/readback happens first; immutable
CaptureCatalogue write/readback follows. No parser, projection or release is accepted
before those controls.

## Historical capture identity

The old Cosenza capture manifests predate the stable archive-first capture UUID. They do,
however, preserve a positive acquisition event: stable SourceSeries, capture timestamp,
byte SHA-256, original/resolved locator and declared reference date.

For this compatibility migration only, the capture UUID is deterministic from that
historical acquisition provenance. It never uses the migration processing time and it is
never minted from a hash alone. Re-running the migration therefore addresses the same
historical capture/check and must be idempotent at both ContentObject and catalogue
layers.

Unknown dates remain unknown. Declared source reference date, historical capture time
and current migration processing time are separate fields/concepts.

## Recovery-plan schema v2

Existing schema-v1 recovery plans remain valid. The migration proof uses an additive
schema-v2 plan with an explicit `capture_migrations` collection.

Each migration names exactly one repository-supported `known_version` by authority,
`evidence_version_key` and SHA-256, and supplies the recovered frozen capture,
immutable catalogue receipt and operator evidence references.

Materialisation replaces that exact historical row one-for-one with the recovered
capture. It does not append a second denominator item. The denominator cardinality must
therefore remain unchanged. SourceSeries ownership and byte size must agree with
reviewed repository evidence; otherwise migration fails closed.

A successful migrated capture becomes `verified` only when the governed provider
rereads both its exact ContentObject and its immutable capture provenance. Package
availability alone is `recoverable_pending`, not `verified`.

## Cosenza recovery target

The retained GitHub Actions evidence package from workflow run `34051655207`, artifact
`9994719997`, was verified during recovery. Its reviewed package SHA-256 is
`0ff0a21f494685f0f01b73b8dfd905b6cd7193718c4253e8f6a0ed08da257071`.

It contains the two original Cosenza PDFs represented by:

- `data/captures/cosenza/combined_2026-06-28.json`;
- `data/captures/cosenza/combined_2026-08-03.json`.

Protected run `36511913025`, on `main@3d5b0f1f0ec038250a63d5409aadf0509ce4daa8`,
completed both recoveries and the one-for-one denominator migration. The exact
capture IDs are `9e769f09-3d3c-5d2a-b0f7-1b53ee5895c0` (28 June reference) and
`32f713a4-2106-5c58-8256-6f3c02c133c3` (3 August reference). Historical capture
times remain 6 September 2026 at 18:25:35 and 18:25:37 UTC respectively.

Subsequent inventory proofs read these already recovered catalogue records and
ContentObjects and compare their acquisition metadata with the original repository
manifests. They no longer download or rewrite the retention-bound package. Failure
to retrieve a selected archived original fails the proof; there is no fallback to
current Prefecture URLs. The original package adapter remains available for other
positively evidenced historical recoveries. This readback is not independent restore.

After successful provider/catalogue readback, the two existing legacy `known_version`
rows are replaced by the two capture identities in the recovery denominator. The
national denominator must remain unchanged rather than increasing by two; the proof
must derive its baseline from current repository state rather than a historical prompt
count.

## Non-claims

This migration closes only a recoverable historical-source gap. It does not establish
production relational capture persistence, persisted ParseRun/observation snapshots, a
complete frozen national release, full archive-backed national replay, public deployment
or independent backup/restore. Those remain separate acceptance evidence under #163.
