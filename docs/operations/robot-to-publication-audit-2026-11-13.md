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
