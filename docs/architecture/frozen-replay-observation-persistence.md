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

## Capture-only semantic projection boundary

The rich combined-White-List projector raises `EditionAttributionRequired`
(`LookupError`) before creating a projection activity if any succeeded rich parse
run in the requested series lacks a capture-to-edition attribution. This also
prevents an attributed subset from being projected successfully while capture-only
inputs are silently omitted by an inner join. The check does not create an edition
or infer attribution from a capture timestamp, declared date or matching hash.
Snapshot persistence remains independent of this downstream requirement. A reviewed
attribution design is required before the affected rich observations can enter this
edition-based semantic projector.


## Exact rich semantic input selection

The current semantic pipeline accepts an optional paired `--parse-run-id` and
`--capture-id`. A pin selects one existing successful Cosenza rich interpretation
and one pre-existing primary `capture_parse_run` link of the same series and exact
ContentObject. Bundled inputs and mixed-series rich records are rejected. The
selected capture must already have exactly one source-edition attribution in that
series with a known observation date; this interface creates no attribution,
approval or administrative edition. Unattributed captures elsewhere in the series
do not invalidate an explicitly selected attributed input.

Without pins the previous series mode remains available only for unambiguous
contexts: capture-only inputs still fail, multiple interpretations of one edition
and multiple editions for one interpretation require explicit selection. No latest
parser, timestamp or arbitrary UUID is chosen automatically.

`057_projection_capture_selection.sql` is an additive schema migration. It retains
all existing projection codes and marks legacy projections with a NULL capture
pin. New pinned projections retain the exact capture FK, constrained to the
pre-existing acquisition/interpretation link; that provenance cannot be changed or
filled in retrospectively. Repeating the same pin reuses its projection. Attempting
to reuse an existing projection through another capture (or through a legacy NULL
pin) requires review and fails rather than duplicating the interpretation or
rewriting lineage. Run this migration through the governed schema deployment path
before using the updated projector against an existing database.

The pipeline passes only the projection IDs returned for its selected inputs into
the canonicaliser. Entity, identifier and procedure loaders all use that same
selection; existing observations from other parser/projector revisions remain
retained and are not silently included in the canonicalisation run. The run
identity continues to bind the exact selected projection codes. A pinned run also
does not perform the unrelated legacy address-country cleanup. Explicit selection
controls interpretation scope; it does not clear source QA flags, resolve competing
source evidence or authorise public dissemination.
