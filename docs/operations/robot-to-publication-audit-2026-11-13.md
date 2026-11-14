# Robot-to-publication audit — 13 November 2026

## Scope and authoritative checks

This review distinguishes **source monitoring**, **immutable capture**, **private interpretation**, **edition qualification**, and **public release selection**. The Prefecture robot is not a publication robot. A successful check or a changed HTML page does not establish a new White List edition.

Verified components:
- National robot workflow: [Prefecture robots](https://github.com/colazeta/italian-anti-mafia-whitelist/blob/main/.github/workflows/prefecture-robots.yml), scheduled by the checked revision daily at `04:17 UTC`; each authority can also be dispatched individually. Captures are stored in the protected archive, while the public robot-state branch contains check metadata.
- Private transform: [transform-reviewed-captures.yml](https://github.com/colazeta/italian-anti-mafia-whitelist/blob/main/.github/workflows/transform-reviewed-captures.yml); executes on eligible completed scheduled/manual robot runs, but **not** a robot workflow started by a code push. New source bytes are interpreted under frozen code and protected DB/archive access. This is not public approval.
- Public publication: [public_snapshot.json](https://github.com/colazeta/italian-anti-mafia-whitelist/blob/main/data/publication/public_snapshot.json) pins the selected immutable release. [Public retro portal](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/workflows/public-pages.yml) verifies and deploys precisely the pinned derivative.

## Verified snapshot and meaning of the denominators

The robot-state branch, as read after [robot run 43496640775](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/43496640775), contained:

| Check | Count | Interpretation |
| --- | ---: | --- |
| Authority robots | 106 | National monitoring universe |
| Authority robots with a check result | 106 | Check attempt, not published content |
| Robot status `changed` | 100 | May reflect HTML changes, not an updated White List |
| Robot status `partial` | 5 | Campobasso, Cosenza, Pistoia, Varese, Ascoli Piceno |
| Robot status `unchanged` | 1 | No change detected in that attempt |
| Mapping and parser profile reviewed | 74 | Capability flag, not guaranteed compatibility with future files |
| Mapping/profile not reviewed | 32 | Requires source qualification |
| Authorities with a change to an already associated source URL in that run | 5 | Stronger, still not evidence of an administratively new edition |
| Newly discovered, filename-filtered candidate-document URLs in that run | 28 across 12 authorities | Triage candidates only; not confirmed updated editions |

There were 196 queued URLs in the five partial checks (146 Cosenza and 50 Campobasso). The public dashboard's “100 variations” should never be treated as 100 newly published editions.

The heuristic filename triage must exclude unrelated administrative attachments (for example, seizure forms), and every candidate must be matched to the proper listed/applicant register and a defensible source reference date. It is not a substitute for source inspection.

## Concrete outstanding source examples

**Catania — 13 November 2026.** The robot archived two new official XLSX URLs, currently marked `candidate` rather than associated approved sources:

- Listed: [white-list-iscritti-aggiornato-13-novembre-2026.xlsx](https://prefettura.interno.gov.it/sites/default/files/18/2026-11/white-list-iscritti-aggiornato-13-novembre-2026.xlsx), SHA-256 `90bbbc4af8542ee9c2f15368a4adc1c0916f6277867702fbb72f4d1d23831a11`.
- Applicants: [white-list-richiedenti-aggiornato-13-novembre-2026.xlsx](https://prefettura.interno.gov.it/sites/default/files/18/2026-11/white-list-richiedenti-aggiornato-13-novembre-2026.xlsx), SHA-256 `65c630bc4b12741f0a3848a73efb104a61ef8fe7cf41d0c65f69d44c8f900033`.

These must pass **two distinct** strict schema/source-row QA checks, preserve blank and anomalous source cells, and reconcile against the [approved 6 November Catania edition](../sources/catania-publication-review-2026-11-06.md). Do not copy the earlier source reference date or implicitly approve a new edition.

**Perugia.** The robot has archived candidate listed/applicant PDF resources from 3 and 5 November, but its last run reported only a landing-page change. A changed publication layout is a parser-compatibility question, not an argument to repurpose prior-edition extractors without evidence.

**Other candidates.** The last run surfaced filename-filtered new document candidates at Arezzo, Bari, Pesaro e Urbino, Vibo Valentia, Bolzano-Bozen, Palermo, Siracusa, Agrigento, Bergamo, Pordenone and Teramo. Some candidate names are ambiguous; classification must be document-specific before any parser runs.

## Private interpretation outcome and stop reasons

The [13 November scheduled downstream run 43426686021](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/43426686021) processed four shards. Its closed aggregate logs reported:

| Outcome | Count |
| --- | ---: |
| Changed reviewed inputs evaluated | 12 |
| New private interpretations with database readback | 7 |
| Reused private interpretations with database readback | 2 |
| Quarantined inputs | 3 |
| Public promotions | 0 |

Two shards returned failure specifically because nonzero quarantine outcomes cause `auto_transform.main()` to exit 1. That is the intended fail-closed contract, not evidence that all private interpretation failed. Retain quarantine receipts and inspect the protected source-level reports for each source and reason. Do **not** turn parser incompatibility, missing edition review or source anomalies into an unconditional success.

The subsequent [robot run 43496640775](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/43496640775) was a push-triggered run; its downstream transform [43499509706](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/43499509706) was correctly **skipped** under the current trust/event condition. No downstream interpretation of the newly discovered 13 November Catania attachments is established by that push-triggered run.

## Next acceptance criteria

1. **Candidate triage:** reliably identify current listed/applicant source documents, distinguish new file from changed landing page, and filter unrelated administrative attachments.
2. **Schema QA and provenance:** exact archived SHA-256 readback, parser compatibility, source-specific row/sector/date checks, explicit quarantines and no fabricated status or reference date.
3. **Private outcome tracking:** publish aggregate stage counts and quarantine classes without exposing original files, rows, private credentials or protected database locations.
4. **Approved edition selection:** compare new candidate outputs with currently pinned publication, require a recorded independent release decision, validate exact register coverage and preserve other authorities byte-for-byte where appropriate.
5. **Public dashboard:** show separate `last checked`, `last archived candidate`, `last privately interpreted` only when independently attested, and `last approved public edition`; otherwise show “not verified”.
6. **Geographic enrichment:** never use optional geocoding as a publication gate; preserve literal source addresses.

This audit does not itself promote a release, rewrite the protected archive or certify the present status of an individual firm.


## Robot filename/date display (14 November 2026)

The public Robot table now links the selected identifiable document filename instead of presenting only a date or "Non identificabile". It recognises strictly validated numeric dates and written Italian month names **in the filename itself**, for example elenco-iscritte-4-settembre-2026.pdf. A directory component such as /2026-11/ is never treated as the document's date.

If no filename date is recoverable, the view still shows the original filename and link; the earliest preserved discovery/capture observation is displayed as **prima rilevazione**, explicitly not an official publication date. Selection prefers a file with an unambiguous filename date, then preserved first-observation chronology, then technical HTTP metadata, and finally stable URL ordering. An undated document might have been published later than the selected dated document. The detail history retains all observed file links for review.

This is a monitoring presentation correction, not a new official reference date, SourceEdition approval, parser validation or public release promotion. The selected published-company edition is separately labelled. A website-declared publication date would require a source-bound observation with explicit date semantics rather than substitution of Last-Modified, first-seen timestamps or archived capture time.

Regression coverage: tests/robot_documents.test.cjs, executed as part of the public-portal Python test suite.


## Per-Prefecture public-edition baseline and detected subsequent documents (14 November 2026)

The Robot table now includes **Ultima edizione pubblicata** and **Documenti successivi rilevati**. The first comes only from the source reference dates in the exact selected public snapshot: data/monitoring/national_coverage.json is bound by release tag and registry SHA-256 to data/publication/public_snapshot.json. The minimal source identity (source key, register, population, reference date, SHA-256) is projected into the generated public data/robots.json directory; no company data or private candidate interpretation is exposed.

A subsequent document is a **detected publication candidate**, not a confirmed new edition or a parser-approved output. The counter compares an unambiguous date in each discovered official document filename with the latest *relevant published source-series date*; if a unique population/source cannot be identified it requires a date later than all released sources for the authority. A resource already having the selected published SHA-256 is never counted as outstanding. Duplicate captures of the same URL and duplicate links to an evident same-source/date candidate do not inflate the count. When multiple independent register/source-series identities are positively known, they remain separate. Same-date changed files, undated documents and ambiguous intermediate dates are separately flagged for examination and never silently counted as later official editions.

When no authority edition has been published, when the robot report is missing, or when the published directory and the selected snapshot disagree, no numeric backlog is asserted. Partial robot checks display a **lower bound** on the detected candidate documents, not a completed total. A displayed zero means **no identifiable later candidate in the available observations**, not that the Prefecture has no newer official publications. The full filename, link, scope/date evidence and acquisition indication remain available in the per-robot detail. No automatic public promotion follows from this comparison.
