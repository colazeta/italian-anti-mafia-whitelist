# Frozen replay observation persistence

Issue #163 requires a selected archived source interpretation to survive independently of a later source-level or national release failure. Durable source bytes and capture/check provenance already cross the archive boundary before parsing; this layer extends the same separation to parser observations.

## Boundary

The observation-persisting replay is a stricter execution mode around the existing frozen-release builder. It does not create another acquisition path and it does not fetch official source URLs.

The order is:

1. validate the reviewed frozen release manifest against the exact publication configuration;
2. use the existing archive-backed replay to verify every selected immutable capture-catalogue receipt and every selected ContentObject by provider readback before parser access;
3. execute one configured parser over those archived inputs;
4. immediately persist the complete parser records and diagnostics through `source.parse_snapshot`, together with exact labelled `source.parse_run_input` and `source.capture_parse_run` lineage;
5. commit that source interpretation independently;
6. only then continue source acceptance, semantic approval, aggregate registry validation and any later release gate.

A later failure therefore cannot erase a parser interpretation that was successfully produced from already archived inputs. Conversely, an observation-database failure stops the replay before the affected parser result can be treated as an archive-complete interpretation. The source bytes and immutable capture provenance remain recoverable in the private evidence store.

## Interpretation is not publication

Persistence happens immediately after parser execution returns, before public source validation and global release acceptance. A persisted `ParseRun` with `status_code = succeeded` means that the parser execution completed and its exact output was preserved. It does **not** mean that the output was accepted for publication, semantic projection or canonical administration.

This distinction is intentional. A parser result may later fail row-count, semantic digest or national release validation and must still remain auditable as an interpretation that actually occurred. A parser exception produces no parse snapshot; its already archived capture remains recoverable and may be quarantined/reprocessed later.

No `SourceEdition` is created or inferred by this path. Declared publication/reference time stays on source provenance, capture time stays on the capture, parser processing start/end time stays on processing provenance, and legal/effective time remains a separate downstream concept.

## Transaction and failure semantics

Each source parse snapshot is committed in its own database transaction. This is deliberate: a later parser or national release failure must not roll back earlier successful observation snapshots. Repeating the same interpretation remains idempotent through the existing parse-run/snapshot identity rules; a changed parser/configuration/code revision creates a different interpretation, not a new administrative publication.

The replay refuses to start this persistence mode unless `EVIDENCE_DATABASE_URL` is available. Database coordinates are never written into public logs. The protected replay emits only a redacted count of committed source parse snapshots together with the reviewed release id and code revision.

## Bundle inputs

The persistence layer consumes the exact labelled capture set from each frozen source binding. Scalar sources retain their established `primary` compatibility identity. Bundle parsers retain every label/capture separately, including equal-byte ContentObjects. A URL is never used as parser-observation identity.

## Scope and evidence claims

This code path is necessary for production historical-observation persistence, but tests alone do not establish it. Unit tests verify the ordering boundary and fail-closed writer behaviour; PostgreSQL regressions separately verify append-only parse snapshots and labelled input constraints. Acceptance under #163 still requires an actual protected replay against the approved private provider and production evidence database, followed by readback evidence. National recovery reconciliation, a complete selected frozen release and independent restore controls remain separate acceptance items.
