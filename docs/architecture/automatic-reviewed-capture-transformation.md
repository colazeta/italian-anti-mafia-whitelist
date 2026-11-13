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

## Trusted capture chronology

Within one reviewed source, robot-state candidate captures are ordered by
**UTC instants**, not the textual order of ISO 8601 timestamps. An offset-aware
capture timestamp is required; malformed or timezone-naive candidates are
ineligible rather than being mistaken for the latest document. Identical UTC
instants retain the existing deterministic capture-ID tie-break.

This selection still only proposes an archive candidate. The existing private
catalogue, exact manifest, immutable original-byte readback and parser gates
remain mandatory. Capture timestamps do not determine administrative edition
dates, and this change does not re-run or re-pin a frozen historical campaign.

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
`PGconn.ssl_in_use` (libpq `PQsslInUse`). A provider proxy's PostgreSQL
backend `pg_stat_ssl` is not substituted for the actual client transport.
Connections without TLS fail before writes. Cipher/protocol details are not
claimed because psycopg does not expose libpq PQsslAttribute.
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

## Bounded historical Cosenza reconciliation

`Reconcile frozen Cosenza captures` materialises only the two exact historical
capture identities already recovered into the private catalogue (28 June and
3 August 2026). It never queries a live Prefecture URL or enumerates a bucket to
infer that evidence is missing. The full original catalogue manifest, byte size,
SHA-256, capture/reference dates and HTTP provenance must agree with the matching
reviewed `data/captures/cosenza/combined_*.json` document before a database write.

The historical recovery predates required resource/authority classification codes.
Those codes are subsequent technical assessments, not new source observations:
policy `reviewed-legacy-cosenza-classification-v1` explicitly classifies only these
two reviewed official PDFs as `primary_official` / `pdf`. Any originally supplied
conflicting code fails. The assessment is preserved separately at private
`operations/v1/legacy-classification/<capture UUID>.json`, bound to the complete
reviewed legacy-manifest digest, original byte digest and original capture UUID.
Conditional creation and exact readback reject a conflicting later assessment.
The original catalogue record and original manifest are never amended. Relational
classification columns represent this separately evidenced assessment where the
original capture lacked those optional fields; they must not be reported as
classification metadata supplied at the original capture time.

Both captures retain their historical UUIDs, timestamps, source locators and
reference dates. The validated Cosenza parser reinterprets exact original bytes,
with expected historical denominators of 1,327 and 1,334 records. Its configuration
uses each matching historical source/page locator, not the current-edition URL.
Each complete private snapshot pins the executing Git revision and configuration,
and is independently read and rehashed after commit. The workflow executes two
passes to prove stable identities are reused. It emits only aggregate totals;
classifications, source rows, originals and detailed attempt reports stay private.

This closes only the selected legacy captures, not the national historical
backlog, normalised semantic/canonical population, independent recovery or any
new public-release approval. Its archive-first compatibility path is deliberately
separate from the strict writer for newly captured source manifests.

## Private structure inspection for edition-bound quarantines

Changed Lodi listed/applicant and Milano combined captures remain quarantined by
`EditionReviewRequired`. Before that unchanged gate, verified archived inputs are
inspected for CSV widths/header positions/section positions or HTML table/header
shape. The append-only private operational report retains actual counts and
booleans comparing selected structural properties with the reviewed parser.
No source cell, company name, identifier, header string or exception message is
included. An unreadable document records an incomplete inspection, not success.

These diagnostics are a review aid, not a parser compatibility decision: matching
counts cannot approve an edition, populate observations or clear the quarantine.
Source reference dates remain unknown. Strict production parser date/hash and
completeness checks are unchanged. Structural diagnostics are excluded from the
closed aggregate public Actions report. Reviewers must still inspect the exact
archived bytes and review dates, semantic/status interpretation and full parser
invariants before any acceptance or publication.

### Bounded transient retries and private quarantine age

