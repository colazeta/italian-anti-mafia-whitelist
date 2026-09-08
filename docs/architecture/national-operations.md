# National coverage and source monitoring

The internal `data/monitoring/national_coverage.json` ledger uses the existing 106
territorial-authority keys. It is not a company registry, does not replace the
listed/applicant source-population ledger, and is excluded from the public artifact.

## Evidence and initial state

The seed reconciles the territorial CSV with the reviewed directory artifact from
run 34252484175 and the approved publication configuration at commit 00a9e82.
Four explicit Ministry-directory aliases preserve the existing authority keys:
`bolzano-bozen` → `bolzano`, `la-spezia` → `spezia`,
`monza-e-della-brianza` → `monza-e-brianza`, and
`pesaro-e-urbino` → `pesaro-urbino`. The website template is not an authority.

All territories have an identified official index destination; only 34 have a
separately verified primary page. A date-only previous investigation is retained
as such. It is never converted into an invented successful monitoring timestamp.
Current-edition identification and uninvestigated history are unknown (`null`).
The latest approved source reference dates are retained without asserting currentness.

The four existing public pilots retain `public_export_enabled=true` and progress
`VALIDATED`. This reflects their approved source-observation parsers, not completed
production ingestion. Only Cosenza has the existing canonical integration benchmark.
Its two frozen capture manifests explicitly identify ephemeral artifact storage.
The first operational check subsequently marks Cosenza `BLOCKED`, retaining its
last completed `VALIDATED` stage, after source access is denied. See the dated
Cosenza check record. None is promoted to terminal `PUBLISHED`: durable evidence verification remains
false, consistently with issue #16. No published company data is withdrawn.

## States and queue

Coverage: `NOT_STARTED`, `SOURCE_IDENTIFIED`, `CAPTURED`, `PARSER_IMPLEMENTED`,
`VALIDATED`, `PUBLISHED`, `BLOCKED`, `NOT_APPLICABLE`.
Monitoring: `NEVER_CHECKED`, `CURRENT`, `CHECK_DUE`, `CHECK_FAILED`,
`SOURCE_CHANGED`, `PROCESSING_UPDATE`.

`PUBLISHED` requires all source, capture, parser, canonical integration, population,
public-export and durable-evidence gates plus completion evidence. `NOT_APPLICABLE`
requires an explicit reason and evidence; a failure to discover a list cannot
justify it. `BLOCKED` is never terminal. No exceptions are seeded.

Validate against the canonical authority universe before selecting:

```bash
python -m white_list_archive.acquisition.operations data/monitoring/national_coverage.json
```

Expansion prioritises investigated work, the furthest completed implementation
stage, existing canonical integration, actionable source issues, unrepresented
regions, then oldest investigation/check. The key is only the final deterministic
tie-breaker. Review current issues and ledger evidence before every selection;
the stored actionable-issue flag is not a substitute for that review.
Cosenza is first because it already has the canonical benchmark and the oldest
investigation among the four validated pilots, not because its parser is universal.

The `transition` function records mode changes. Maintenance starts only when every
territory is defensibly terminal. Each selection recomputes a queue ordered first
by oldest successful source check (unknown first), then failed attempts, edition
age and content-change age. Returning to incomplete coverage restores expansion.
There is no fixed national rotation.

## Recording checks

`record_check` accepts only a completed landing-page/resource investigation, with
an evidence locator and the complete set of verified resource SHA-256 identities.
A link availability check or retrieval of an already-known PDF alone is insufficient.
Partial/failed checks record an error and cannot replace previous content identities
or advance successful recency. Successful unchanged checks advance recency without
creating a capture or changing an edition date. Changed bytes mark a processing
need; repeated unchanged checks do not hide a pending update, even after an
intervening failure. `source_update_pending` survives failed checks and may be
cleared only after the separate update pipeline has validated integration. Source captures,
parser validation, canonical integration and public export remain separate operations.

Checks append evidence events; functions return a copy and never rewrite an earlier
event. Git versions this operational ledger, so a recorded no-change check can
legitimately require a small PR. The acquisition layer remains responsible for
immutable content storage and deduplication. This module does not claim to run a
background worker or a source-specific monitor that has not been implemented.

## Operational cycles and rollback

Work one Prefecture at a time, checkpoint within 60 minutes, and continue the same
Prefecture when unfinished. Each checkpoint records mode, Prefecture, completed
work, evidence, tests, public effect, problems, coverage, last successful source
check and next action/Prefecture. See the working record. Never promote coverage
to meet a cycle deadline. A global source-storage blocker requires resolution,
not a sequence of falsely completed Prefectures.

Changes use focused PRs and green CI. Revert a ledger/code commit to roll back an
operational decision; do not delete frozen source evidence or canonical history.
The ledger is reviewable infrastructure. Permanent evidence storage still requires
the separately documented backend and retention/integrity guarantees in issue #16.
