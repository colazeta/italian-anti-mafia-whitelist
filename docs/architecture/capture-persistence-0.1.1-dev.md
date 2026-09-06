# Capture persistence — 0.1.1 development

The first live Cosenza content capture exposed a small set of requirements that were not explicit in schema 0.1.0. This note records the rationale for the 0.1.1 development changes.

## Stable internal codes

Operational ingestion must be idempotent. Random UUIDs remain the database primary keys, but repeatable loaders also need stable internal lookup codes for objects that recur across runs.

The development schema therefore adds nullable unique project codes:

- `core.public_authority.authority_code`;
- `source.source_series.series_code`;
- `source.source_edition.edition_code` within a series.

These are **project identifiers**, not source-issued or administrative identifiers. They do not replace `authority_identifier`, company identifiers, source locators or provenance.

A dated Cosenza page can therefore be loaded repeatedly as the same logical `SourceEdition`, while repeated HTTP observations remain distinct `SourceCapture` objects when capture time/content differs.

## Unknown register start date

Schema 0.1.0 required `white_list_register.effective_period` to be non-null. During the Cosenza import we know that the current ordinary register exists, but the pilot has not independently established its exact administrative start date.

The development schema therefore allows `effective_period = NULL` for a register. The meaning is strictly:

> exact effective interval not yet established canonically.

It does not mean an unbounded historical period.

This avoids manufacturing `2013-08-14` as the start date of every individual Prefecture's register merely because that is the lower bound currently used for the ordinary legal regime.

## Ephemeral versus durable content storage

A `ContentObject` is identified by its byte SHA-256. The first live capture acquired the PDF bytes and verified their hashes, but the bytes initially live in a GitHub Actions artifact rather than the future archival object store.

The development schema introduces `content_storage_status`:

- `ephemeral` — acquired/hash-identified, but currently held only in a non-durable location;
- `durable` — stored in the designated durable content-addressed store;
- `unavailable` — identity is known but no retrievable byte location is currently available.

Byte identity (`sha256`, `file_size`) remains immutable. A durable object cannot be downgraded to an ephemeral/unavailable state.

The current Cosenza manifests are imported as `ephemeral` with a `github-actions://...` storage URI. This is intentionally transitional and is not presented as archival completion.

## Capture-level HTTP provenance

`source_capture` now preserves:

- final/resolved URL;
- HTTP ETag;
- HTTP Last-Modified timestamp.

Together with `captured_at`, HTTP status, origin type, evidence rank and the linked content SHA-256, this permits an acquired representation to be independently audited and later rechecked for source replacement.

## Persistence boundary of the current pilot

The importer currently materialises:

`PublicAuthority -> WhiteListRegister -> SourceSeries -> SourceEdition -> SourceResource -> SourceCapture -> ContentObject`

and:

`SourceSeries -> SourceSchema -> SourceSchemaVersion`.

It does **not** yet create a successful `ParseRun` because row-level `ParsedRecord` objects from the live parser have not yet been durably loaded into PostgreSQL. Creating a successful parse run without its records would overstate persistence completeness.

## Release semantics

`VERSION` remains `0.1.0`, the last frozen/validated schema release. The Python project version is moved to `0.1.1.dev0` while these additions are tested. A subsequent release should be made only after the migration/import path and PostgreSQL regression gate are green on `main`.
