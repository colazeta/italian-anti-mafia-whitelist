# Private production checkpoints

The existing protected `Transform reviewed captures into private observations`
workflow runs `acquisition.production_checkpoint` in shard 0 even when another
source stage fails. It stores the report in the existing immutable private
operations namespace and verifies exact readback. No new scheduler, store,
service, schema or publication path is involved. The operational ledger is
[#225](https://github.com/colazeta/italian-anti-mafia-whitelist/issues/225).

## Definitions and units

Each report pins an exact code revision and one transaction timestamp. All
queries share a fresh repeatable-read, read-only transaction. Table privilege
checks precede reads; an unavailable numerator or denominator is `not_verified`,
never zero. Registered durability and relational counts do not themselves attest
a fresh original-byte readback, complete snapshot-content rehash, an approved
administrative edition or a public deployment.

| Metric | Numerator / denominator and meaning |
| --- | --- |
| `durable_content_objects` | Durable DB registrations / all registered ContentObjects. Not objects freshly rehashed at the provider. |
| `snapshot_record_occurrences` | Sum of records over all stored interpretation revisions. Not distinct companies or a current population. |
| `parse_run_snapshot_coverage` | Persisted snapshots / registered parse runs. Primary-key/foreign-key constraints ensure one snapshot per run; this is persistence coverage, not approval. |
| `capture_interpretation_coverage` | Captures with at least one exact labelled input and persisted snapshot / all captures. A capture counts once despite multiple interpretation revisions. Not latest-version or full-history coverage. |
| `series_interpretation_coverage` | Distinct non-null captured SourceSeries with such an interpretation / all registered SourceSeries. A series counts once despite many captures/revisions. Not authority or register completeness. |
| `capture_parse_input_mismatches` | Missing/different ContentObject on an exact labelled capture→parse link / all capture→parse links. Bundle secondary inputs must match `parse_run_input`, not the legacy primary `parse_run.content_object_id` anchor. |
| `snapshot_count_mismatches` | Stored record_count different from the JSON array length / all snapshots. Structural validation only, not a canonical content-digest rehash. |

Base table counts also expose registered sources, captures, originals, parse
runs, labelled inputs, snapshots, source records, administrative editions,
semantic observations and canonical entities as separate layers. They do not
combine into a single misleading conversion percentage. Public coverage,
candidate-version queues and source freshness use the separately SHA-bound
selected-publication ledger and robot observations.

## Failure and privacy behaviour

A nonzero count/labelled-input mismatch is recorded as
`integrity_status: failed`. Persist and read back the private report **before**
returning a nonzero process exit. Monitoring does not repair or rewrite evidence,
invent an attribution, grant access, or automatically approve/reject a release.
Other correctly scoped stages retain their own outcomes.

The console emits only `checkpoint_persisted`, verified/unverified metric counts,
`failed_integrity_checks`, and zero `publications`. Full metrics, rows, object
coordinates, SQL exceptions and credentials cannot expand that public surface.
Unavailable permissions remain explicit and do not trigger privilege changes.

## Dated production reconciliation — 15 November 2026

Direct Neon SELECTs on `rapid-dust-83010061`, branch
`br-sparkling-boat-b954jrme`, database `whitelist` measured:

- **14:43:06 UTC:** 134 SourceSeries, 621 captures, 417/417 originals registered
  durable, 745 runs/745 snapshots, 233,123 record occurrences across revisions;
  zero runs without snapshots and zero stored-count/JSON-array mismatches.
- **14:45:30 UTC:** 0/778 labelled link mismatches. Nine valid secondary bundle
  links differ from the compatibility primary anchor and must not be reported as
  corruption.
- **14:50:04 UTC:** 518/621 captures with a persisted labelled interpretation;
  131/134 registered series with a linked interpretation; 754/754 runs with
  snapshots. These are separate transaction checkpoints, not an assertion that
  all increments were produced by this metric change.

Tests cover missing readers, unavailable denominators, unit separation and
persist-before-failure/redaction. The existing `tests/evidence_db_check.py` also
executes the real PostgreSQL permission/count/join SQL in a read-only consistent
transaction after schema application in CI. The ordinary protected workflow is
the separate provider acceptance for persistence/readback of the private report.
