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


## Integration and acquisition follow-up

PR #201 passed CI, public artifact and desktop/mobile browser gates, then deployed
successfully on main (run 36339272615, attempt 2). The first release creation
succeeded; its immediate HTTP read hit transient asset propagation. A bounded rerun
after the assets became visible verified release retrieval and deployed. The initial
bootstrap path and publisher write permission are now removed: ordinary Pages
publication reads only explicit release assets and never downloads the current site.

PR #150 is integrated as isolated research with 24 continuously executed
methodological tests. Original numerical results and execution dates are unchanged.

The source integration reconciles the previously reviewed Enna #160 surface
without weakening its exact input gates, and updates Potenza to the independently
repeat-fetched 27 September response. Milano #162 cannot promote its now-replaced
22 September live response. Its last approved public edition is explicitly preserved
from the immutable release, with all old reference/check dates and parser provenance
unchanged. This choice is made before acquisition, never automatically on failure. Enna adds one authority and one
scope: discovery becomes 74 authorities / 146 series / 77 complete scopes; 32 of the
106 national authorities still need discovery. The public selector is unchanged
until a separately validated candidate is deliberately selected.

Source downloads now use four bounded workers and report all acquisition/byte
failures together. They do not discard successful captures or retry the whole
national build. Parsing and semantic acceptance remain strict and deterministic.
The protected archive-reviewed-sources.yml independently preserves exact current
responses for Potenza, Milano and Enna, with immutable provenance/readback; changed
responses are quarantined, not approved. Unknown reference times stay unknown.
Relational capture persistence is attempted only through the existing configured
writer and reported separately. Successful scopes survive another scope's failure.

A successful main source candidate is preserved as an immutable public derivative
release, including its selector manifest. It cannot deploy Pages itself. A reviewed
selector update is still needed. This prevents expired review artifacts from being
the only surviving copy of an approved public candidate.

Automation inspection: the acquisition preparation lane is enabled; the serial
archive/integration lane is disabled (last execution 24 September). A scheduler
timestamp is not a lock or proof of a concurrent writer. This audit performs the
pending integration directly; it does not silently reactivate a disabled recurring
task. No new paid infrastructure is provisioned.

### Confirmed private capture and scope independence

Main archive run [36340494490](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/36340494490)
independently wrote and read back both exact source content and capture provenance:

| Scope | SHA-256 | Bytes | Relational writer |
| --- | --- | ---: | --- |
| Potenza | `69317d249f8968b5a4a39811a78bb47f53fae03b593c1fc1aea4e1c52ca4909b` | 438877 | unavailable |
| Milano | `e656d98e49b0e5838cc8841d78ab6537b0be6ae18cc96252ba1e22993329e9cc` | 972493 | unavailable |

The Milano response from the runner is substantial HTML, unlike the local
interstitial; its new facts have not been reviewed or promoted. Exact original bytes
and immutable capture receipts now survive outside temporary CI storage. This
confirms the private object archive works and isolates the missing relational writer.
It does not establish independent backup recovery or a full national frozen release.

The candidate builder supports `--preserve-public-source` together with an explicit
`--public-snapshot-manifest`. Each reused scope must match the reviewed configuration
by source, authority, register, population, reference date, raw hash, parser, URLs and
observation count. Snapshot hashes are verified before reading. Changed configuration,
missing provenance, unknown keys and mixing with original-source frozen replay fail
closed. All other sources still pass their live byte/parser/semantic gates. Unit
regressions prove reused records and old verification times remain exact, and that
the reused source is never downloaded or reinterpreted. This allows Enna/Potenza to
progress independently while Milano's new edition receives its own review.

The reviewed `data/publication/preserved_public_sources.json` explicitly selects 136
unchanged single-resource public editions (128 raw-hash approvals and eight
independently recomputed approved semantic digests). The same identity and
provenance gates used for Milano apply to every selected scope. The other six source
scopes (new/changed, legacy parser provenance or multi-resource inputs) retain strict live
construction. Adding or changing a configured source does not silently alter this
selection; configuration drift fails until the explicit list is reviewed. Reused
scopes retain their original verification dates and parser provenance. This removes
unrelated current-URL drift from incremental release composition while preserving
the separate national original-source archival debt.

The incremental real candidate also exposed Taranto listed-source semantic drift
(run 36341850295): expected `27211daaa4734c29bc0f48d9a86e229d04671a150fcad997b8045d997e6bab92`,
observed `80d220362fcc571d40eec8736b6c4c53dce2318a7993899e950040d8ba50b84e`.
The released Taranto observations independently recompute to the approved digest.
They are now explicitly preserved with their original raw digest/check date; the
new response is queued for independent archival capture and substantive review.
The same check binds Aosta, Biella and Como's preserved semantic editions. Any
changed observation fails before acquisition. No unreviewed semantic hash is adopted.

The real six-scope build then exposed a pre-existing lineage check mismatch:
Ferrara/Pordenone use explicit publication adapter keys that differ from their
physical diagnostic parser names. The restoration step now recognises only the
five existing, reviewed bindings and preserves the declared parser revision; an
unrelated physical name still fails. Five parameterised regressions cover both
accepted bindings and rejection of different names. No source counts or source
facts change because of this correction.

Cosenza’s existing fully qualified record parser name is likewise preserved through
its explicit adapter binding, with a regression that rejects unrelated module names.
