# Reggio Calabria — November 2026 source-candidate review (not an approval)

**Evidence cut-off:** 20 November 2026, protected [run 44825613270, shard 0/job 136597447361](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/44825613270), `main@9c77979a2e76036461f420a01cc1db02951d50c9`. This is a source-extraction review checkpoint for a **previously unpublished Prefettura**, not a SourceEdition, approved source binding, publication intent or release.

## Exact source identity and candidate digest

| Property | Listed | Applicants |
| --- | --- | --- |
| SourceSeries candidate | `reggio-calabria-listed` | `reggio-calabria-applicants` |
| Authority / register | `reggio-calabria` / `reggio-calabria-ordinary` | Same |
| Logical population | `listed` | `applicant` |
| Original SHA-256 (R2 readback) | `d185e63dcd0a603aec194ddc32593960cb72f183fdba120abd0d2dc6f9666b13` | `fa15cb7cbd4c17d94a05c374c2e69b073648122197aef866b7ed6ea95a969764` |
| Original bytes | 281,479 | 392,393 |
| PDF pages / one table per page | 72 / 72 | 78 / 78 |
| Numbered physical rows | 546 | 703 |
| Number-only rows | 2 (ordinals 544, 546) | 0 |
| Data-bearing candidate observations | **544** | **703** |
| Full-value candidate `records_digest` | `e78258b4a61f9e8df9e378cb8a79ec622055082cb89b4ebb80371c7621994049` | `884582c859d5d272b16084d5e3f79334229a6d02097db53e5ff0111591be9b7f` |

