# Automatic private transformation of reviewed White List captures

## Purpose

The **Prefecture robots** workflow already checks all 106 canonical authorities and
archives original bytes and capture provenance independently. This pipeline
adds the missing *automatic private interpretation* boundary after a successful
trusted-main robot run. It does not change what an administrative White List
publication means, nor automatically authorise new public row-level disclosure.

The new **Transform reviewed captures into private observations** workflow runs
automatically after the national robot workflow completes successfully (or by
manual dispatch). Four deterministic authority shards run with two workers
at most in parallel. Each worker fetches the current `robot-state` metadata
index and considers only source keys already tied to reviewed Prefecture
source/parser configurations. One latest complete capture set is considered
per source scope, including every labelled member of a source bundle. If its
bytes equal the approved baseline, no new transformation is attempted.

## Archive-first and database boundaries

1. The robot state selects a candidate capture by exact approved source key
   and URL. State metadata alone is not accepted as proof of storage.
2. The worker reads the exact immutable capture/check record from the private
   `CaptureCatalogue`. Its complete frozen manifest must exist and agree with
   the public robot-state index. Older catalogue entries lacking the complete
   manifest are deferred/fail closed; their provenance is not invented.
3. The worker independently verifies the catalogue record, then reads the
   `ContentObject` bytes from the governed evidence store and recomputes
   size/SHA-256. No live official-source URL is fetched.
4. All source-bundle members must be fully verified before any parser starts.
5. The worker ensures the reviewed `SourceSeries` exists and persists each
   verified capture and its immutable byte identity to the private database.
   Each relational write commits independently of the parser or later sources.
6. Only then does the repository's already approved parser execute. Its full
   records and diagnostics are committed as a **private parse snapshot** with
   exact input capture IDs, parser revision, configuration digest and executing
   Git commit. A failed parser cannot erase the already archived original.
7. A changed byte payload is **not** presumed to have the reference date of
   the formerly approved edition. The candidate parser configuration uses an
   empty/unknown reference date until edition evidence is reviewed.

The SQL writer and archive must already be configured in the approved
`evidence-archive` environment. The workflow does not create a new storage
service, new database, credentials or paid resources.

## Quality, review and publication

- **A successful parse is an interpretation, not acceptance.** Changed row
  counts, semantic drift, unexpected statuses, new publication/reference
  dates, missing listed/applicant populations and legally consequential
  changes still need the existing QA, source qualification and publication
  gates. No `SourceEdition`, legal status or public data is inferred from
  a robot capture alone.
- Newly discovered/unmapped authorities, changed source URLs, unverified
  parser bindings, incomplete bundles, missing provider provenance and parser
  failures are explicit deferred/quarantine cases. They are not silently
  treated as absence, revocation, rejection or approved population growth.
- Parsing outputs and the original documents are private. GitHub Actions
  step summaries contain only bounded counts and safe operational statuses.
  There are no row-level artifacts, direct commits to main, public releases
  or Pages deployments from this workflow.
- The same exact input/configuration/code revision uses the existing
  append-only parse-run identity and database idempotency rules. Repeated
  source checks still preserve separate immutable capture/check provenance.
- The last approved public snapshot remains in place until the separately
  governed, *frozen archive-backed* staging and public-contract checks pass.
  Automatic public promotion would require a distinct reviewed governance
  change and successful completion of issue #163's outstanding gates.

## Operational acceptance criteria

The first protected run should demonstrate separately:

1. robot-state freshness and completed-source candidate coverage;
2. private `ContentObject` and capture-catalogue readback for selected sources;
3. relational capture persistence with complete source provenance;
4. distinct, durable parse snapshots for byte-distinct updates;
5. idempotent retries and explicit quarantine for malformed or missing bytes;
6. no new public release, no row-level artifact and no Pages deployment.

Unit tests of the selection contract are necessary but **do not** prove
production provider/database persistence. A controlled production run and
independent readback are still required before claiming the full automatic
transformation loop operates reliably. The current workflow intentionally
handles the *latest* capture set per reviewed source; backfilling all earlier
historical capture revisions remains a separate reconciliation task.

## Known limitation

A new edition with a different layout can fail its existing parser and must
be reviewed; a fully unattended parser-family authoring process is not
appropriate for legally sensitive records without independent evidence.
The workflow also does not discover or validate the remaining 32 Prefetture.
Those authority/source-mapping tasks remain with the expansion workstream.
