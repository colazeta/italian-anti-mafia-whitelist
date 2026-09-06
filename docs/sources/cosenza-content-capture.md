# Cosenza content-level capture pilot

Date of first controlled capture: 2026-09-06

This note records the first White List ingestion step that goes beyond source discovery and edition inventory into immutable content-level acquisition and an observational diff between two real published snapshots.

## Editions captured

The pilot uses two adjacent verified editions of the Cosenza combined source series:

- reference date **2026-06-28**;
- reference date **2026-08-03**.

Both edition pages are official Prefettura di Cosenza pages and each exposes a combined PDF covering companies shown as registered and/or requesting registration, plus section-specific resources.

The exact capture manifests are stored under `data/captures/cosenza/`.

## Content identity and HTTP provenance

The capture workflow resolves the attachment URL from the dated edition page and records:

- source reference date;
- edition page URL;
- resolved resource URL and final URL;
- HTTP status;
- UTC capture timestamp;
- ETag and Last-Modified when supplied;
- MIME type and byte size;
- SHA-256 of the original resource bytes;
- PDF page count;
- SHA-256 of the deterministic `pdftotext -layout` representation;
- structural schema fingerprint;
- exact Git processing revision and GitHub Actions run/artifact identifiers.

The June and August PDFs have different binary SHA-256 values, as expected for distinct editions, while both yield the same structural schema fingerprint:

`fbb124c5a43d26bef93316844b3021096060f7ed9d2cc0f8f6081f6df935dc97`

Both files contain 69 pages. This is direct evidence that the same parser/schema family can be used for this adjacent-edition comparison without silently assuming document identity.

## First observational diff

The mention parser deliberately produces **source mentions**, not canonical Legal Entities. Matching for this diagnostic uses the pair `(source identifier, normalised source name)` and preserves ambiguity for later entity resolution.

Aggregate result from 2026-06-28 to 2026-08-03:

| Metric | Value |
| --- | ---: |
| source rows before | 1,325 |
| source rows after | 1,332 |
| net row difference | +7 |
| mention observations added | 21 |
| mention observations disappeared | 14 |
| common mentions | 1,311 |
| common mention records whose content changed | 67 |
| new source identifiers | 19 |
| disappeared source identifiers | 12 |
| stable-identifier source-name changes | 2 |
| ambiguous source identifiers | 1 |
| common mentions whose parsed source-status wording changed | 55 |

Parsed source-status counts changed from:

- `pending`: 658 → 654;
- `listed`: 452 → 461;
- `renewal_update_in_progress`: 202 → 201;
- `renewal_requested`: 11 → 14;
- `other_or_unknown`: 2 → 2.

The most frequent observed source-status transition was `pending -> listed` (25 mentions). Other observed transitions are retained in the aggregate diff JSON.

## Interpretation guardrails

These diagnostics are deliberately weaker than administrative-event claims.

1. `added` means a mention is observed in the later source and not under the same mention key in the earlier source. It does **not** by itself mean a new registration.
2. `disappeared` means a mention is no longer observed under the same mention key. It does **not** mean administrative removal.
3. `source_status` is a parser classification of published `Esito` wording. It is not the canonical `legal_effect_status`.
4. A source identifier is evidence, not a canonical entity key.
5. A source-name change on the same unique identifier is a resolution candidate, not proof of corporate continuity or succession.

## Empirical validation of the entity-resolution design

At least one 11-digit identifier occurs against more than one distinct source mention in the captured material. The repository therefore must not enforce the naïve rule:

`identifier_value -> one LegalEntity`

This directly supports the existing architecture:

`ParsedRecord -> EntityMention -> EntityResolution -> LegalEntity`

The ambiguity is retained for review rather than silently collapsed.

## Raw content storage policy in this pilot

PDF bytes and row-level extracted records are **not committed to Git**. The successful GitHub Actions run uploaded them as a workflow artifact and the repository freezes only:

- immutable content hashes and acquisition metadata;
- structural fingerprints;
- aggregate diagnostics;
- processing revision/run lineage.

The manifest currently records `raw_content_storage_status = workflow_artifact_ephemeral` because GitHub Actions artifacts are not the durable archive intended by the database model.

The next infrastructure step is therefore durable content-addressed object storage. Once available, the raw resource bytes should be written under their SHA-256 identity and the durable object URI recorded in `ContentObject.storage_uri`. Git and Git LFS should not be treated as the primary archival object store.

## Next ingestion step

1. Persist these manifests as actual rows in `SourceEdition`, `SourceResource`, `SourceCapture`, `ContentObject`, `ProcessingActivity` and `ParseRun`.
2. Generalise the same capture/parser version across all verified Cosenza editions that share the structural fingerprint.
3. Treat any fingerprint change as a new `SourceSchemaVersion` requiring explicit parser validation.
4. Continue national source-registry resolution in parallel.