The two original byte hashes and sizes were verified in the existing protected R2 archive. The census checked every page, ordinal sequence, row width and table/header profile against the independently reviewed structure in PRs [#321](https://github.com/colazeta/italian-anti-mafia-whitelist/pull/321) and [#322](https://github.com/colazeta/italian-anti-mafia-whitelist/pull/322). PR [#323](https://github.com/colazeta/italian-anti-mafia-whitelist/pull/323) generated the candidate public-record projections **in memory**, without writing or exposing individual rows. Its two digests are exact identities of provisional extracted observations, **not approval digests**; they must not be copied into a finite `incremental_release_intent.json` as a substitute for source review.

## Aggregate exception register

| Source QA item | Listed | Applicants | Decision |
| --- | ---: | ---: | --- |
| Candidate source statuses | 252 `listed`; 262 `renewal_update_in_progress`; **30 `other_or_unknown`** | 701 `pending`; **2 `other_or_unknown`** | Review all nonstandard outcome expressions and the source's status meaning before binding |
| Nonstandard identifier shape | 14 | 32 | Review source cells and preserve raw values; do not infer identity or reject merely from format |
| Data field omissions | Activities 3; office 1; expiry date 13 | Activities 1; office 2 | Verify physical cell alignment and source meaning |
| Dates needing review | Expiry date 2; listing date 0 | Application date 2 | No silent correction, coercion or invented date |
| Number-only numbered rows | 2 | 0 | Verify whether numbered placeholders, not businesses; reconcile 546 numbered rows versus 544 observations |
| Header-like rows | 1 | 78 | Already counted separately in structural census |

The provisional status labels derive from the versioned extraction code's explicit heuristics and are **not administrative determinations**. A source `outcome_raw` is not a legal-effect event. The candidate does not establish the validity of the 30 + 2 unclassified outcomes, the 46 nonstandard identifier shapes, or the source's data semantics. Review evidence must be physical-source-backed, without disclosing personal data or company-level source rows in this document.

## Source edition and release gates

The two resources were discovered as attachments labelled **16 November 2026**; the protected output reports `source_reference: 2026-11-16`. That field is configured by the candidate code and **is not independent proof** of an explicit official reference date inside each PDF or its official publication page. A direct public retrieval returned HTTP 403; it does not negate the separately SHA-verified originals. Before assigning `reference_date` in a reviewed public manifest, independently establish the document date and the authority/source provenance for **each** population.

1. Inspect the SHA-pinned PDFs in the existing protected review environment for date attribution, official origin, the two listed numbered placeholders, all 32 `other_or_unknown` outcomes, date/identifier exceptions, row/sector/office alignment, and meaning of the listed `renewal_update_in_progress` category. Retain physical page/table/row locators and an aggregate, reviewable exception resolution. Do not infer an administrative transition from edition differences.
2. Only after those gates pass, reuse a validated, versioned parser family; add the two exact SourceSeries with one complete listed/applicant register, documented binding and independently checked source counts/statuses/sector mapping. Validate privacy for the existing public field contract, especially sole traders and identifiers. Preserve every original and earlier approved public observation.
3. Produce the **new** finite source-review intent against the then-current selected manifest/config, with `expansion_authorities: ["reggio-calabria"]`, exact approved counts/statuses/byte hashes/parser identifiers and full reviewed record digests. The present candidate digests may be comparison inputs, but cannot be auto-approved. Require preserved-public replay, all unrelated sources/reports unchanged, checks on the exact PR head, a single serial selector merge and the sole `Public retro portal` deployment followed by five live SHA-256 **and size** readbacks.
4. Until complete, status is **source candidate physically counted; semantic/date/privacy review required; no selector proposal**. The prior public tag remains selected. The reviewer must not treat the candidate's `2026-11-16` string or provisional digest as authority to create a SourceEdition or public release.

**Evidence separation:** The protected workflow's overall `failure` includes expected quarantines in independent stages; the Reggio census step itself succeeded. Neither successful census nor the `review_only` candidate projection verifies a new public release. The independent restore assurance under #16 also remains a separate control. No additional privilege, writer, scheduler, publisher or geography-enrichment dependency is proposed.


## Additional printed-title review gate (21 November 2026, pending protected readback)

The existing read-only archived-PDF census has a narrowly scoped, non-approving
check for the printed **population-specific title** in the upper 12% of each
page and an explicit 16 November 2026 date on that title line (or on an
immediately adjacent line explicitly labelled as an update/date). It emits
**counts only**, separately from the already verified bottom-margin date and
pagination clues. A date in a company row, an unlabelled adjacent line, a
filename, or PDF metadata does not count as title-date evidence. A missing
match is **unknown**, not evidence that a date is absent elsewhere. This
requires execution and readback against both exact archived original SHA pins;
the change alone is not a result and does not resolve date attribution,
privacy, unknown status classifications or approval. No individual source
text is written to the repository or runner logs.

## Redacted lexical triage of unclassified source outcomes (pending protected readback)

The pending source-only code change adds a **fixed-vocabulary, aggregate-only** split of the previously verified **30 listed + 2 applicant** `other_or_unknown` outcomes. It distinguishes lexical cues for adverse wording, expiry/suspension wording, procedure wording, enrolment wording, empty source outcomes and otherwise unmapped wording. Precedence makes these mutually exclusive *review queues*, **not legal-effect statuses**; actual original text, rows, names, identifiers, document locators and dates are never emitted in this summary. It fails closed unless the six category counts sum to the original physical `outcome_other` denominator for each population. Synthetic regression tests cover ambiguous overlapping terms and no leakage.

**Production result: unknown until the existing protected worker has executed this exact merged code and its SHA-pinned source readback has been reviewed.** No change is authorised to the candidate records, full-value digests, source dates, provenance, parser binding, privacy assessment, public intent or selector. This additional triage cannot establish that an adverse administrative event occurred. The independently reviewed 16 November date and the complete source-cell/sector/status/privacy checks remain open. If the worker fails at an unrelated stage, preserve both its failure and the separately observed result of this read-only step.


## Protected readback of pending diagnostic gates — 23 November 2026

[Run #45224486802, job #137867317529](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/45224486802/job/137867317529), frozen main 5911a9de47164b2315d7028098dda0137b60d58d, reverified both original identities and the exact candidate digests above. The listed PDF has authority-header, 16-Nov footer date and exact pagination jointly on **72/72** pages. Applicant authority-header evidence is **78/78** pages; no equivalent printed footer-date/pagination count is reported for that population. Neither source returned a population-specific upper-margin title or attached title-date match (0/72 and 0/78). Thus the listed date has stronger source corroboration, but neither edition reference nor provenance approval was granted and the applicant date cannot inherit the listed date.

The lexical review reconciles the 30 listed exceptions to 3 procedure-wording and 27 unmapped, and the 2 applicant exceptions to 1 procedure-wording and 1 unmapped. All remaining lexical buckets are zero for these denominators only. This does not imply the absence of adverse administrative events, and no status has been reclassified. Identifier shape diagnostics separately flag 14/32 other raw shapes and 2/5 sixteen-character shapes for privacy review. Exact row content remains private. All edition, provenance and privacy flags remain false. No publication intent or parser binding is justified yet.
