# Manual address-linkage validation protocol

## Purpose

This protocol validates whether provider-derived address normalisation is substantively correct before any candidate is promoted to accepted geography.

It is deliberately separate from parser QA. The source-supported canonical address remains unchanged; the reviewer assesses the downstream linkage result.

## Review population

For Cosenza the curation workflow builds a deterministic 150-row sample from the complete ANNCSU validation output.

Sampling is stratified by the evidence/precision class actually presented to the user:

- `matched_civic_access` — exact ANNCSU civic access with a direct provider coordinate;
- `matched_street` — exact official street with a street-level coordinate, including deterministic street-coordinate fallback;
- `matched_without_coordinates` — exact provider normalisation without a usable coordinate pair;
- `matched_address` / `matched_coarse` if such provider classes occur;
- `foreign_matched` if present;
- `not_found`, `error` and `unprocessed` terminal classes if present.

Every observed stratum receives a minimum representation where sample size permits. Remaining slots are allocated approximately proportional to stratum population. Each row records the population size, sample size and inverse-probability sampling weight.

The sample ordering and membership are deterministic for a frozen `address_results.csv`. The review bundle also records a SHA-256 fingerprint of the sample and validation summary.

## Evidence shown to the reviewer

For every sampled address the retro Dataset Explorer displays side by side:

### Source side

- canonical/source-supported address text;
- linked legal entity name(s), where the canonical database relationship is deterministic;
- source observation date and parsed-record locator;
- direct link to the preserved original Prefecture PDF page when the physical row locator can be reconstructed.

### ANNCSU/provider side

- normalised provider label;
- official street/odonym;
- civic number when retained;
- municipality;
- declared coordinate precision;
- latitude/longitude if present;
- provider/version identifiers;
- an OpenStreetMap link for visual plausibility checking of the candidate point.

Absence of an optional source-occurrence link is not itself a provider error; it means the additional canonical-to-physical-source join was not asserted for that sample row.

## Review questions

The UI records the following dimensions independently:

1. **Overall verdict** — `Correct`, `Incorrect`, or `Uncertain / unverifiable`.
2. **Municipality** — whether the resolved municipality is correct.
3. **Street / odonym** — whether the ANNCSU street is the street represented by the source address.
4. **Civic** — whether the civic number/exponent is correct; use `N/A` when the candidate does not claim civic precision.
5. **Coordinate plausible** — whether the plotted point is substantively compatible with the claimed precision; use `N/A` where no coordinate exists.
6. **Declared precision** — whether `civic_access`, `street`, or another precision label honestly describes what the provider result supports.
7. **Notes** — concise reason for an error, uncertainty or noteworthy edge case.

## Core distinction: linkage correctness vs spatial precision

A `street` candidate must **not** be marked incorrect merely because it does not identify a doorway. Its claim is only that the street identity is correct and that the coordinate is a street-level derived point.

A `civic_access` candidate makes a stronger claim: exact civic/access linkage plus the ANNCSU coordinate published for that access. It should therefore be assessed at civic level.

Conversely, a street-level coordinate must never be reviewed or promoted as if it were address/civic precision.

## Overall verdict rule

Use:

- **Correct** when the provider linkage is correct at the precision it explicitly claims and there is no material contradictory evidence;
- **Incorrect** when municipality, street, civic/access identity or claimed precision is materially wrong;
- **Uncertain / unverifiable** when available evidence is insufficient to make a defensible binary decision.

`Uncertain` is not converted into an error or a success for the primary precision estimate.

## Weighted precision estimate

The Explorer reports a live weighted estimate among determinate (`Correct` / `Incorrect`) reviews:

```text
weighted precision = sum(weight_i * correct_i) / sum(weight_i)
```

where the denominator includes only rows with a determinate overall verdict.

The same calculation is shown separately by review stratum. During partial review these estimates are descriptive only; the frozen completed sample is the basis for any formal promotion-policy decision.

## Persistence and gold-standard export

Review choices are stored locally in the browser under a key containing the sample fingerprint. They are not silently written back to the database.

The reviewer must export the completed state as JSON or CSV. JSON export contains the sample fingerprint and all review fields and can later be re-imported into the same sample. This exported file is the candidate gold-standard artifact for versioning and subsequent benchmark use.

A review export must not be applied to a different sample fingerprint.

## Promotion policy

This protocol does not itself set a pass threshold or automatically change `candidate` to `accepted`.

Only after the Cosenza sample is substantially reviewed should the project define and test an explicit promotion rule. Any future fuzzy matching or stronger preprocessing must be benchmarked against a frozen reviewed gold sample and must demonstrate recall gain without a material loss of precision.
