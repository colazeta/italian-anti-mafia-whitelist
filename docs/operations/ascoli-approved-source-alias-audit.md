# Ascoli Piceno — read-only qualification of one frozen source alias

Status: **review-only candidate; no binding or materialisation authorised by this document**.
Evidence checked: 15 November 2026, approximately 07:50 UTC, on production
Neon project `rapid-dust-83010061`, branch `br-sparkling-boat-b954jrme`,
database `whitelist`. No sensitive credentials, object locations, personal
values or source rows are included in this record.

## Why this exception exists

The selected, frozen national source configuration names the already
reviewed Ascoli Piceno comprehensive listed PDF
`ascoli-piceno-listed` (11 August 2026, listed population, 544 expected
source observations). The reviewed source-series inventory and PostgreSQL
instead use `ascoli-piceno-listed-comprehensive`. The inventory explicitly
records that the comprehensive attachment is the selected all-sector
source, while separate sector-specific files are not automatically merged
into it.

A fresh relational read across SourceSeries, ContentObject, SourceCapture,
publisher and White List register verified that one capture of the
comprehensive series matches the **entire exact SHA-256** in the frozen
manifest. The stored content object is durable; the capture is recorded
as `official_current`, `primary_official`, HTTP 200, and its publisher is
`ascoli-piceno` in regime `WL-REGIME-L190-2012`. The listed
comprehensive and applicants series resolve to the same PostgreSQL
register. The capture is dated 7 November **as an acquisition timestamp
only**. Its `declared_reference_date` is NULL: the approved 11 August
document date must not be copied into that field or interpreted as an
administrative event.

**Separate QA gap:** this comprehensive ContentObject currently has
**zero linked ParseRun and zero ParseSnapshot**. Matching bytes and source
scope do not prove a parser output, record count, field interpretation or
approval. In contrast the separately registered applicants series has one
source snapshot (57 record occurrences). Do not automatically substitute
the comprehensive capture into the historic approved backfill: it was
captured under its genuine registered series identity, not retroactively
under the legacy public alias.

## Reusable, restrictive check

`white_list_archive.acquisition.approved_source_alias_audit.qualify_review_only_alias`
accepts the *frozen* public source descriptor, reviewed source-series
inventory and independently queried aggregate capture evidence. It
refuses any changed SHA, parser, date, authority, register, population,
sector scope, origin, durability or non-unique capture. The only supported
pair is the two keys above. Its output is explicitly a review-only
candidate, not an automatic mapping. It performs no network fetches, SQL
writes or public-release edits.

A downstream source-only binding, if separately implemented, must
independently verify an authentic immutable CaptureCatalogue receipt,
the full byte identity and the actual source series/authority/register,
then pass a versioned parser/record-contract QA including all 544
expected observations, sectors and state/date interpretation. It must
preserve the original capture ID and provenance, not invent or relabel
historical captures. Any different source version or logical population
requires separate qualification. Public release and semantic/canonical
approval remain separate, explicit gates.

This review does not change the selected national release and does not
resolve the other 17 manifest-to-database exact-input gaps. It is not an
executed independent recovery test.

## Exact primary-original and physical-parser QA (15 November 2026)

The new read-only `acquisition.ascoli_private_source_qa` compares the frozen
`ascoli-piceno-listed` public descriptor with the reviewed
`ascoli-piceno-listed-comprehensive` source series. It reads the entire
474,484-byte original from the existing primary R2 content-addressed store,
checks the full SHA-256 again and executes the existing strict 110-page
`ascoli_piceno_listed` parser in a transient private directory. It independently
requires 544 source occurrences, 448 explicit listed states, 96 explicit
update-in-progress states, source section fields, identifier coverage and
source-backed decision/expiry dates, without displaying original text or rows.

In the same protected step it *independently* audits pre-existing immutable
CaptureCatalogue entries for that exact registered comprehensive series and
digest, with bounded listing and full original readback. A successful parser
check must never substitute for an authentic capture record or PostgreSQL
snapshot; an unknown catalogue result remains unknown. This audit creates no
capture, parser snapshot, SourceEdition, semantic/canonical observation, alias
binding or public promotion. Review the real job receipt and a separate Neon
readback before claiming production acceptance. The original public release
selector is unchanged. The verification is not an independent backup/restore.

## Bounded source-only materialisation (subsequent controlled step)

`acquisition.ascoli_private_snapshot_backfill` is a **separate** protected
worker step, not a change to the original read-only audit. It is restricted to
the **single exact** 11 August 2026 comprehensive listed original and performs
the following gates before calling the already-tested common database writer:

1. Require the unchanged published legacy descriptor and reviewed registered
   `ascoli-piceno-listed-comprehensive` inventory, full original digest/size,
   544 parsed records, 448 listed and 96 update-in-progress statuses, dates,
   identifiers and sections, and one authenticated complete CaptureCatalogue
   record with explicit source provenance.
2. Re-read the source-specific, bounded immutable catalogue (without live
   acquisition or alias rewriting), require one and only one exact capture and
   match its original source URL, HTTP status, unknown capture reference date,
   origin and authority rank to the frozen approved source.
3. Preserve the actual `capture_id` and registered source key in the private
   relational writer. The reviewed document date can be used for the *source
   observation* configuration; the unknown capture date stays unknown.
4. Before a write, search all earlier code revisions for the same parser,
   full labelled original hashes and configuration hash. Reuse and rehash a
   valid existing snapshot. Otherwise write one source snapshot, verify the
   committed result independently and re-run the cross-revision lookup.

Unknown/mismatched provenance, parser QA, incomplete catalogue, TLS/readback
failure, non-unique capture or field/count drift **fail closed**. Console output
contains only a closed aggregate outcome, with no original rows, company data,
capture identifiers, provider locations or exception details. This step is
wired into the **existing** `Transform reviewed captures` protected shard 0;
it does not add a crawler, executor, scheduler or independent publisher.

This implementation does **not** by itself prove a production write. Acceptance
requires exact-head tests and post-merge CI, protected job terminal status and
independent PostgreSQL readback showing the expected Ascoli ParseRun/ParseSnapshot
for the original SHA. Even a successful snapshot is not a SourceEdition,
semantic/canonical observation, approved *new* edition or public promotion.
The selected public release remains unchanged unless an independent reviewed
publication process explicitly approves a new immutable candidate.
