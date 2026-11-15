# Validated candidate → governed publication handoff

`Public registry candidate` previously ended by storing five derivatives and
asking an operator to construct the selector PR. Its existing main-only
`preserve` job now prepares that handoff. It keeps its existing `contents: write`
and `actions: read` permissions; it cannot open/merge PRs or deploy Pages. No new
credential, environment, scheduler or publisher is added.

## States and continuation

| State | Meaning | Existing orchestrator action |
| --- | --- | --- |
| `no_release_delta` | Exact public observations and source identities are already selected; only technical check/generation metadata differs | Keep the selected release. Do not create a duplicate release, branch or PR. Archive/check history continues independently. |
| `review_intent_required` | The candidate passed build gates but its changed scopes have no committed finite publication intent | Preserve the candidate. Finish source review and merge its intent; never manufacture approval from candidate output. |
| `selector_proposal_ready` | Reviewed intent, source scopes, full observation digests, unchanged unrelated reports and byte identities agree | Read the release's `proposal.json`, verify current main/intent, open or resume the indicated selector PR, require its checks, then merge serially. |
| Failure | Missing/corrupt public asset, stale main/intent, incomplete populations, unexpected scope, conflicting proposal or changed reviewed values | Retain the selected release; record the exact gate and resume after correction. A successful preserve is not publication. |
| Selected → live verified | The selector PR is merged | Follow the existing sole `Public retro portal`; verify build, deployment and all five live hashes/sizes. Record evidence in #225. |

The scheduled orchestration already has authorised PR/merge access and must
prioritise unfinished validated selector proposals before starting another
source-review task. GitHub's job token does **not** start PR checks through its
own branch push; the orchestrator opens the PR through the existing connected
GitHub access. This is an explicit continuation boundary, not a new unattended
approval mechanism or a promise that a quarantined document will publish.

## Pre-merge review

The existing candidate build also runs the identical five-file/full-record
intent gate with `--review-only` before browser and link acceptance. It reads the
exact checked-out PR tree and its SHA-pinned selected baseline; it performs no
Git operation, release creation, branch write, approval or deployment. It writes
only an aggregate temporary receipt outside the public build. A stale intent,
unexpected outside-scope observation/report, corrupt asset or missing source
review therefore fails before merge. The two execution modes are mutually
exclusive. After merge the protected preserver still independently revalidates
current main, all durable assets and branch consistency; PR success cannot
substitute for those production checks or live verification.

## Finite reviewed intent

A source-review PR may add/update
`data/publication/incremental_release_intent.json`, with a corresponding catalog
entry. Its closed fields are:

- `schema_version`: 1;
- `baseline_manifest_sha256`: canonical configuration SHA-256 of the exact
  selected `public_snapshot.json`;
- `source_config_sha256`: canonical configuration SHA-256 of the reviewed
  `multi_prefecture_pilot.json`;
- `review_document`: an existing `docs/sources/*.md` review;
- `changes`: exactly the changed SourceSeries keys, each pinning `count`,
  `statuses`, `reference_date`, `sha256`, `parser`, `records_sha256`.

`records_sha256` is `publication_handoff.records_digest` over every approved
public value, sorted by physical record locator. It includes original identity
and parser lineage; it is not a company identity or administrative event. The
values come from independently reviewed source QA, never automatic adoption of a
new candidate's unexpected output. Scope expansion needs its own review; this
handoff keeps authority/register/source coverage unchanged.

Both populations must exist for each changed register; an unchanged sibling may
satisfy its population. A combined source represents both without duplication.
Source dates cannot move backwards. All observations/status totals and full
digests must match the intent. Every unrelated observation and source report,
including its original verification time, must remain exact.

## Integrity, identity and retry

The preserver chooses the latest unexpired, unambiguous public build artifact
from **the same run**, so a preserve-only retry can use a successful earlier
build attempt. It verifies every candidate asset and restores/re-verifies the
selected baseline. Before a branch write it verifies all five **durable release
assets**, not merely the local pack or manifest.

The two-file proposal consists only of `public_snapshot.json` and monitoring
regenerated from the exact candidate registry bytes. Live deployment remains
unknown in that ledger. A stable proposal identity derives from baseline,
reviewed configuration and intent rather than run ID, attempt or generation time.
The existing proposal is re-read and revalidated, including its durable assets,
instead of force-pushed or replaced by a second proposal. Existing conflicting
or stale branches fail closed. The writer uses a separate Git index, appends a
branch commit and never writes `main` or changes the checked-out worktree.

Candidate code must remain an ancestor of current main and all approval inputs
(parser/publication code, source registry, configuration, public UI/contracts and
publication workflows) must remain identical. Unrelated documentation commits
may advance main; a newer selected release cannot be overwritten by an older
candidate. Ordinary required PR checks and source/privacy rules still apply.

`proposal.json` contains only source keys, aggregate identities, Git revisions,
state and the branch/commit to resume. Original bytes, private rows and provider
coordinates never enter this handoff. After a reviewed source-pair release has been selected and all five live assets
have passed SHA/size acceptance, the corresponding scopes can be added to the
explicit preserved-public-source set. In the fully preserved case, the builder
restores the exact selected five-file derivative, checks every scoped source
descriptor, report, parser and complete record identity, and reuses it without
refetching mutable official pages. It fails closed on a changed source descriptor
or any corrupt/missing selected asset; this is **not** approval of newer page
bytes or an alternative publisher. The next source-review PR removes only the
new pair from preservation and uses an intent bound to the newly selected base.

The previous selected immutable release
remains available for rollback throughout failure and recovery.
