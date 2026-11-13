# Historical Lodi/Milano capture provenance: bounded private readback

The primary R2 check from #252 established that three exact historical source byte
identities were retrievable, but **did not** establish any contemporaneous
capture/check provenance. A SHA-256 digest is not an administrative edition,
and the current PostgreSQL ContentObject catalogue did not contain the four
historical identities when last checked. No capture must be manufactured from
a digest or a current mutable source.

The existing protected \`Transform reviewed captures into private observations\`
shard 0 now runs \`storage.historical_capture_provenance_audit\` read-only
after the primary byte check and historical Lodi parser QA.

The check selects **only four existing frozen public historical pins**:

- Lodi listed and applicants, exact SHA identities pinned in reviewed parser v6;
- Milano combined on the 22 and 27 September 2026 observation boundaries,
  pinned in the prior reconciliation PR #162.

For each of three named reviewed SourceSeries the probe reads at most **64
capture-catalogue entries** from the existing private
\`captures/v1/<source-key>/\` prefix. It does not enumerate the entire bucket
or equate a prefix listing with the complete national archive. A candidate
must have a canonical UUID capture key, match one of the exact frozen
historical source digests, successfully rehydrate its **complete embedded
immutable capture manifest** using \`load_catalogued_capture\`, pass the
existing \`CaptureCatalogue.verify_receipt\` path, and independently read and
hash the exact ContentObject with its original declared byte size.

Only the aggregate number of already-existing verified capture/check identities
per frozen scope is reported. The closed output does not include private
object keys, capture IDs, source URLs, source rows, personal information or
provider exception text. \`verified_immutable_capture_provenance\` is a
positive, exact, byte-backed catalogue claim, **not** a new DB insertion or
approved source edition. If the relevant prefix is inaccessible or its bounded
listing is truncated, \`bounded_catalogue_listing_complete\` is false.
An unverified candidate, absent manifest or negative bounded result remains
\`unknown\`; it does not imply lost or missing source evidence. Old catalogue
records without an embedded complete manifest are not rewritten or silently
upgraded. The check creates **zero** acquisitions, database writes,
administrative editions, semantic/canonical materialisations or public releases.

This is a diagnostic inside an already-authorised protected worker, without
new workflows, jobs, scheduled actions, credentials, costs or privileges.
It does not alter the existing quarantine, SHA pins, historical campaign,
reviewer authorisation contract or public release gate.

A successful runtime readback allows the verified capture provenance to be
**reviewed for a separate, reversible persistence proposal**; it does not
authorise backfill or promotion. A negative or unavailable result requires
checking already-authorised historical manifests and evidence packages, not
guessing dates/identities or re-downloading mutable URLs. Backup/restore
**independence** under #16 must still be demonstrated using a separate target;
a primary R2 read is not proof of independent recovery.
