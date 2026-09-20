# White List administrative-performance pilot

Status: **internal research / experimental**.

This directory isolates the methodological pilot for White List administrative-performance measures from the production archive. Nothing under `research/white_list_performance_pilot/` is loaded by `db/apply.sql`, exposed by the public site, or treated as a reviewed release.

## Objective

Test whether the canonical White List model can support defensible measures of administrative throughput and timeliness without changing source evidence or canonical facts.

The pilot is built around four outputs:

1. procedure-level spells;
2. processing-time and censoring diagnostics;
3. Prefecture-period flow measures, only where source coverage permits them;
4. Prefecture application-cohort measures.

The production archive remains the source of truth. Research code reads from it and never writes back inferred administrative facts.

## Non-negotiable analytical rules

- A source-observation date is not a decision date.
- Disappearance from an edition is not administrative removal.
- Nominal expiry is not completion of a procedure.
- A pending renewal is not loss of legal effect.
- An observed listing date may be used only as a labelled proxy where the canonical pipeline supports the chronology; it is never relabelled as an exact administrative decision date.
- Transitions observed only between editions are interval-censored.
- Procedures still open at the last usable observation are right-censored.
- Clearance rate and backlog are not calculated unless the applicant population and longitudinal observation window are sufficiently complete.
- Eligibility is assessed per metric, not once per Prefecture.
- Research outputs must carry a source/code freeze identifier.

## Pilot sequence

### Execution anchor

**Cosenza** is the first computational anchor because the canonical procedure model is already populated and eleven historical editions have been inventoried. The next substantive step is to ingest the historical editions through the existing source → semantic → canonical pipeline, then run the spell view and validate transitions.

### Phase-1 onboarding cohort

The first heterogeneous onboarding cohort is:

- Pistoia — separate HTML applicant/listed tables; applicant table exposes application date and outcome;
- Biella — separate HTML applicant/listed tables; applicant table exposes application date and outcome;
- Cagliari — separate PDF populations; applicants expose application date/status and listed records expose renewal/update information;
- Torino — separate applicant/listed sources with application dates and procedural annotations;
- Potenza — combined custom application used as a stress test for snapshot-transition logic.

These authorities are not treated as computationally ready until their observations are processed through the same canonical pipeline used by the anchor.

All other authorities remain in the expansion pool. `scripts/build_eligibility.py` evaluates the entire territorial-authority universe from the current source registry, so the pilot can expand without maintaining a separate hand-built sample.

## Files

- `config/pilot_authorities.csv` — manual pilot/onboarding signals only.
- `config/metric_definitions.yml` — versioned analytical definitions and gates.
- `scripts/build_eligibility.py` — deterministic whole-universe eligibility report.
- `sql/001_procedure_spell.sql` — experimental procedure-spell view; not part of production migrations.
- `sql/002_validation_queries.sql` — fail-closed validation checks before any aggregate is reported.
- `outputs/eligibility_baseline.csv` — frozen eligibility snapshot generated against the branch base commit.

## Promotion rule

Nothing in this directory should be promoted to `db/schema`, `src/`, `mart.*` production views, the Dataset Explorer, or public releases until:

1. the Cosenza historical reconstruction has passed row-level validation;
2. at least two different publication models replicate the same analytical semantics;
3. exact/proxy/interval/right-censored dates are distinguishable in output;
4. flow denominators have explicit applicant-population coverage gates;
5. metric definitions are frozen and independently reproducible.
