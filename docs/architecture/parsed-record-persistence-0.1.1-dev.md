# Parsed-record persistence — 0.1.1 development line

## Purpose

This note documents the first row-level persistence implementation for real White List source observations. It extends the 0.1.1 development line without changing the meaning of the frozen 0.1.0 release.

The first implementation target is the Prefettura di Cosenza combined White List series.

## Layer boundary

The flow is:

```text
ContentObject
  -> ParseRun
     -> ParsedRecord
        -> SourceFieldValue
        -> EntityMention
```

These objects belong to the **source-observation layer**. They are not canonical companies, White List relationships or administrative states.

A successful parse therefore does **not** create a `core.legal_entity`, `white_list_relationship`, registration/removal event or legal-effect status.

## Reproducible ParseRun

Each parser execution emits a parse manifest containing:

- parser name;
- parser version;
- exact Git processing revision;
- configuration hash;
- start/completion timestamps;
- input text SHA-256;
- emitted record count.

`source.parse_run.parse_run_code` is a stable internal key derived from:

`ContentObject SHA-256 + parser name + parser version + processing Git revision + configuration hash`.

The UUID remains the database primary key. `parse_run_code` is an internal idempotency/reproducibility key and is not a source identifier.

A changed parser revision/configuration creates a distinct parse run even when the input bytes are identical.

## ParsedRecord immutability

Each Cosenza parser-v1 row becomes one `ParsedRecord` with:

- deterministic row locator (`row:000001`, etc.);
- parser-computed record hash;
- full raw row block in `raw_record_text`;
- source schema version.

Parsed records are immutable. Corrections or improved extraction require a new ParseRun; the earlier parse remains available for audit/reproducibility.

## Fields persisted by parser v1

Only source fields that parser v1 structurally isolates with sufficient confidence are materialised as `SourceFieldValue`:

1. `Ragione sociale`;
2. `Codice fiscale/Partita IVA`.

The source identifier is deliberately parsed as `UNRESOLVED_CF_OR_VAT`; an 11-digit value is not automatically promoted to a canonical tax-code or VAT identifier and is not treated as a unique entity key.

The normalised business name is stored as a parsed representation of the raw source name, not as a canonical name.

## Why `source_status` is not yet a SourceFieldValue

Parser v1 classifies wording in the full source row into analytical source-status categories such as `listed`, `pending` or `renewal_update_in_progress`. This is useful for edition-to-edition diagnostics but parser v1 does not yet isolate the exact raw `Esito` field structurally across all multiline cases.

Therefore the classification remains parser output/diagnostic metadata rather than being persisted as though it were a faithfully isolated raw source column. The entire raw row block is retained, so a later parser version can add a proper raw `Esito` field without rewriting v1.

Even when persisted later, source `Esito` will remain distinct from canonical legal effect.

## EntityMention boundary

Each row produces one unresolved `EntityMention` with role `unknown` in the combined Cosenza list. The parser does not infer canonical identity or even force a listed/applicant role from status wording.

Entity resolution remains a separate processing activity with its own method, confidence and review trail.

## Readable source-observation mart

`mart.cosenza_source_mentions` exposes a simple query surface over the provenance graph. It includes:

- edition code/reference period;
- row locator/hash;
- raw and normalised operator name;
- raw source identifier and parsed identifier-scheme marker;
- full raw record block;
- parse-run and parser provenance;
- content SHA-256.

Example:

```sql
SELECT *
FROM mart.cosenza_source_mentions
ORDER BY edition_code, record_locator
LIMIT 50;
```

This mart is intentionally named `source_mentions`: it is not the canonical White List dataset.

## Validation

Normal CI uses synthetic fixtures to verify:

- ParseRun reproducibility;
- ParsedRecord immutability;
- exact field-value cardinality;
- unresolved EntityMention creation;
- repeated import idempotence;
- readable mart output;
- zero canonical entities created by parsing.

The live Cosenza workflow additionally re-downloads the two frozen official editions and requires exact agreement with the frozen resource URL, PDF SHA-256, text SHA-256, page count and structural schema fingerprint before attaching row-level parsing to the frozen ContentObjects.

A mismatch causes the workflow to fail and requires review as a new capture.

## Dissemination boundary

Row-level source observations are internal archive data at this stage. They are not committed as a public CSV/JSON release in `data/releases/`.

A later release/browser layer can expose reviewed fields after provenance, data-quality, reuse and privacy checks. Until then the supported inspection surface is PostgreSQL/read-only marts plus ephemeral workflow artifacts used for reproducibility testing.
