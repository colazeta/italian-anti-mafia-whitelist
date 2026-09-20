# White List administrative-performance research pilot

Status: **experimental research; v0.4 source-diagnostic checkpoint executed**.

Start with [the completed results](outputs/checkpoint_0_4/RESULTS.md) and the machine-readable tables in `outputs/checkpoint_0_4/`. The original v0.1 planning files remain historical records, not current eligibility or results.

## Completed checkpoint

The research-only run `35531034683` executed code commit `3ad0e832599adc5eba793cb5268ad888d7327d02` on 20 September 2026. It requested 39 sources for 20 authorities; 35 approved sources yielded 31,795 observations for 18 authorities. Four HTML sources for Biella and Taranto failed the existing byte-approval boundary and were not silently accepted. The Cosenza research history expanded from 11 inventoried dates to 19 acquired and parsed editions, spanning 24 June 2024 to 15 September 2026, with 22,969 repeated source observations.

These are not counts of distinct firms or administrative procedures. The historical processing was research-only, not canonical ingestion. Modena's ordinary and post-earthquake registers remain separate.

## What is supported

- Published-pending age distributions, with explicit date coverage and missing-age bounds.
- Historical source-state counts and conservative longitudinal linkages.
- Conditional application-to-listing lag diagnostics.
- First-observed-pending cohorts, with an explicit unobserved-final-state category.
- Per-authority/register discovery and analytical evidence gates.

## What is not yet identified

True administrative processing-time distributions, clearance rates, total administrative backlog rates and administrative survival curves are not reported. No missing quantity is set to zero. The observed histories do not establish complete incoming applications, all administrative outcomes or reliable decision dates for every episode.

The methodological review corrected the original v0.1 assumptions. A published pending-to-listed transition is not automatically an administrative decision interval: the pending publication may be stale. A last pending publication is not automatically evidence of independent right-censoring. Ordered application/listing dates still require same-procedure evidence. See [METHODOLOGICAL_REVIEW.md](METHODOLOGICAL_REVIEW.md).

The original `sql/001_procedure_spell.sql` recipe is retired and deliberately raises an exception. It has not been deployed. `sql/002_validation_queries.sql` is a legacy design artefact, not an executed validation suite for the v0.4 results.

## Execution and reproducibility

The executable entrypoint is:

```sh
python research/white_list_performance_pilot/scripts/run_completion.py --output-dir artifacts/research-performance-aggregate
```

Run it from the pinned repository after installing the existing publication dependencies and acquisition utilities. `run_completion.py` reuses `run_followup.py`, `run_source_pilot.py` and production parser implementations rather than changing them. Source changes fail closed against existing approvals. Cosenza historical parsing is explicitly exploratory and requires separate row-level review before canonical promotion.

The research workflow `.github/workflows/research-performance-pilot.yml` runs only on the research branch, has read-only repository permissions and checks that tracked inputs remain unchanged. It has no recurring schedule. Its aggregate artefact includes the executed code, dependency freeze, source URLs and hashes, tests and full non-identifying diagnostic output.

The delivered offline bundle additionally contains an Italian six-page report, an eight-sheet workbook, CSVs, an executed notebook, a base-R reader and numerical validation. Aggregate tables can be rebuilt from the frozen diagnostic JSON. Recomputing medians independently from original company rows still requires reacquisition of the original bytes; raw documents are not retained in this checkpoint.

## Safety and dissemination

Research code does not write canonical facts, alter production parsers, change production publication configuration, merge to main or deploy the public site. The repository and branch are public: a research directory is not a confidentiality boundary. Only code, methodology, provenance and non-identifying aggregate results are retained. Company names, identifiers, addresses, working row-level extracts and original source documents are excluded from the result package.

## Promotion requirements

Promotion remains a separate decision. It requires independently checked historical row coverage, verified administrative episode identities and date semantics, complete inflow/outcome evidence for flow rates, replication across publication models, reproducible uncertainty handling and a documented release review. More source snapshots alone do not satisfy those conditions.