The private transformer retries an archived-input job at most three times, with
one and two second delays. Only typed transient storage errors and explicitly
allowlisted PostgreSQL SQLSTATEs at persistence/readback boundaries qualify.
Parser failures, edition review requirements, hash mismatches, TLS validation
failures and permission errors remain fail-closed without retries. A replay
uses the same archived inputs and the existing snapshot idempotence/readback
checks; it does not discover sources or approve an edition.

Private outcomes retain the attempt count. For each quarantined source, input
hash set, stage, reason and error class, an immutable receipt under
`operations/v1/quarantine-first-observed/` records the first observation by this
tracker. Conditional creation and bounded readback verify that receipt; a new
receipt must also pass byte-for-byte readback. Each private operational report
records the resulting age in seconds and its observation timestamps. Age is
not inferred from capture time and does not establish how long a failure
existed before this tracker. Changed bytes or failure classifications start a
separate receipt, while a code deployment alone does not reset it. Previous
receipts are never overwritten or deleted. Current reports identify current
quarantines; receipts alone are not a list of unresolved cases.

Receipt/readback failure produces an unverified ageing diagnostic and a failing
worker exit. These fields, source identities and hashes stay private; the public
operational summary remains an explicit aggregate allowlist. No original rows,
headers, exception messages or company identifiers enter these diagnostics.

## One input revision per automatic cycle

The workflow freezes one trusted main code revision and one robot-state commit
before starting its matrix. Every shard checks out that exact code and reads the
state file from the frozen commit, even if main or robot-state advances while
other jobs are running. The freeze job receives no archive/database secrets; only
main-originated permitted events can reach protected transformation jobs. A
workflow run's trigger SHA may differ from this explicitly frozen execution SHA;
private reports retain the actual executed revision.
## Bounded historical interpretation catch-up

The separate manual **Transform bounded historical reviewed captures** task closes
the latest-only selection limitation without changing the ordinary robot-triggered
worker or adding a recurring schedule. It serialises with the existing private
transformer, uses the same protected environment, `transform_one`, typed bounded
I/O retry policy and private quarantine-ageing receipts.

Selection freezes the exact retained robot-state Git head and enumerates a full
reviewed-authority shard denominator. Scalar sources include every positively
indexed byte-distinct version, including the reviewed baseline. Repeated capture
checks of the same bytes share one interpretation candidate; their immutable
capture identities remain preserved in the archive/history. Complete bundle
candidates contain only labelled capture identities that actually coexist as the
active archived inputs in a retained resource-state revision. No Cartesian joins
or invented source dates create additional bundle versions. Missing source
bindings, unreviewed historical mappings, unknown byte identities and unresolved
active bundle inputs remain explicit private selection-review items.

The private plan pins configuration digests, interpretation keys, exact capture
IDs and hashes, and the first retained Git revision witnessing each candidate.
Legacy metadata absent from the index can be filled only from that exact capture's
verified immutable catalogue record. Conflicting provenance fails; no live-source
lookup, synthetic original or altered catalogue is permitted. The shared worker
still independently verifies original bytes, persists/rereads captures and full
snapshots, clears unreviewed candidate reference dates, and enforces edition-bound
parser quarantines. A successful historical parse is not an approved edition.

Each dispatch attempts one to ten jobs (two by default). Aggregate output gives
the full shard denominator, selection digest, exact frozen robot head, current
cursor, attempted batch size, next cursor and remaining pending count. Continuing
from a nonzero cursor requires both the exact frozen robot head and its selection
digest. Changing the selection invalidates the cursor. The cursor advances
**attempts**, including visible quarantines, and is never a count of successful
validation or public approvals. Re-dispatch an earlier cursor to revisit a failed
batch; idempotency and reread checks remain those of the common transformer.

The full bounded attempt report, selected outcomes, review items and complete
candidate manifest are retained create-only in the existing private operations
report namespace with exact readback. Only aggregate counts and code/history/
selection digests reach logs; no original, parsed rows, report keys or detailed
selection evidence is uploaded as a public artifact. This task covers retained
reviewed robot capture identities, not undiscovered historical publications or
legacy packages that lack that index. Those gaps, independent restore and frozen
national release approval retain their separate acceptance requirements.

