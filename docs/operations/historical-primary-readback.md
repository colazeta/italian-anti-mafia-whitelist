# Four historical Lodi/Milano object identities — protected, read-only R2 check

This narrowly scoped primary-store audit addresses the four historical source
SHA-256 identities documented in `tests/test_lodi_parser_semantics.py`
and in the review discussion of PR #162. Earlier SQL checks found that none
of these four historical byte identities was present in the then-current
PostgreSQL ContentObject catalogue. That absence does not establish an
absent or lost object in R2.

The existing `Transform reviewed captures into private observations` workflow
executes `historical_object_audit` **inside its existing protected shard 0**.
It does not introduce a job, trigger, credential, timer, crawler or resource.
The audit makes exactly four content-addressed primary R2 GET/readback attempts
using the already implemented `EvidenceStore.read_digest_verified` primitive.
It computes SHA-256 again on the returned bytes and enforces a size ceiling.
It does **not** download mutable source URLs, acquire captures, register
ContentObjects, write PostgreSQL, parse data or approve source editions.

The only output is a fixed, aggregate-safe JSON summary with one bounded
status per named historical scope and explicit negative claims for provenance,
PostgreSQL materialisation, parser/edition approval and independent recovery.
A verified digest proves **that exact bytes were retrievable from the primary
R2 store at that run**, not that the bytes have complete contemporaneous
capture provenance, are correctly attributed to a reviewed source edition or
are present in Neon. A failed GET, integrity mismatch or unavailable provider
is `unknown`, **never** evidence that a version is missing or irrecoverable.
Exception messages and source bytes are not reported. No output is promoted
as public source data, and no new public artifact is uploaded.

After a protected run, compare the reported statuses with read-only Neon
ContentObject/capture checks. For any available historic SHA, recover and
verify its exact capture provenance separately from an existing immutable
catalogue or historical manifest before proposing a reversible backfill.
For unavailable/unverified SHA, seek other existing authorized evidence
packages without inferring loss. The existing quarantine for the *current*
Lodi listed/applicants and Milano combined source versions stays enforced;
each new byte-distinct version requires its own parser compatibility and
population review. The existing edition/reviewer and public-release gates are
unmodified. The audit is **not** a substitute for an independent backup
and executed clean restore under issues #16/#163.

The first protected execution needs a reported outcome and readback evidence
before this change can be called operationally verified. Passing synthetic
unit tests or merging the code alone is not that evidence.
