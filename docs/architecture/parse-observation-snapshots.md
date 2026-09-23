# Private parse observation snapshots

Issue #163 requires the archive to preserve not only immutable source bytes and capture/check provenance, but also the historical interpretations produced from those bytes. Public aggregate history is not sufficient for this purpose: it cannot reconstruct parser-level source observations and it must remain separate from private source evidence.

## Identity and time model

A `SourceCapture` records one acquisition/check and its capture time. A `ContentObject` identifies exact bytes. A `ParseRun` is an interpretation revision over one **or more labelled ContentObjects** under one parser revision, configuration and code revision. A parser rerun never creates a `SourceEdition` merely because the interpretation changed.

`source.parse_run.content_object_id` remains the established scalar/primary compatibility anchor. The complete parser input identity is now append-only `source.parse_run_input(parse_run_id, input_label, content_object_id)`. Existing scalar parse runs are migrated explicitly as `input_label = 'primary'`; established parse-run IDs are not rewritten. Bundle parsers retain every member separately, including the case where different captures/labels happen to contain identical bytes.

`source.parse_snapshot` stores the complete parser record array **and diagnostics object** for a successful parse run as private JSONB together with one canonical snapshot SHA-256 and record count. The digest covers both components, so a diagnostic change is an interpretation-output change even when the row array is unchanged. Processing timestamps and parser/configuration lineage remain on the linked `provenance.processing_activity`; declared source reference/publication time remains on source provenance. The snapshot therefore does not overload capture time, source time or effective/legal time.

`source.capture_parse_run` is an append-only bridge between acquisition provenance and interpretation provenance. Its `input_label` identifies the exact labelled parse input supplied by that capture. The database rejects a bridge when the capture ContentObject does not equal that labelled `parse_run_input`. This supports the required cases without collapsing identities:

- two captures of unchanged bytes remain two captures but may reuse one parse run and one observation snapshot;
- scalar and bundle interpretations preserve their complete immutable input sets;
- byte-distinct captures cannot be substituted for a labelled parser input;
- different input labels/captures remain distinct even when their ContentObjects have equal bytes;
- a new input set or parser/configuration/code revision creates another parse run and snapshot, not another administrative publication;
- an unparsed or quarantined capture can exist with no parse link at all.

## Persistence boundary

`white-list-persist-parse-snapshot` starts after archive-first capture persistence. It refuses any selected capture whose ContentObject is not marked `durable`, validates the complete JSON records/diagnostics payload and hashes it before any write, then creates or verifies the parse run, immutable labelled input set, snapshot and capture/parse associations in one caller-owned database transaction.

The established scalar envelope remains valid with `capture_id`. Bundle parsers use `capture_inputs`, a non-empty list of exact `{label, capture_id}` rows; the two forms are mutually exclusive. Labels and capture IDs must each be unique within one parse run, and input ordering is canonicalised by label so caller ordering cannot create a different interpretation identity. The remaining closed envelope contains only parser name/revision, exact 40-character code revision, configuration hash, processing start/end times, records and diagnostics. It deliberately has no SourceEdition or publication field. Source administrative identity must come from source evidence, not from a parser execution.

Scalar parse-run codes preserve the identity introduced before bundle support. Multi-input parse runs use a separately namespaced canonical digest over every labelled input SHA-256 plus parser/configuration/code lineage. This is an explicit compatibility extension: existing IDs are not silently changed, while a changed bundle member necessarily creates a different interpretation identity.

A repeated persistence of the exact same interpretation is idempotent. Conflicting processing provenance, conflicting labelled inputs for an existing parse-run identity or conflicting output for an existing snapshot fails closed. Snapshot, parser-input and capture/parse bridge rows reject update/delete operations; a changed interpretation must be represented by a new parse run.

## Scope of the evidence

The snapshot is private internal evidence, not a publication artefact. It supplements the structured `parsed_record`/`source_field_value` model and is useful where national parsers expose heterogeneous source fields that have not yet been normalised into one field-definition schema. It must not be published merely because it exists in the database.

The CI database regression uses real PostgreSQL constraints and synthetic source rows. It demonstrates scalar idempotence, repeated-capture reuse, parser-revision separation, multi-ContentObject bundle retention, labelled capture/input matching, SourceEdition non-creation, complete records/diagnostics retrieval and immutable snapshots/input provenance. It is not production observation persistence and does not replace the separately required real-provider, national recovery, frozen-release replay or independent restore evidence.