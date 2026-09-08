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
