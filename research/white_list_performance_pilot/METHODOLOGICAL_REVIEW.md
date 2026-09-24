# Methodological review: what the public archive identifies

Status: experimental research, 20 September 2026. This note supersedes more permissive interpretations in the initial v0.1 pilot. It does not alter production facts or parsers.

## Three different estimands

1. **Observed pending age**: source reference date minus an unambiguous application date for a row explicitly published as pending. This is the age of the observed pending population, not the eventual duration of the procedure. It can be calculated at a single snapshot, without a complete historical inflow series. A national or prefectural total backlog requires a separate completeness assessment.
2. **Application-to-listing date-pair lag**: a diagnostic among published rows with a unique application date and a later listing date. Chronological order is necessary but insufficient to prove that both dates describe the same procedure. Until that linkage and date semantics are reviewed, this must not be described as actual processing time.
3. **Administrative processing and clearance**: require identified procedure episodes, explicit terminal outcomes, and a defined population/window. These are not automatically identified by a pair of publicly available applicant/listed files.

## Changes to the initial pilot assumptions

### Administrative intervals versus observation intervals

A pending record on date A and listed record on date B delimit a **published-state transition**. They delimit an administrative decision only if the pending record is known to reflect the administrative state at A, rather than a stale publication. Without that additional assumption/evidence, neither Turnbull estimation nor replacing B with a midpoint fixes the problem. The v0.1 SQL transition bounds must therefore not be interpreted as administrative decision bounds.

### Discovery completeness is not flow completeness

Finding both logical populations identifies publication channels, not a census of all applications and all terminal outcomes. Applications can enter and leave between editions; refusals, withdrawals and transfers may not remain published. More historical snapshots do not by themselves prove complete inflows or clearance numerators. All outcomes, opening stock, closing stock, reopenings and transfers must reconcile before a true period clearance/backlog rate is released.

The intended stock identity is:

`closing pending = opening pending + incoming + reopened + transfers in - resolved - withdrawals - transfers out + documented corrections`

Every term must use mutually exclusive, defined accounting rules. An unresolved residual is not silently absorbed into resolved cases.

### Cohorts, truncation and censoring

A snapshot of pending cases overrepresents long-lived procedures. A current list of successful applicants excludes historical unsuccessful or removed cases. Kaplan–Meier or interval-censoring estimators do not repair incomplete cohort ascertainment or informative publication loss. Applications already pending when collection begins require explicit delayed-entry handling or a separate prevalent-cohort analysis. Disappearance is loss of observation, never proof of administrative completion.

### Identity and procedure grain

Entity identifiers, source rows, sector rows and procedure episodes are different units. An entity/date/type hash is a candidate linkage key, not an official procedure identifier. Several same-day applications, sector additions, updates and renewals can otherwise be merged. The source diagnostic excludes ambiguous linkage groups rather than resolving them by row order. Exclusion denominators are exported.

### Procedure type and legal effect

Absence of a renewal annotation does not independently establish initial-registration type. Keep unknown types unknown for research. An older listing date alongside a newer application may describe an earlier registration and a later renewal. Pending renewal does not itself establish loss of legal effect. Ninety, 180 and 365 days are descriptive age thresholds, not automated findings of legal non-compliance; working days, suspensions and the legally applicable clock need separate evidence.

### Evidence classes

- `approved_parser_executed`: original bytes match the frozen approved source and the existing parser count checks pass. This validates reuse of that source boundary, not full administrative-population completeness.
- `exploratory_parse_NOT_canonicalised`: captured historical PDF passed a minimal header check and the existing parser ran. Layout compatibility, row recall, reference-date consistency and episode linkage still require independent review.
- `blocked_unapproved_bytes`: mutable source no longer matches the approved raw hash, or no raw hash is available. No administrative statistic is inferred from the new bytes.
- `capture_or_parse_failed`: no statistic; only a redacted error class is retained.

## Isolation and dissemination

The runner reads existing source configuration and parser implementations. It does not apply schema migrations, write canonical tables, update source registries, merge the PR, deploy the site or create scheduled maintenance. Source bytes and entity-level working rows stay on the temporary runner and are not uploaded by this workflow. The retained output contains only non-identifying research aggregates and source provenance.

The GitHub repository and its branch are public. A `research/` path means experimental/non-production, not confidential. Do not put company-level research data, credentials or confidential manuscript content there. This iteration has no permanent raw-evidence storage claim: temporary capture is not durable archival ingestion.

## Promotion requirements

Before publishing processing-time or flow results: validate date semantics and same-procedure linkage; review a stratified row sample against exact source pages; establish outcome and inflow ascertainment; reconcile stock/flow identity; separate initial/renewal/unknown episodes; document exclusion rates; freeze code and source hashes; and replicate across publication formats. Until then, report source diagnostics under their literal labels and leave non-identifiable metrics null.
