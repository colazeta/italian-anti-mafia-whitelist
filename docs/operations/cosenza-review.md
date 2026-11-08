# Private Cosenza document review dossier

The existing protected Cosenza owner queue automatically calls this preparation
after independently verified rich readback and QA. Each actual source revision
is processed separately; the two existing reviewed input pairs use their explicit
June/August order. Source completion receipts are preserved. Dossier failure makes
the workflow fail visibly and is retried on the next eligible wake-up without
rewriting completed source work. The existing ordinary robot completion, exact
owner command and relevant main push routes share this same workflow; there is
no additional schedule, crawler, credential or privilege. New inputs beyond the
two reviewed pairs still require their own validated acquisition/parser route.

`normalisation.cosenza_review.retain_review(conn, store, *, inputs,
dossier_code_revision)` prepares and retains a deterministic dossier for one or
two explicitly ordered versions. Each input must contain exactly `capture_id`,
`parse_run_id`, `source_revision` and `expected_count`. The source revision
identifies the code that actually produced the rich interpretation. The separate
dossier revision identifies the executing review and candidate-planning code.
The caller owns a read-only database connection and its rollback; no parser,
source writer, edition importer, semantic pipeline or publisher is invoked.

Each input passes the existing full rich QA and lineage readback. Its immutable
capture catalogue entry and archived original are independently loaded and
verified; original SHA-256/byte length must match both the manifest and QA.
Snapshot rows and diagnostics are read and rehashed again against the exact QA
snapshot pin. These verified rows feed the pure candidate planner without a
second planner database read. A digest check binds the candidate payload before
it enters the dossier. The dossier retains source/capture/snapshot identities,
original provenance and timestamps, parser version/configuration/fingerprint,
separate code revisions, complete snapshot rows/diagnostics, aggregate QA
anomalies and the deterministic candidate payload.

The dossier is a private working document. Row-level source values, names,
identifiers, provenance URLs, private object keys and candidate records remain
in R2. The function returns keys for internal use and a separate `safe_summary`;
only that summary may be printed or placed in public workflow evidence. It has
counts, digest proofs, verification flags and blocked readiness, without source
identities, storage keys or source rows. Never print the complete return value or
`load_retained_review(store, dossier_sha256)`, which returns the verified private
row-level document.

Every version has an explicit unknown administrative reference date. Capture
metadata, owner-command labels, filenames and ordinal comparison order are not
substitutes for a reviewed document reference date. No header extraction or PDF
reparse is performed. The preserved exact original remains the review source;
the checklist requires a reviewer to inspect its document identity, dates,
population/sector coverage, identifiers, temporal differences and attribution.
This preparation neither authenticates a reviewer nor records an approval.

For two versions, the caller supplies the comparison order explicitly. Identical
record hashes are counted as a multiset, preserving duplicate occurrences.
Before-only and after-only occurrences mean document differences only. A shared
mention key is compared field-by-field only when it occurs once in each input;
ambiguous groups are counted, without arbitrary pairing or identity resolution.
Row ordinals are preserved as provenance but excluded from changed-field lists.
An absent row never becomes a revocation, cancellation, interdiction or other
legal event. The comparison makes no claim about distinct enterprise counts.

Canonical UTF-8 JSON excludes observation-time QA timestamps. The dossier and its
receipt use SHA-256-addressed immutable R2 keys; a checkpoint also binds ordered
inputs, dossier code and the full evidence digest. All writes use conditional
creation followed by bounded byte-for-byte readback. Repeated identical work
reuses exactly the same objects. A new code revision, changed ordered input or
changed reviewed evidence produces separate immutable objects, retaining prior
ones. Corruption, incomplete QA, mismatched original/snapshot pins or receipt
readback failure raises without claiming verified retention. The loader rehashes
the retained dossier before returning it. Payloads are bounded to 32 MB.

Successful preparation reports zero database writes and edition approvals, with
semantic and publication readiness false. The main workflow still needs a real
run proving persisted dossier/receipt hashes and complete independent readback;
unit tests or an uploaded workflow artefact alone are insufficient operational
acceptance.

The disposable PostgreSQL check `tests/cosenza_review_db_check.py` runs after the
existing `tests/capture_rich_db_check.py` fixture. It uses real source tables,
full QA/readback and candidate planning, retaining a synthetic in-memory archive
fixture. It verifies deterministic repeat retention and unchanged source,
edition, semantic and canonical row counts in a read-only transaction. The
external catalogue is mocked only for this isolated database check; a production
main run must independently verify the actual R2 catalogue and original bytes.