Reviewed main changes to the historical worker or its workflow also run a bounded
acceptance batch (shard zero, cursor zero, two attempted interpretations). This
is not a background drain or a second schedule; subsequent batches require exact
continuation pins. Automatic acceptance retains pending work and quarantines.

The safe console summary exposes `quarantine_receipts_verified` over
`quarantine_receipts_expected` (current quarantined outcomes), plus
`tracker_age_max_seconds` and `diagnostic_failures`. A receipt counts as verified
only with an explicit true verification flag and a non-negative integer age.
The maximum is null when there are no quarantines or any current quarantine
lacks verified age evidence; unknown ages never become zero. Diagnostic failures
count unverified current receipts plus a separate operational-report persistence
failure, if present. These fixed aggregates contain no source identities, rows or
private storage coordinates. They do not extend the public artefact contract.
Operational acceptance requires complete receipt coverage and zero diagnostic
failures in addition to the independent private-report readback claim.

## Automatic resumption of a frozen historical campaign

The existing historical workflow now defaults to `resume`. It resumes one batch
of at most ten interpretations, rotating fairly across all four authority shards.
The first bounded acceptance push uses two jobs. Successful trusted-main
`Prefecture robots` completion wakes the same workflow using the existing daily
robot cadence; there is no additional cron, crawler, ChatGPT task or credential.
The owner can also post the exact command `/whitelist-history-resume` on issue
#225. Only a newly created comment by the repository owner on that exact issue
is accepted; PRs, edited comments, other authors, arguments and other issues are
ignored before the protected job. The runtime repeats that event authorisation.
Ignored comments receive a unique concurrency group, so unrelated discussion
cannot occupy the shared transformer lock. Accepted wakes remain serialised with
the ordinary private transformer.

Preparation creates a frozen campaign only when none exists. Its immutable
context pins the exact code revision, configuration-file SHA-256, robot-state
commit, all four interpretation-selection digests and their explicit denominators.
Later robot heads and code deployments do not change an active campaign. The
controller reads its private state and checks out the context's exact code before
executing a worker. Selection/configuration drift fails before interpretation.
A manual dispatch with `restart_cycle: true` explicitly preserves the previous
closing state and starts a separate campaign; no wake-up implicitly restarts one.
The older `manual` mode remains an independent explicit batch operation.

The active JSON cursor under `operations/v1/historical-backlog/active.json` is
mutable **operational state**, separate from source originals and catalogue
records. Updates require the provider's exact ETag through conditional `IfMatch`.
Every batch first writes a new immutable attempt receipt under its campaign's
private operations path and verifies full readback. That receipt binds exact
planned inputs and outcomes, the previous checkpoint hash and the complete next
checkpoint. Only then can the active cursor advance. Reload independently reads
both the immutable campaign context and last receipt and verifies that they agree
with the complete cursor/result ledger. Missing ETags, conditional-write rejection
or mismatched readback fail closed and cannot claim progress.

A process interrupted after database commit but before checkpoint can repeat the
same frozen inputs. The existing transformer rereads/reuses the committed parse
snapshot rather than fabricating a new edition. A rejected cursor update leaves
its append-only attempt receipt intact and the old cursor selected for retry.
No source evidence is overwritten, and no failed result is treated as validation.

The cursor counts attempted jobs. Successful results require independent database
and TLS readback, and explicitly remain unapproved for public publication.
Quarantines remain in a durable unresolved ledger while other unattempted jobs
can progress. When all cursors are exhausted, any unresolved interpretation or
scope-review item yields `blocked_review`, never `complete`. Aggregate inspection
reports the full denominator, attempted, validated, pending and unresolved counts.
A complete campaign therefore means its selected private historical interpretation
scope passed; it does not approve administrative editions, close undiscovered
historical gaps, prove independent restore or authorise a public release.
