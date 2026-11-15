# Taranto, 6 November 2026 — protected source-readiness evidence (not publication approval)

## Evidence boundary

Source-level acceptance was exercised by the **existing** protected `Transform reviewed captures into private observations` workflow, run [43757038299](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/43757038299), shard 1/job 132943330432, on `main@5761596b3f272ac0ec1ed1ff85e1883029c57628` on **15 November 2026**. The archived inputs were fetched from the established private CaptureCatalogue, with complete original SHA-256 and immutable capture provenance verified; there was **no live refetch, source publication or administrative-edition attribution**. The official HTML text declares an explicit update of **6 November 2026**, independently validated against capture time. The archive's `source_capture.declared_reference_date` is still NULL; this is not a contradictory administrative event date. The public selected baseline for these series is **7 September 2026**.

| SourceSeries | Exact archived original SHA-256 | Original bytes | Parser (revision) | Independent physical census / public observations | Exact source statuses |
| --- | --- | ---: | --- | ---: | --- |
| `taranto-listed` | `013cc91b1a62e353e77ab0e773299b6c0ed25c930d9d26d9bd62ec4613ed9396` | 150,383 | `taranto_html_listed@1` | 383 / 383 | 183 `listed`; 200 `renewal_update_in_progress` |
| `taranto-applicants` | `c873e011a424e278f91a1bf80abec69282fc5ea53d310aa7118e49693c81c970` | 109,175 | `taranto_html_applicants@1` | 226 / 226 | 226 `pending` |

Both series map to `taranto-ordinary` and jointly satisfy the two logical populations. The independent census inspects the complete physical evidence table, including nonempty rows that the parser could otherwise skip; it rejects unreviewed pre-header content, header drift, inconsistent row widths and incomplete observations. It was run against the above **actual archived originals**, not only synthetic fixtures. Physical counts equal parser diagnostics and public-contract record counts; `dropped_date_rows=0` in the tested extraction.

Source semantic SHA-256, calculated by the established parser contract: `80fd32841490c1c72845fb394c8fab796d95b3e6f481a51951824f0d0c29a19b` (listed) and `1b51bb0dda7e0e001435351e07ce60b11d982afd2cf5cdb07373034da2b2e033` (applicants). This semantic digest is **not** the full-public-record digest required by `incremental_release_intent.json`.

## Source quality / limits

The listed source has **377/383** structured identifiers, six raw-only identifiers and eight malformed **source row dates** retained without correction. The applicant source has **225/226** structured identifiers, one raw-only identifier and zero malformed row dates. Both have zero blank identifier rows in the protected aggregate QA. These counts concern documentary occurrences, **not distinct businesses**. The literal status lexemes and sector fields still require finite review against the actual frozen source and the versioned public contract, particularly whether the eight malformed row dates have been preserved without creating a false event or status. Absence between editions is never removal/interdiction.

The old public population was 388 listed-source plus 212 applicant-source observations (600); the observed candidate population is 383 plus 226 (609): **net +9 source presences**, subject to unchanged-scope comparison. The 60-day gap (7 September to 6 November) is a *potential freshness improvement*, not a published change.

## Acceptance still to be completed

1. Retain a complete, closed and reproducible full-public-record SHA-256 digest for each source (the exact `publication_handoff.records_digest` over every value, parser lineage and original identity). The companion change to protected readiness reporting emits these aggregate digests and safe blank-field counts, with regression tests that prevent raw cell leakage.
2. Complete and document independent review of identity, administrative statuses, source date meaning, sectors, malformed row values, privacy and source/public-record digests. Bind the exact two pins and versioned parsers in the reviewed manifest only after this review.
3. Commit a **new finite intent** bound to the current selected Como baseline `public-data-43736522316-1` and the exact updated source config. The old Como intent cannot authorise Taranto.
4. Let the existing `Public registry candidate` perform all five durable-asset checks, outside-scope record/report comparison and selector proposal. Only then review CI on the exact proposed head, merge serially under the existing mandate and verify all five live asset SHA-256/size values through the sole `Public retro portal`.

The document is an aggregate **source-readiness dossier**. It is **not** a SourceEdition, a semantic/canonical projection, an approved publication intent or an authorisation to alter the live selector. It neither introduces storage/credentials/privileges nor weakens the quarantine of unrelated sources.
