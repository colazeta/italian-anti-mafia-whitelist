# Strict historical Lodi parser qualification in the protected read-only lane

## Purpose and exact scope

The ordinary protected \`Transform reviewed captures into private observations\`
workflow performs a **read-only, source-only parser compatibility check** for two
historical Lodi White List original byte identities already pinned in the
reviewed \`lodi_sheets.py\` v6 contracts and
\`data/publication/multi_prefecture_pilot.json\`:

- \`lodi-listed\`, SHA-256 \`0cb78eec4e7c902a9ec9e6fa3b64ef52c276a2de32cd86cba3e59cf68775d945\`;
- \`lodi-applicants\`, SHA-256 \`c200e90a0410ba23fddee9d3ad0a5ac1532fec8dedfe0ec983eb2e94d0601a16\`.

The parser's reviewed observations are 169 grouped listed records
(145 \`listed\`, 24 \`renewal_update_in_progress\`) and six applicant
records (two \`rejected_or_denied\`, four \`pending\`). These counts are
**source-document occurrences** under the existing strict parser contract,
not unique economic operators or a newly approved legal status.

The script \`acquisition.historical_source_qualification\` selects exactly one
existing reviewed configuration per source key, checks SHA-256, source type,
population and its *pre-existing source-observation boundary label*,
retrieves exact immutable original bytes from **primary** R2 through the
existing \`EvidenceStore.read_digest_verified\`, rehashes them and runs the
**unmodified** strict Lodi v6 parsers. Inputs are staged only in a temporary
private runner directory, removed after parsing. Parser exceptions, private
provider coordinates, source rows and individual identifiers never appear in
the closed-schema JSON summary. Cardinality and source-status distributions
must match the reviewed contracts. Failure or unavailable evidence remains
\`selection_unverified\`, \`primary_bytes_unknown\` or
\`parser_review_required\`; it is not an object-loss claim or approval.

This check uses the **existing protected transform shard 0**. It introduces no
extra runner, trigger, credential, crawler, timer or persistent resource.
It makes no live-prefecture requests, no capture or PostgreSQL writes, no
edition attribution, no semantic/canonical execution and no publication. It
does not cause unrelated reviewed source transforms to fail if this independent
historical diagnostic is unavailable.

## Acceptance boundary

A \`strict_parser_compatible_source_only\` result proves, at most, that the
selected historical bytes were retrievable from primary R2 and passed the
already reviewed physical parser contract in that specific execution. It does
**not** establish contemporaneous capture provenance in the immutable
CaptureCatalogue, presence of the historical object in PostgreSQL, legal
reference/decision dates, a newly approved edition, today's mutable Lodi
source layout, independent backup/restore, or public-release eligibility.
The existing listed/applicant quarantines remain enforced.

The historical observation-boundary labels in the frozen reviewed source
configuration do **not** become approved administrative edition dates.
All missing dates remain unknown. The source's denials and pending labels
are preserved as explicit reported source statuses, not independent legal
determinations. Absence between documents implies no revocation or removal.

After a protected run, record the safe two-source result in issue #225 and
independently reconcile the exact immutable capture manifest or documented
legacy acquisition package **before any relational backfill**. If complete
provenance is unavailable, retain a known-version-only recovery status; never
invent a capture ID or date from an R2 hash. Any future parser or edition
promotion requires its separate source, temporal, population and reviewer
gates. The #16 independent recovery and #163 national backlog criteria stay
open until their respective executed acceptance evidence exists.
