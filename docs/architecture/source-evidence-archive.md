# Original-source evidence archive

## Purpose

A provenance-aware White List archive is not independently auditable if it retains only parsed values and metadata about a source that may later disappear or change. The exact bytes used by a parser are therefore first-class evidence.

For every captured source edition, the archive should be able to answer four separate questions:

1. **What resource was retrieved?** — source URL, capture time, HTTP metadata and source-edition context.
2. **What exact bytes were parsed?** — immutable `ContentObject` identity keyed by SHA-256.
3. **Where is the preserved copy?** — durable storage locator when a long-term evidence backend exists.
4. **Where in the original document did a parsed observation come from?** — parser-specific physical locator such as PDF page and, where reliable, table/row/bounding-box coordinates.

This turns parser quality from a trust claim into something an independent reviewer can reproduce.

## Evidence chain

The intended evidence chain is:

```text
SourceEdition
     │
     ▼
SourceResource / original URL
     │
     ▼
SourceCapture ───── capture time / HTTP metadata
     │
     ▼
ContentObject ───── SHA-256 / MIME / byte size
     │
     ├──────────── durable evidence-storage URI
     │
     ▼
ParseRun
     │
     ▼
ParsedRecord ───── physical source locator
     │
     ▼
SourceFieldValue
     │
     ▼
semantic / canonical evidence links
```

A URL is never treated as document identity. If the same URL later serves different bytes, that is a new `ContentObject` and a new capture.

## Current Cosenza pilot

The live Cosenza workflow now creates an internal evidence package after verifying the official PDFs against the frozen capture manifests.

For both the 28 June 2026 and 3 August 2026 editions the package contains:

- the exact original PDF bytes used for parsing;
- SHA-256, byte size, page count and original official URL;
- a row-ordinal → PDF-page locator for every parser-v2 observation;
- the Dataset Explorer itself;
- database-table previews and full internal CSV exports.

The row detail view links directly to the preserved PDF at the reconstructed source page (`#page=N`). This locator is evidence about parser provenance; it is not an administrative identifier and it does not assert that the row occupies only that page.

The workflow refuses to package a PDF if its SHA-256 differs from the frozen `ContentObject` identity. It also validates that every current parser-v2 row has a page locator.

## Durable storage versus workflow artifacts

The current Explorer package is an **auditable pilot package**, not yet the final durable archive. GitHub Actions artifacts are retention-bound and must not be mistaken for permanent evidence storage.

The production archive should use a dedicated object store such as S3-compatible storage / Cloudflare R2 or equivalent. Git is not the correct backend for thousands of binary source documents.

Recommended content-addressed object key:

```text
sha256/<first-two-hex>/<full-sha256>.pdf
```

Required durable-storage properties:

- immutable/content-addressed writes;
- no overwrite of an existing hash key with different bytes;
- `ContentObject.storage_uri` (or equivalent storage locator) written only after successful durable upload;
- explicit storage status (`ephemeral`, `durable`, `missing`, etc.);
- object versioning/retention controls where operationally appropriate;
- independent integrity checks against the database SHA-256;
- backup/replication policy separated from publication policy.

A new byte sequence always creates a new `ContentObject`; it never replaces the previous one.

### Recovery-inventory verification semantics

The national recovery inventory distinguishes byte preservation from a complete archived acquisition. A capture is `verified` only when both the exact durable `ContentObject` and the immutable capture/check provenance can be read back and verified. Durable bytes with missing or invalid capture provenance still count as a durably retrievable ContentObject, but the capture remains `not_verified` until its temporal provenance is established. This prevents storage availability alone from being reported as complete temporal coverage.

`recoverable_pending` is reserved for exact matching bytes found in an explicitly supplied recovery package when the governed durable original is not yet verified. `missing` requires both positively confirmed durable absence and an explicitly completed recovery search; failed provider reads, incomplete searches and corrupt objects remain `not_verified` rather than being converted into unsupported loss claims.

### National recovery denominator

The recovery denominator must include more than archive-first capture manifests. Historical transition notes or reviewed source evidence can prove that a byte version was actually observed even when no durable capture UUID/catalogue record survives. Those versions remain part of the recovery problem, but the project must not invent a historical `SourceCapture` or `SourceEdition` identifier after the fact.

The denominator therefore distinguishes two identity classes:

- `capture`: an acquisition with a stable capture identity that can be checked against immutable capture provenance;
- `known_version`: a byte identity supported by one or more explicit evidence references but lacking recoverable capture identity.

A `known_version` uses an `evidence_version_key` only as a reconciliation key. It is not an administrative edition label and cannot be promoted to `verified`, even when matching bytes are already in the governed object store, because durable bytes alone do not establish the missing temporal capture/check provenance. Exact bytes in a recovery package may be `recoverable_pending`. A `missing` outcome additionally requires known byte size, positively confirmed durable absence and an explicitly completed recovery search. Unknown byte size therefore remains `not_verified` rather than being converted into loss.

Denominator metrics keep captures, historical versions without capture identity, distinct known ContentObjects and durably retrievable ContentObjects separate. Repeated evidence items may legitimately reference the same SHA-256: the evidence items remain distinct while the ContentObject count is content-addressed. This preserves evidence of repeated or differently documented observations without fabricating capture times or deduplicating away known recovery obligations.

## Verification workflow

An independent reviewer should be able to:

1. open a row in the Dataset Explorer;
2. inspect the parsed raw/source values;
3. open the preserved original PDF at the referenced page;
4. compare the visual source row with the parser output;
5. verify the PDF SHA-256 against the evidence metadata;
6. trace the observation through `ParseRun`, semantic projection and any canonical evidence links.

For a stronger later implementation, physical locators may include bounding boxes or table-cell coordinates when the parser family can emit them reliably. Page-level locators are already valuable and should not be replaced by invented precision.

## Dissemination boundary

Preserving source bytes internally and redistributing them publicly are different decisions.

The archive should retain exact source evidence when legally and operationally permitted, but a public dissemination profile may expose:

- the original document;
- a transformed/redacted evidence view;
- only provenance metadata and the official source link;
- or no document bytes at all.

This decision is separate from capture and provenance. Public availability at the time of capture does not by itself settle indefinite bulk redistribution, especially where documents contain personal data or sole-trader information.

## Operational invariant

A parser result is not fully audit-ready merely because its rows are reproducible. For production ingestion, the project should aim for:

`validated source identity + preserved original bytes + parser version/configuration + physical locator + parsed raw value + downstream provenance`.

If durable source bytes are temporarily unavailable, the archive must say so explicitly rather than implying that a URL alone is equivalent evidence.

## Implementation

The S3-compatible adapter, verified database promotion and private verification workflow are documented in [evidence-store operations](evidence-store-operations.md). Implementation tests do not establish that a production store has been provisioned.
