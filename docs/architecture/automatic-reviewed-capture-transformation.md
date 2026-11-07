# Automatic private transformation of reviewed White List captures

## Purpose

The **Prefecture robots** workflow already checks all 106 canonical authorities and
archives original bytes and capture provenance independently. This pipeline
adds the missing *automatic private interpretation* boundary after a successful
trusted-main robot run. It does not change what an administrative White List
publication means, nor automatically authorise new public row-level disclosure.

The new **Transform reviewed captures into private observations** workflow runs
automatically after the national robot workflow completes successfully. A merge
of changes to the transformer/workflow starts an initial acceptance run; a
weekly Sunday 18:43 UTC schedule is an independent catch-up trigger, and
manual dispatch is retained for diagnosis. Four deterministic authority shards run with two workers
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
6. Immediately after relational capture commit, a **separate database connection**
   reads back capture and ContentObject identity. Missing/mismatched database
   evidence fails closed, without deleting the original.
7. Only then does the repository's already approved parser execute. Its full
   records and diagnostics are committed as a **private parse snapshot** with
   exact input capture IDs, parser revision, configuration digest and executing
   Git commit. A separate database readback verifies the committed snapshot
   digest and record count. A failed parser cannot erase the archived original.
8. A changed byte payload is **not** presumed to have the reference date of
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
  A 14-day Actions artifact contains a **closed, aggregate-only status**
  (no parsed rows, documents, source identities or private coordinates).
  Source-specific investigation remains within the private execution boundary;
  the public artifact exposes only totals for transformations, QA flags,
  blocked dependencies and quarantined candidates.
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
4. distinct, durable parse snapshots for byte-distinct updates, independently
   read back from the database after commit;
5. idempotent retries and explicit quarantine for malformed or missing bytes;
6. QA checks for changed row and sector totals, dropped date rows and missing
   source-status fields; these flag review without automatically approving
   or withholding a successfully persisted private interpretation;
7. a bounded aggregate public operational report, explicitly classified in
   the repository artifact policy; source-specific and row-level reports are
   never uploaded to public Actions artifacts; no public release or Pages deployment.

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

## Release boundary and outstanding acceptance

The automated transformer makes **private interpretations**, not reviewed new
source editions. Before automatic public promotion can be enabled, a selected
frozen release must retain verifiable original bytes and capture provenance,
pass the complete source/population/parser and public contract checks, resolve
edition/reference dates with evidence, satisfy data protection and distribution
policy, and complete the national archive/replay and independent recovery gates
in issue #163. These conditions are not inferred from successful parsing. Until
then, the last validated public snapshot remains unchanged.

A green pull-request CI proves only software-level contracts. The protected
post-merge execution must separately establish valid R2 readback, private
relational capture/snapshot persistence, and safe status reporting. The pipeline
fails rather than silently treating missing database credentials as success.

## Production diagnostics and client transport verification

The production database was activated on 7 November 2026. Runs
[42390480396](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/42390480396)
and [42390699415](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/42390699415)
committed then reused nine private snapshots containing 2,703 records. Twelve
captures reference eleven durable byte objects. These are point-in-time
acceptance counts, not hard-coded expected population sizes. Three candidates
(Lodi listed/applicant and Milano combined) require edition/parser review;
none was promoted. The original nine interpretations all carried QA flags.

Every transformer database connection now checks libpq's **client-side**
`ssl_in_use`, negotiated protocol and cipher. A provider proxy's PostgreSQL
backend `pg_stat_ssl` is not substituted for the actual client transport.
Connections without TLS or negotiated transport evidence fail before writes.
Only a boolean attestation is included in the public aggregate status. The
connection string and its authentication material are never diagnostic fields.

After commit, the transformer reads the complete snapshot through a distinct
connection, recomputes its canonical SHA-256 and verifies its record count.
The reuse path performs the same check and recomputes QA flags from the actual
stored records/diagnostics against the reviewed baseline. Reuse therefore does
not clear existing review flags or masquerade as a new validation.

Each nonempty execution retains a private attempt report at
`operations/v1/transform/<UUID>.json` in the **existing private evidence bucket**.
The report binds the executing code revision and exact labelled capture IDs/
byte digests to outcomes, QA flags and failure stages (archive integrity,
capture persistence/readback, reuse, parser compatibility, parsing or snapshot
persistence/readback). It contains no source rows, raw exception messages or
credentials. Attempts use new keys, conditional creation and exact object
readback; earlier diagnostic evidence is never overwritten or deleted. This
namespace uses application conditional-write protection; it is not claimed to
have the separate `sha256/` Bucket Lock policy. A failed diagnostic write or
readback fails the execution without deleting already committed captures or
snapshots. The public artifact remains aggregate-only and exposes a boolean
private-report verification result, never a private report key.

Edition-bound parsers for Lodi/Milano are explicitly classified as
`edition_bound_parser_requires_review` at `parser_compatibility`, after the
original capture has been preserved. Their approved old dates and hashes are
not substituted into changed candidate inputs. A parser-contract revision must
be independently reviewed before this gate can be removed. No automatic retry
loop attempts to circumvent deterministic edition incompatibility.

These controls do not establish exhaustive national QA, complete historical
backfill, an independent recovery copy, a restore test or a newly approved public
release. Issues #163, #16 and #225 remain open for those separate controls.
