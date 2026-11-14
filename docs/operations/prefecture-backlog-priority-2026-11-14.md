# White List publication-gap priorities — evidence snapshot, 14 November 2026

**Purpose:** rank the 106 Prefecture robots by archived, dated White List document candidates later than the corresponding source-series edition in the selected public release. This is an operational triage queue **not** a claim that documents are approved, new firms were found or all interim editions must be published.

**Snapshot provenance**
- Robot state: `robot-state:state.json`, Git blob `8274fb15af3a58c7ef32acad57bf0a488acd69c2`; latest checked authority at approximately 11:51 UTC (12:51 Europe/Rome) on 14 November 2026.
- Published baseline: `data/monitoring/national_coverage.json`, selected release `public-data-43524455108-1`, pinned `registry.json` SHA-256 `e235c2bae950cd85ec4f3c6b477c3ebba0a05ea745430142ce2020d0da843226`; 74 authorities with selected published sources.
- Method: the pure `robotPublicationGap()` function in `public-site/robots.js`. Compare by associated source, population and date where known; require acquired-byte evidence; exclude published digests and undated/ambiguous documents from the numeric delta.

## National triage overview

| Measure | Snapshot |
| --- | ---: |
| Prefectures monitored | 106 |
| Prefectures with selected public baseline | 74 |
| Prefectures with no published baseline | 32 |
| Prefectures with positive documented delta | 30 |
| Dated subsequent document candidates captured | 278 |
| Prefectures with published baseline and no comparable later candidate | 44 |
| Documents requiring separate review due to unknown/ambiguous comparison | 790 |

A zero is not a certificate of freshness. The 32 without a published baseline are **not** zero-backlog authorities: they need their own intake/approval queue. The 790 uncertain document records are a separate source-qualification queue, not an addition to the 278.

## Top evidence-backed deltas

| Prefecture | Latest selected published source date | Candidate documents after baseline | Latest candidate date identifiable | Working format of recent candidates |
| --- | --- | ---: | --- | --- |
| Trento | 2026-09-11 | 24 | 2026-11-11 | PDF (listed and applicants) |
| Chieti | 2026-09-18 | 24 | 2026-11-06 | DOC (listed and applicants) |
| Bolzano/Bozen | 2026-09-11 | 18 | 2026-11-13 | DOCX (listed and applicants) |
| Caltanissetta | 2026-09-09 | 16 | 2026-11-10 | PDF (listed and applicants) |
| Messina | 2026-09-11 | 16 | 2026-11-13 | PDF (listed and applicants) |
| Prato | 2026-09-21 | 16 | 2026-11-11 | XLSX listed; DOC applicants |
| Brescia | 2026-09-10 | 14 | 2026-11-02 | XLSX (listed and applicants) |
| Lecce | 2026-09-09 | 14 | 2026-11-11 | PDF (sectors and applicants) |
| Agrigento | 2026-09-04 | 12 | 2026-11-13 | PDF (listed and applicants) |
| Cagliari | 2026-09-06 | 12 | 2026-11-08 | PDF (listed and applicants) |

The ten rows above account for **166/278 (59.7%)** of the dated candidate documents, but do not prove 166 publication operations are necessary. Historical intermediate versions could be retained as audit evidence while the latest correctly parsed and approved versions replace current published source editions.

## Processing order and gates

1. **Initial validation wave:** inspect Trento and Chieti (24 each), then Bolzano/Bozen (18), Caltanissetta, Messina and Prato (16 each). Within a tie, prefer parser-compatible current series and complete source attestations; DOC/DOCX formats can require a different pipeline from PDF/XLSX.
2. **For each Prefecture:** inventory the most recent candidate in each distinct register and population; identify whether the website's declared date really describes that file. Check source URL, SHA-256 and the archived bytes. Distinguish historical intermediate editions from distinct registers, avoiding false double-counting.
3. **Extract and validate privately:** parse the latest approved source version for each series, compare schema and row semantics, quarantine mismatches, and validate source date, included statuses and matching firms before requesting publication approval. A reviewed parser for the older source does **not** automatically approve new versions.
4. **Publish only after independent approval:** promote an exact digest-pinned release, with source-specific decisions; keep unchanged Prefectures byte-for-byte unchanged, update national coverage, verify live assets. Never use a robot count to bypass source, schema, release or provenance gates.
5. **Recompute ranking dynamically:** the public Robot page now computes the national dashboard from the current `robot-state` JSON and the selected public-release directory. The snapshot table above is historical evidence; do not manually maintain it as live truth.

## Interpreting the metrics

- **Document delta:** number of distinct acquired date-bearing candidate documents later than selected source-series reference dates. It is an evidence lower bound and can include historical intermediates.
- **Current edition gap:** number of independently identified source series whose *latest validated* version remains newer than the selected public version. This needs a private validation decision and is **not currently certified by robot metadata alone**.
- **Unresolved evidence:** undated, ambiguous, unbound or otherwise non-comparable documents. These remain visible but do not inflate the numerical document delta.
- **No published baseline:** dedicated intake workstream, not zero backlog.

Do not infer a ready-to-publish count, real-time prefecture freshness, or newly listed firm counts from this report.
