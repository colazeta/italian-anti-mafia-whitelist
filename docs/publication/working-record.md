# Operational working record

## 2026-09-08T16:27:21Z — Phase 1 validation checkpoint

- **Mode:** EXPANSION_MODE (expansion execution gated on Phase 1).
- **Current Prefecture:** none selected; public-site revision across the existing release.
- **Completed:** live inspection of all nine former public sections; before/after
  statistic classification; plain-Italian navigation and explanations; exact public
  file allow-list; nested company-field checks; separation of page and edition dates;
  source diagnostics moved outside Pages; PR #38 opened.
- **Evidence:** baseline commit `3cfdcc1`; preserved static metadata; equality of all
  5,052 existing public company-record dictionaries; approved eight-document live
  rebuild passed at PR commit `2c233ce2`.
- **Tests:** 117 baseline / 127 revised local Python tests pass; ordinary CI and full
  Cosenza source/canonical/Explorer regression passed at `2c233ce2`. Browser test
  initially detected a Node/Chromium thousands-separator difference in the assertion;
  corrected to compare numeric values at `17c293e5`. Exact latest-commit gates pending.
- **Public impact:** no deployment yet. Four publishing authorities, five registers
  and all company observations retained. No new Prefecture admitted.
- **Open problems:** final responsive screenshots and official-link report awaiting
  CI; local ministerial downloads return 403; local browser previews are prohibited
  by browser policy. Existing durable-evidence gap (#16) remains explicit.
- **Coverage status:** national expansion incomplete; the current source-backed
  public pilot is not evidence of nationally complete canonical ingestion.
- **Last successful source check:** no new Prefecture-wide monitoring check asserted.
  CI has separately verified approved document identities.
- **Next action:** complete PR #38 responsive/link review, merge only with green CI,
  then verify the deployed site and update the final audit.
- **Next Prefecture:** select from the current ledger and issue tracker only after
  Phase 1 passes; no preselected alphabetical queue.

## 2026-09-08T16:53:34Z — Phase 1 complete; operations infrastructure checkpoint

- **Mode:** EXPANSION_MODE.
- **Current Prefecture:** none ingested in this cycle; Cosenza is next in the recomputed queue.
- **Completed:** PR #38 merged as 00a9e82; deployment and live registry/directory inspected. National internal ledger and queue prepared using all 106 existing authority keys.
- **Evidence:** final PR run 34252484175: all 5,052 rebuilt company dictionaries exactly equal the baseline; 106 directory authorities; all 128 official links HTTP 200. Fourteen rendered views inspected. Post-merge Pages run 34252881996 and Cosenza integration run 34252881934 succeeded.
- **Tests:** 127 Phase 1 Python tests; all existing and seven new operational tests pass (134 total). Tests cover complete national membership, terminal gates, mode transition, recency rotation, no-change checks, failed checks, pending changed content and priority.
- **Public impact:** clearer Italian interface live; company registry preserved. The new ledger remains internal and does not enable another Prefecture.
- **Open problems:** production source evidence is still retention-bound (#16). Unknown monitoring timestamps remain null. No current-edition monitoring success is inferred from document/link checks.
- **Coverage status:** four validated public pilots, 102 identified source destinations, no defensibly terminal production coverage yet.
- **Last successful source check:** none newly asserted.
- **Next action:** validate and merge the focused operations infrastructure PR, then investigate Cosenza's current official source and its remaining completion gates.
- **Next Prefecture:** Cosenza, based on existing canonical integration and the oldest documented investigation among validated pilots. Issue tracker refreshed after Phase 1 merge.

## 2026-09-08T16:57:43Z — Cosenza cycle checkpoint

- **Mode:** EXPANSION_MODE.
- **Current Prefecture:** Cosenza.
- **Completed:** refreshed issues and initial queue; attempted current official landing-page investigation through retrieval and browser; recorded failed check without changing successful recency.
- **Evidence:** docs/sources/cosenza-operational-check-2026-09-08.md; HTTP 403 and browser Access Denied; existing main-branch source/canonical run 34252881934 passed.
- **Tests:** full 134-test Python suite and CI required for the updated operational record; source equality/desktop/mobile/public-boundary checks already passed in Phase 1.
- **Public impact:** no new Prefecture or company observation published; existing registry remains available.
- **Open problems:** current landing page denied in this environment; permanent source-evidence backend/access not provisioned (#16).
- **Coverage status:** BLOCKED; last completed stage VALIDATED.
- **Last successful source check:** unknown, unchanged; the failed attempt is recorded separately.
- **Next action:** resolve designated private evidence storage and source access, then resume Cosenza's current-edition investigation and preservation validation.
- **Next Prefecture:** Cosenza resumes; no switch from this unfinished cycle. No maintenance mode or unattended worker is claimed.

## 2026-09-08T19:46:34Z — Bari source-discovery checkpoint

- **Mode:** EXPANSION_MODE.
- **Current Prefecture:** Bari, first unpublished queue candidate; explicit user request for another territory.
- **Completed:** refreshed main, issue tracker and 106-authority ledger; selected Bari; attempted registered official source; recorded failure precisely.
- **Evidence:** docs/sources/bari-operational-check-2026-09-08.md; official landing-page HTTP 403; issue #20 unresolved populations; issue #16 durable storage still open.
- **Tests:** complete Python suite and ledger validation executed for this change; CI must pass before merge.
- **Public impact:** none; four existing Prefectures and 5,052 presences remain published. Statistics PR #41 is merged and deployed.
- **Open problems:** source cannot be inspected through the available retrieval route; designated durable evidence backend/access remains unavailable.
- **Coverage status:** BLOCKED; last completed stage SOURCE_IDENTIFIED. No parser/capture/validation promotion.
- **Last successful source check:** unknown, unchanged; only last attempted check updated.
- **Next action:** restore authorised official-source access and provision designated durable storage; resume Bari's listed/applicant investigation.
- **Next Prefecture:** Bari resumes when unblocked; no subsequent unit started in this cycle.

## 2026-09-08T20:05:15+00:00 — Operational process correction

- **Mode:** EXPANSION_MODE.
- **Current Prefecture:** none; common infrastructure prerequisite first.
- **Completed:** separated actionable preflight from territorial ranking; explicit storage prerequisite; successful-check completeness attestation; clarified local-blocker fallback and reporting.
- **Evidence:** Cosenza/Bari failed-check records, open issue #16, existing immutable-source architecture. No new source access claimed.
- **Tests:** complete Python suite plus new regressions for missing/unverified storage, local-blocker skipping and rejection of incomplete source checks; CI required before merge.
- **Public impact:** none; company registry, historical captures and public export unchanged.
- **Open problems:** designated durable store/access is still not provisioned; Bari/Cosenza source-access failures remain unresolved.
- **Coverage status:** unchanged, national coverage incomplete.
- **Last successful source check:** unchanged for every Prefecture.
- **Next action:** provision and validate the designated private evidence store using frozen Cosenza documents; the executable decision now reports this explicitly.
- **Next Prefecture:** none until the global prerequisite is resolved; territorial ranking remains available separately.

## 2026-09-08T20:21:47+00:00 — Evidence storage implementation

- **Mode:** EXPANSION_MODE.
- **Current Prefecture:** Cosenza as preservation benchmark; no new ingestion.
- **Completed:** S3 conditional-write adapter, independent retrieval verification, existing ContentObject promotion, CLI recovery, private manual workflow for both frozen editions, operational setup/recovery instructions.
- **Evidence:** storage/evidence.py; evidence-store-operations.md; immutable Cosenza manifests unchanged. Local environment has no configured EVIDENCE/AWS storage variables; available connectors do not provide the designated S3/R2 account provisioning route.
- **Tests:** 151 local Python tests including synthetic storage failure/idempotence tests and Boto3 API stub; CI adds real PostgreSQL promotion with synthetic transport. Live store verification remains separate.
- **Public impact:** none; no source bytes, credentials, receipt or internal storage location added to the public export.
- **Open problems:** designated private backend and authenticated access absent; live upload/recovery and retention/backup verification not claimed. Issue #16 stays open.
- **Coverage status:** unchanged; no promotion of national readiness or a Prefecture.
- **Last successful source check:** unchanged; no new source investigation asserted.
- **Next action:** configure evidence-archive environment as documented; run private live verification; preserve receipts and verify policy before readiness promotion.
- **Next Prefecture:** none until global prerequisite is verified.
