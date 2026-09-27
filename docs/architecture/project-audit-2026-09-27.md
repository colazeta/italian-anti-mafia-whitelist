# Project audit — 27 September 2026

## Scope and verified baseline

Reviewed `main@6221ac39792e402545f7a13fb28956ae2b8322cd`, the public site,
open issues/PRs, workflow history, publication contracts, source discovery,
archive/recovery boundaries and the electoral derivation. Changes are verified
in a clean worktree; earlier working files are preserved.

## Findings and remediation

| Finding | Severity | Remediation / evidence |
| --- | --- | --- |
| Two independent workflows deployed Pages | High | One uploader/deployer, `public-pages.yml`; live registry acquisition becomes `public-registry-review.yml`, with its existing source, browser and link gates. |
| UI-only releases depended on 141 mutable source acquisitions | High | Public releases restore five approved derivatives from versioned GitHub Release assets, using a reviewed SHA-256/size manifest. A source change needs a new reviewed snapshot. |
| Snapshot workflow depended on the mutable website it overwrote | High | Preserve the previous approved public bytes in release `public-data-2026-09-27-verified`. Only the initial, exact five pinned hashes may bootstrap from Pages. Main deployment requires successful release-asset retrieval. |
| Navigation waited for the 112 MB registry | High | Attach navigation immediately; fetch data only for the selected section; support `#electoral`; isolate errors and allow retries; prevent late responses from switching views. |
| Electoral comparison overflowed narrow screens | Medium | Grid columns can shrink; wide data tables scroll inside their panel and chart headings wrap. |
| Equal electoral values received different ranks | Medium | Competition ranks (1, 1, 3), without mutating the dataset. Filtering preserves the national rank. |
| Missing ballots appeared as zero reported sections | Medium | Preserve unknown combined completion as null. Display “Non determinabile”; completeness and all scores remain unchanged. |
| Overall score validation checked ranges only | Medium | Recompute all overall scores, event-hour bindings and coverage; validate source hashes, finite values, counts and timestamp/hour consistency. |
| Network retries deleted the whole acquisition workspace | High | Retry only the failing request on transient HTTP/transport errors. Do not retry permanent 4xx errors. Retain each observed byte version under its SHA-256 locally; do not call this durable storage. |
| README and issue #20 described obsolete population gaps | Medium | Recomputed 73 authorities, 145 source series, 76 scopes with both populations. Remaining 33 national authorities are still undiscovered, not “not published”. |

## Publication contract and operation

`data/publication/public_snapshot.json` binds exactly `registry.json`,
`registry.csv`, `prefectures.json`, `prefectures.csv`, `history.json` to decoded
byte hashes/sizes and one explicit release tag. The compressed release assets
contain **already approved public derivatives only**. Originals, review workspaces,
private storage coordinates and credentials are excluded. The source reference
dates, checks and publication semantics are not relabelled by a UI deployment.

The loader stages and verifies all five files before replacing any destination
file; it never selects “latest”. The ordinary publisher runs the artifact validator
and desktop/mobile browser acceptance before deployment. Source candidates retain
their independent official-source link checks; UI deployment does not turn link
availability into a new source check. Aggregate source history listens to successful
source candidates, not repeated UI builds.

To promote updated data: validate a complete candidate (live or frozen), use
`python -m white_list_archive.publishing.public_snapshot pack --data public-site/data
--output /tmp/public-snapshot --tag public-data-<unique-id>`, preserve the five `.gz`
assets in a new release without overwriting assets, then review the generated
`manifest.json` as a replacement for `data/publication/public_snapshot.json` in a
PR. Source acquisition and private evidence retention remain separate obligations.

## Work that still requires operational evidence

* **#163:** the full national original-source frozen release is not yet available.
  The public derivative release fixes website reproducibility; it does not prove
  original-source retention or a national database replay.
* **#16:** R2 has previously passed private content verification. A designated
  persistent observation database and independent backup/restore target still
  require configuration/operational verification. Do not invent credentials or
  promote an ephemeral CI database to production.
* **#67:** the repository rulesets API returns an empty list. Main protection needs
  repository administration capability, absent from the connected write tools.
* **#199 / #162:** Potenza and Milano live source contents differ from approved
  hashes. Their observed changes need substantive review; no hash gate is relaxed.
* **#160:** Enna's prior focused gates passed, but national publication was blocked
  by unrelated mutable sources. Review against current main and preserve the exact
  attachment before promotion.
* **#150:** aggregate research checkpoint is isolated from production; its
  administrative-performance evidence limitations remain explicit.

## Verification

The initial full local suite failed only because optional database/storage packages
were absent; after installing the declared extras, the full suite passes. New tests
cover atomic snapshot restoration, tampering, publication boundaries, request retries,
evidence retention and electoral score reconciliation. Browser tests exercise actual
approved data at desktop/mobile widths, navigation with a failed registry request,
recovery, all four elections, all indicators and tied ranks. The local Chromium
download endpoint was unavailable; the GitHub-hosted browser gate is authoritative.

The local source probe recorded 135 acquisition errors, four matching sources,
one changed HTTP response (Milano: an anti-bot interstitial, not a valid source table) and one semantic change (Potenza). The 403 responses in this
execution environment are not evidence that all those official sites are unavailable
from the production runner. ANNCSU's latest inspected main execution succeeded;
the earlier 403 is not treated as a permanent source failure.
