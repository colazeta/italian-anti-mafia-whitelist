# Pistoia ANNCSU substantive address review — results

## Status

The first cross-region replication of the frozen exact-linkage policy is complete for Pistoia, Toscana. The production policy itself has **not** been relaxed.

Frozen evidence:

- review date: **9 September 2026**;
- source-backed exact-Toscana address population: **287** unique addresses from the approved Pistoia listed and applicant publications;
- ANNCSU dataset: **`INDIR_TOSC`**, provider version **2026-08-03**;
- ANNCSU candidates: **5 / 287 (1.74%)**;
- `not_found`: **282 / 287 (98.26%)**;
- deterministic review sample: **150** rows, fingerprint `df35ef283e07e2f166b969fbeb86618c04a63a8dbae97b661673431a1dfdde52`;
- all **5 / 5 returned candidates** were substantively reviewed;
- no candidate was automatically promoted to accepted geography.

The candidate decisions are frozen in `data/validation/pistoia/address-review-2026-09-09.csv`; provenance, provider identity, denominator rules and the production-policy decision are in the companion metadata JSON.

## Candidate review

| Review stratum | Population | Reviewed | Correct | Incorrect | Observed precision |
|---|---:|---:|---:|---:|---:|
| `matched_civic_access` | 1 | 1 | 1 | 0 | **100.00%** |
| `matched_street` | 4 | 4 | 4 | 0 | **100.00%** |
| **All candidates** | **5** | **5** | **5** | **0** | **100.00%** |

Because the full candidate population is only five rows, these are descriptive corpus results rather than a stable national precision estimate. The single `civic_access` result is correct, but one additional observation is not enough to convert the Cosenza finding into a national auto-acceptance policy.

`not_found` follows the same denominator rule as the frozen Cosenza review: it is a coverage/recall failure, not a false returned match, and is excluded from match precision.

## Cross-region comparison

| Metric | Cosenza / Calabria | Pistoia / Toscana |
|---|---:|---:|
| Canonical/source-backed addresses | 1,298 | 287 |
| Candidate coverage | **48.07%** | **1.74%** |
| Candidate precision | **82.49%** population-weighted estimate | **100.00%** candidate census (5/5) |
| `civic_access` reviewed precision | **36/36 = 100.00%** | **1/1 = 100.00%** |
| `street` reviewed precision | **16/28 = 57.14%** | **4/4 = 100.00%** |
| Estimated validated end-to-end yield | **39.65%** | **1.74%** |

The key replication finding is therefore not a precision failure but a **large recall/coverage collapse** under the unchanged exact-linkage policy. Of 287 Pistoia addresses, 282 produced `no_exact_street_match`; only five reached a returned candidate. This is a materially different source/provider interaction from Cosenza and is exactly why the Cosenza metrics could not be generalised nationally.

## Interpretation and production decision

The evidence supports three separate conclusions.

First, exact ANNCSU matches that do occur in Pistoia are clean in this frozen corpus: the single exact civic/access match and four street matches were all judged correct at their declared precision. The street results remain street-level; a source civic that was not confidently resolved is not silently promoted to civic precision.

Second, exact-linkage **coverage is not portable across Prefectures**. The unchanged policy drops from 48.07% candidate coverage in Cosenza to 1.74% in Pistoia. The dominant Pistoia error mode is `no_exact_street_match`, so the next empirical problem is recall enhancement and fallback, not loosening precision labels on the five successful matches.

Third, the national production rule remains conservative: **no ANNCSU class is automatically promoted to `accepted` geography**. `civic_access` remains the strongest candidate for a future acceptance rule, now with 37/37 reviewed correct examples across two regions, but the Pistoia contribution is only one observation and the severe coverage heterogeneity argues for more replication before a national rule. `street` remains candidate-only.

The explicit decision after this replication is therefore: **defer national auto-acceptance; proceed to recall/fallback validation while preserving candidate-by-default semantics**.

## Reproducibility

PR #56 added the live `Pistoia address-linkage replication` gate. It downloads and SHA-verifies both approved Pistoia publications, parses their complete listed/applicant populations, extracts exact Toscana source addresses with row-level provenance, uses only the official `INDIR_TOSC` ANNCSU dataset, produces full validation outputs, and builds a database-UUID-independent deterministic sample. The post-merge live run succeeded and regenerated the same sample fingerprint as the PR run.

Live run: `https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/34376366469`.

Related: #17, #28, #31, #32, #33.
