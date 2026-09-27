# Lodi registered-company source review — 27 September 2026

The official Lodi White List page links to a mutable registered-company Google Sheet. The CSV was fetched independently twice on 27 September; both captures contain 36,404 bytes and have SHA-256 `0cb78eec4e7c902a9ec9e6fa3b64ef52c276a2de32cd86cba3e59cf68775d945`. The applicant tab remains byte-identical to its approved SHA-256 `c200e90a0410ba23fddee9d3ad0a5ac1532fec8dedfe0ec983eb2e94d0601a16`.

The registered-company sheet still has 324 physical rows, seven columns each, 291 statutory-section memberships and 169 grouped observations. The strict parser verifies the same section counts and grouping distribution. Comparison with the previously published 169 Lodi registered-company records shows one changed observation, at source row 299:

| Field | Previously published | Current official CSV |
| --- | --- | --- |
| Company | SOVEA S.r.l., identifier `04785630965` | Same |
| Section | X | X |
| Listed date | 07/04/2025 | 25/09/2026 |
| Expiry date | 07/04/2026 | 25/09/2027 |
| Update marker | `in aggiornamento` | Blank |

The source-row split is now 252 listed and 39 explicitly in renewal/update; after conservative grouping it is 145 listed and 24 in renewal/update. No observations were added or removed. The date of this review is an observation boundary, not an inferred publication date. A blank update marker is represented as `listed` according to the existing parser semantics; it is not an independent legal determination of validity.

The current capture is pinned in `data/publication/multi_prefecture_pilot.json` and in parser version 6. Any subsequent sheet change must trigger another review rather than automatic acceptance.
