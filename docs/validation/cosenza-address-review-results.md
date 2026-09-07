# Cosenza ANNCSU substantive address review — results

## Status

The manual Cosenza address-validation milestone is complete for the current exact-linkage architecture.

Frozen review evidence:

- review date: **7 September 2026**;
- canonical address population: **1,298**;
- ANNCSU candidate population: **624 (48.07%)**;
- deterministic review sample: **150**;
- candidate rows requiring substantive match review: **78 / 78 reviewed**;
- `not_found` sample rows: **72**;
- sample fingerprint: `128436f8ad826af033dc03282a1f598a17c987d9a443e27ea4658d9476925eec`;
- original uploaded review-export SHA-256: `105de28cc4fc242fe59f966b540661a56fc98b9486379f8896c50261a6f0f59b`.

The reviewer-decision layer is versioned in `data/validation/cosenza/address-review-2026-09-07.csv`, with source-export identity and interpretation recorded separately in the metadata JSON.

## Important denominator rule

`not_found` is a **coverage/recall failure**, not a returned false match. It is therefore excluded from match precision.

The reviewer explicitly stated after exporting the file that all `not_found` cases were intended to count as failed end-to-end outcomes. In the raw export 14 `not_found` rows were explicitly marked `incorrect` and 58 were blank. The project records that interpretation in metadata; those 58 blanks are not converted into false matches and are not placed in the precision denominator.

## Observed candidate review

| Review stratum | Population | Sample | Correct | Incorrect | Observed precision |
|---|---:|---:|---:|---:|---:|
| `matched_civic_access` | 309 | 36 | 36 | 0 | **100.00%** |
| `matched_street` | 225 | 28 | 16 | 12 | **57.14%** |
| `matched_without_coordinates` | 90 | 14 | 12 | 2 | **85.71%** |
| **All candidates, population-weighted** | **624** | **78** | **64** | **14** | **82.49%** |

The population-weighted candidate precision estimate is **82.49%**. Combining that estimate with observed ANNCSU candidate coverage gives an estimated validated end-to-end yield of **39.65%** of the 1,298-address Cosenza population.

These are descriptive validation estimates for this frozen Cosenza corpus and sample. They are not claims about national performance.

## Interpretation

The review supports treating the precision classes differently.

### `civic_access`

All **36/36** reviewed cases were judged correct. This is the strongest validated class in the current architecture and supports exact Istat municipality + typed `ODONIMO` + exact unique civic/access linkage as the high-quality Cosenza baseline.

The Cosenza sample alone is not used to generalise an automatic national acceptance rule.

### `street`

Only **16/28** reviewed cases received an overall `Correct` verdict. Street-level results therefore remain useful candidates/normalisations but are not sufficiently reliable to promote automatically to accepted geography.

A `street` candidate must also never be represented as civic/access precision.

### Candidate without coordinates

**12/14** were judged correct as normalisations. Because they contain no usable coordinate, they cannot enter geographic truth regardless of linkage correctness.

### `not_found`

All `not_found` outcomes are treated as unresolved coverage failures for this review. They remain an explicit queue for future fallback-provider or improved-linkage work. They are not evidence that the real-world address does not exist.

## Promotion policy after Cosenza review

The current production rule remains deliberately conservative:

- **no ANNCSU class is automatically promoted to `accepted` geography solely from this Cosenza review**;
- `civic_access` is the only current class considered a plausible future auto-accept candidate, subject to replication on additional Prefectures/regions;
- `street` stays `candidate` and may only be consumed as explicitly street-level geography;
- candidates without coordinates are normalisation-only;
- `not_found` remains unresolved/fallback;
- any fuzzy or stronger normalisation stage must be evaluated against this frozen reviewed evidence before adoption.

This policy is already enforced technically: candidate results do not leak into `mart.address_geography`.

## What is closed

For Cosenza, the following part is now closed:

1. provider architecture comparison;
2. exact ANNCSU production linkage;
3. reproducible validation sample;
4. reviewer UI and source/PDF drill-down;
5. completed candidate review;
6. frozen gold-standard decision export;
7. weighted quality measurement;
8. explicit candidate/acceptance policy.

## What remains outside this milestone

The remaining work is nationalisation and unresolved-case handling, not another round of Cosenza geocoder tuning:

- correct source-country modelling for foreign source addresses;
- expose stable address-normalisation quality/coverage metrics in the Explorer;
- orchestrate required ANNCSU regional bulk files by provider version;
- repeat the exact-linkage review on additional Prefectures/regions;
- define and test the managed/self-hosted fallback path for unresolved and foreign addresses;
- benchmark any future fuzzy/normalising stage against frozen reviewed evidence.

Architecture: `docs/architecture/address-normalisation.md`.
Protocol: `docs/validation/address-review.md`.
