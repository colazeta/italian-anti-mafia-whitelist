# Private parse observation snapshots

Issue #163 requires the archive to preserve not only immutable source bytes and capture/check provenance, but also the historical interpretations produced from those bytes. Public aggregate history is not sufficient for this purpose: it cannot reconstruct parser-level source observations and it must remain separate from private source evidence.

## Identity and time model

A `SourceCapture` records one acquisition/check and its capture time. A `ContentObject` identifies the exact bytes. A `ParseRun` is an interpretation revision of one ContentObject under one parser revision, configuration and code revision. A parser rerun never creates a `SourceEdition` merely because the interpretation changed.

`source.parse_snapshot` stores the complete parser record array for a successful parse run as private JSONB together with a canonical snapshot SHA-256 and record count. Processing timestamps and parser/configuration lineage remain on the linked `provenance.processing_activity`; declared source reference/publication time remains on source provenance. The snapshot therefore does not overload capture time, source time or effective/legal time.

`source.capture_parse_run` is an append-only bridge between acquisition provenance and interpretation provenance. The database rejects a bridge when the capture and parse run do not reference the same ContentObject. This supports the required cases without collapsing identities:

- two captures of unchanged bytes remain two captures but may reuse one parse run and one observation snapshot;
- byte-distinct captures cannot share a parse run;
- a new parser/configuration/code revision on unchanged bytes creates another parse run and snapshot, not another administrative publication;
- an unparsed or quarantined capture can exist with no parse link at all.

## Persistence boundary

`white-list-persist-parse-snapshot` starts after archive-first capture persistence. It refuses captures whose ContentObject is not marked `durable`, validates the complete JSON record array and hashes it before any write, then creates or verifies the parse run, immutable snapshot and capture/parse association in one caller-owned database transaction.

The input envelope is closed and contains only interpretation metadata plus the record array: capture ID, parser name/revision, exact 40-character code revision, configuration hash, processing start/end times and records. It deliberately has no SourceEdition or publication field. Source administrative identity must come from source evidence, not from a parser execution.

A repeated persistence of the exact same interpretation is idempotent. Conflicting processing provenance for an existing parse-run identity or conflicting output for an existing snapshot fails closed. Snapshot and capture/parse bridge rows reject update/delete operations; a changed interpretation must be represented by a new parse run.

## Scope of the evidence

The snapshot is private internal evidence, not a publication artefact. It supplements the structured `parsed_record`/`source_field_value` model and is useful where national parsers expose heterogeneous source fields that have not yet been normalised into one field-definition schema. It must not be published merely because it exists in the database.

The CI database regression uses real PostgreSQL constraints and synthetic source rows. It demonstrates idempotence, repeated-capture reuse, parser-revision separation, SourceEdition non-creation, immutable snapshots and cross-content rejection. It is not production observation persistence and does not replace the separately required real-provider, national recovery, frozen-release replay or independent restore evidence.
