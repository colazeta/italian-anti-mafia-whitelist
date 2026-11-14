# Robot-to-publication gap triage — 14 November 2026

## Evidence boundary

- Snapshot: public robot-state `state.json` blob `8274fb15af3a58c7ef32acad57bf0a488acd69c2`, 106 authorities, last checks 11:35–11:53 UTC on 14 November 2026.
- Public selected release: `public-data-43524455108-1`, pinned registry digest `e235c2bae950cd85ec4f3c6b477c3ebba0a05ea745430142ce2020d0da843226`.
- Publication-source ledger: `data/monitoring/national_coverage.json` blob `dbaf9417b26016c8db8f3508f369c96bad483868`, 74 authorities with a comparable selected edition, 32 without.
- Formula: `robotPublicationGap` in `public-site/robots.js`. This returns **archived, date-identifiable official-document candidates detected later than each applicable selected public SourceSeries**, not approved new editions or a count of records/companies. Same-source/date duplicates and already published SHA identities are excluded. Missing dates, source ambiguity and unacquired links are separate review items. One selected published source may have many historical versions.
- Count at this snapshot: **278 candidate document versions in 30/74 comparable Prefectures**; **44/74 with no date-identifiable later candidates** (not a guarantee of current completeness); **32/106 with no comparable public edition**; **790 additional unclassified document/attachment clues**, including 201 in Cosenza's partial run. The latter are **not** 790 confirmed relevant newer lists. Four robot checks were partial (Campobasso, Cosenza, Pistoia, Frosinone).
- Top ten contain **166/278 (59.7%)** of dated archived candidates.
- Date within the filename can identify a candidate but cannot itself certify the administration's publication date, a lawful event, a parser or public approval.

## Ranked queue (frozen snapshot, not a live national completeness claim)

| Rank | Prefettura | Candidate versions | Latest published reference | Latest candidate filename date | Unclassified clues | Partial check |
|---:|---|---:|---|---|---:|---|
| 1 | Trento | 24 | 2026-09-11 | 2026-11-11 | 1 | No |
| 2 | Chieti | 24 | 2026-09-18 | 2026-11-06 | 0 | No |
| 3 | Bolzano/Bozen | 18 | 2026-09-11 | 2026-11-13 | 0 | No |
| 4 | Caltanissetta | 16 | 2026-09-09 | 2026-11-10 | 0 | No |
| 5 | Messina | 16 | 2026-09-11 | 2026-11-13 | 0 | No |
| 6 | Prato | 16 | 2026-09-21 | 2026-11-11 | 0 | No |
| 7 | Brescia | 14 | 2026-09-10 | 2026-11-02 | 0 | No |
| 8 | Lecce | 14 | 2026-09-09 | 2026-11-11 | 0 | No |
| 9 | Agrigento | 12 | 2026-09-04 | 2026-11-13 | 2 | No |
| 10 | Cagliari | 12 | 2026-09-06 | 2026-11-08 | 0 | No |
| 11 | Napoli | 11 | 2026-09-13 | 2026-11-13 | 9 | No |
| 12 | Bari | 10 | 2026-08-31 | 2026-11-13 | 0 | No |
| 13 | Campobasso | 10 | 2026-08-11 | 2026-11-04 | 0 | Yes |
| 14 | Belluno | 9 | 2026-09-02 | 2026-11-10 | 1 | No |
| 15 | Trapani | 9 | 2026-09-11 | 2026-10-30 | 0 | No |
| 16 | Avellino | 8 | 2026-09-01 | 2026-10-29 | 8 | No |
| 17 | Pescara | 8 | 2026-09-16 | 2026-11-04 | 7 | No |
| 18 | Foggia | 8 | 2026-09-10 | 2026-11-06 | 3 | No |
| 19 | Firenze | 7 | 2026-09-09 | 2026-11-12 | 0 | No |
| 20 | Pesaro e Urbino | 6 | 2026-08-31 | 2026-11-13 | 0 | No |
| 21 | Caserta | 4 | 2026-08-31 | 2026-11-10 | 4 | No |
| 22 | Ancona | 4 | 2026-09-07 | 2026-10-30 | 3 | No |
| 23 | Genova | 4 | 2026-09-10 | 2026-11-12 | 2 | No |
| 24 | Benevento | 4 | 2026-08-31 | 2026-10-28 | 0 | No |
| 25 | Cosenza | 2 | 2026-08-03 | 2026-10-13 | 201 | Yes |
| 26 | Pistoia | 2 | 2026-08-21 | 2026-10-21 | 6 | Yes |
| 27 | Parma | 2 | 2026-09-05 | 2026-10-19 | 2 | No |
| 28 | Catania | 2 | 2026-11-06 | 2026-11-13 | 0 | No |
| 29 | Forlì-Cesena | 1 | 2026-09-11 | 2026-11-09 | 1 | No |
| 30 | Lucca | 1 | 2026-09-11 | 2026-10-22 | 1 | No |

## Operational allocation

**Lane A — freshness, as few reviewed decisions as possible.** Use the existing immutable evidence and source-bound parser workflows to qualify the **most recent** listed and applicant candidate for the highest-gap Prefectures first, then compare all non-target records to the selected live release. Trento/Chieti are tied by count; Chieti DOC parser family must not be assumed equivalent to Trento PDF. Prefer readiness (source identity, actual byte readback, known parser family, zero unresolved field/row QA, controlled release scope), not raw candidate volume alone. Existing approved current Catania/Perugia/Alessandria remain unchanged. Catania 13 November already has its own documented parser diagnostic lane (#225): do not duplicate it.

**Lane B — historical versions.** Preserve all 278 candidate references in a separate immutable historical queue after exact source/date/content checks, then process bounded, idempotent batches. Newer editions do not imply that all intervening versions must be served as independent live releases. Require explicit identity and version sequence; do not infer deleted or revoked companies from successive snapshots.

**Lane C — coverage and uncertainty.** Qualify 32 authorities with no released source separately; no numeric publication gap is available for them. Inspect large unclassified pools by real source role and register/population (Cosenza 201 is a notable **classification issue**, not 201 confirmed new editions). Partial robots must be rerun through existing workflows without creating a duplicate crawler or bypassing their review gates.

## Next verifiable deliverable

Within the existing serialised publication workflow, choose a source-bounded candidate from Lane A after preflight for active workers/PRs, pin original bytes and parser version, check document date, listed/applicant populations, layout/rows, status/sector mapping, privacy, and readback against the selected snapshot. Save a *reviewable non-live* candidate or an exact reason for quarantine. Only publish through the approved sole publisher and only after required acceptance/approval; the current public selector must never be replaced based solely on a filename-date or backlog count.

The Robot UI ranks by candidate count by default and permits independent views of unclassified clues, non-comparable authorities and alphabetical order. Rankings recompute from currently loaded robot observations; this note remains a dated evidence snapshot.
