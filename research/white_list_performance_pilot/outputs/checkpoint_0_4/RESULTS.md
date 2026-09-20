# White List source-diagnostic pilot: completed checkpoint v0.4

Experimental research results, 20 September 2026. This is not a production release or an administrative-performance ranking.

## Execution and scope

Research run: https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/35531034683

Execution commit: `3ad0e832599adc5eba793cb5268ad888d7327d02`. The research job completed successfully, including source checks, aggregate-only artefact audit and unchanged-input checks. The general static/database CI at run `35531034558` also completed successfully for this execution commit.

| Quantity | Result |
|---|---:|
| Authorities requested | 20 |
| Current sources requested | 39 |
| Approved current sources successfully parsed | 35 |
| Authorities represented by approved current results | 18 |
| Current source observations | 31,795 |
| Cosenza historical editions acquired and research-parsed | 19 |
| Repeated historical source observations | 22,969 |

Counts are source observations, not distinct firms or administrative procedures. Do not add current and historical counts to claim a population. Modena contributes separate ordinary and post-earthquake registers. Biella and Taranto each have two sources blocked by changed bytes; blocked is neither missing publication nor zero activity.

The historical dates span 24 June 2024 to 15 September 2026. Eight additional dates were discovered beyond the original 11-date inventory. The 9 September 2024 legacy edition was recovered through a positively discovered current official link. None of the 19 histories had identical bytes assigned to different reference dates. Historical results remain exploratory and were not written into the canonical database.

## Published-pending age

`pending_age.csv` contains 19 source/register series for the 18 included authorities. Age is the reference date minus an unambiguous application date, conditional on a row being published with pending status. It is not eventual processing time. Current reference dates come from the frozen source configuration, not from the retrieval clock; they are not all independently audited document-heading dates.

Selected numerical results, without a performance ordering:

| Authority/source | Reference | Published pending | Age-assessable | Median days | More than 90 days, dated subset |
|---|---|---:|---:|---:|---:|
| Brescia | 2026-09-10 | 1,263 | 422 | 533 | 367/422 |
| Cagliari | 2026-09-06 | 51 | 51 | 60 | 14/51 |
| Cosenza, approved current source | 2026-08-03 | 657 | 656 | 555.5 | 599/656 |
| Milano | 2026-09-18 | 1,147 | 1,147 | 476 | 965/1,147 |
| Modena, ordinary | 2026-09-16 | 502 | 502 | 414.5 | 493/502 |
| Napoli | 2026-09-13 | 2,530 | 2,529 | 592 | 2,391/2,529 |
| Parma | 2026-09-05 | 235 | 235 | 187 | 192/235 |
| Pistoia | 2026-08-21 | 45 | 45 | 163 | 32/45 |
| Roma | 2026-09-14 | 2,256 | 2,233 | 922 | 2,154/2,233 |
| Torino | 2026-09-11 | 162 | 162 | 101 | 94/162 |

Different publication practices, source dates, procedure mixes and missingness prevent a direct efficiency ranking. Ninety days is a descriptive age threshold here, not a finding of unlawful delay.

### Missing dates materially change interpretation

Brescia has age information for 422 of 1,263 published-pending rows: 33.4%. Of those 422, 367 exceed 90 days. Without assuming anything about the 841 undated rows, the share exceeding 90 days among all 1,263 rows is bounded by 29.1% and 95.6%. These are worst-case missing-age identification bounds, not confidence intervals. The observed-subset median of 533 days cannot be represented as the median for all pending applications.

Selection into conservative longitudinal linkage also matters. Roma's median is 922 days among 2,233 age-assessable source rows, but 780 days among the 2,027 rows retained by the conservative linkage filter. The 142-day difference is a selection diagnostic, not a change in performance.

An applicant publication is not necessarily a pending-only publication. Perugia has 1,213 applicant-source observations but only 176 classified as pending in the executed parser output. Status semantics must be retained rather than treating the file title as a denominator.

## Cosenza: latest historical observation

At the exploratory 15 September 2026 edition, 1,354 source observations include 653 rows published as pending. Of these, 652 have an assessable application date. Their median age is 598.5 days; P25 is 306, P75 is 1,351 and P90 is 2,378.8 days. There are 606/652 (92.9%) above 90 days and 446/652 (68.4%) above 365 days.

This newer research edition does not replace the approved 3 August source in production. See `cosenza_history.csv` for all 19 dates and frozen source hashes. Changing composition and historical parsing differences must be considered when reading the series; it is not a causal trend estimate.

## Selected application-to-listing lags

There are 369 qualifying conservative source linkages with a prior pending publication, a consistent unique application date and a later listing date inside the observed publication gap, without a prior renewal annotation. Two additional candidate transitions were excluded for missing or invalid listing dates.

The application-to-listing lag has median 246 days, P25 108, P75 574 and P90 1,107.2. Counts above 90, 180 and 365 days are 290, 223 and 143. The median gap between last pending and first listed publication is 41 days; that gap is not itself an administrative decision interval.

These lags are conditional on observable, successfully linked cases. They do not establish an unbiased processing-time distribution for all applications, nor independently verified administrative procedure identities. No Kaplan-Meier or Turnbull administrative survival curve is reported.

## First-observed-pending cohorts

Across the history there are 931 conservative entity/name/identifier/application-date keys first observed as pending. At the final edition, the categories partition into 467 pending, 193 listed, one renewal and 270 not observed with the same linkage key. Separately, 371 were ever observed later as listed; this overlaps the final-state categories and must not be added to them.

The first cohort, observed on 24 June 2024, contains 377 keys. After 813 calendar days, on 15 September 2026, 166 are still published as pending, 40 are published as listed and 171 are not observed with the same key. The corresponding shares are 44.0%, 10.6% and 45.4%. A key can be lost because its name/date/identifier representation changes; absence is not proof of rejection, withdrawal, cancellation or resolution.

These are observation-entry cohorts, including prevalent cases, not complete incoming-application cohorts. See `observed_pending_cohorts.csv` for the 19 groups.

## Validation and withheld estimands

The execution passed 24 named research regression tests and additional entrypoint self-tests. A separate offline check passed 345 aggregate assertion groups covering counts, partitions, quantiles, denominators, hash approval and null estimands. This is numerical and contract validation, not an independent historical row-recall audit.

True administrative processing-time distributions, flow clearance rates, total administrative backlog rates and administrative survival estimates remain unreported/null. Snapshot availability alone does not establish complete inflows and all closures, or current administrative status at each source date. The original v0.1 procedure-spell SQL is retired fail-closed rather than retained as an executable but misleading metric recipe.

## Preserved outputs and boundary

This directory preserves compact numerical tables and provenance in the research branch. The delivered offline package adds the full non-identifying diagnostic JSON, executed notebook, CSV exports, workbook, Italian report and file hashes. Rebuilding derived aggregate tables is possible from the frozen JSON; independently recomputing raw-row medians requires the same source bytes, which were temporary on the runner and are not archived here.

The repository is public: experimental/research status does not imply confidentiality. No company-level rows, names, identifiers, addresses or raw source documents are committed. Production code, canonical data, public-site deployment and main remain unchanged by this checkpoint. PR #150 remains draft.
