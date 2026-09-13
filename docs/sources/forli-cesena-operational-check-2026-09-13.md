# Forlì-Cesena operational source check — 2026-09-13

## Scope

This note records the evidence and parser-preparation checkpoint for national expansion. It is **not** publication approval and does not yet mark Forlì-Cesena as publicly integrated.

## Current official publication surface

Official Prefettura landing page:

- https://prefettura.interno.gov.it/it/prefetture/forli-cesena/evidenza/white-list

The current page was verified on 2026-09-13. It exposes one current attachment labelled **“White list dell'11 settembre 2026”** (473.63 KB) and reports a page update timestamp of **11 September 2026, 13:22**.

Current official attachment identified from that page:

- https://prefettura.interno.gov.it/sites/default/files/44/2026-09/wlp-al-11-09-2026.pdf
- stated edition date: 2026-09-11

The publication itself provides the semantics needed for the two non-default current-state markers: `AVVIO ISTRUTTORIA` is the application/instruction-stage population and `IN AGGIORNAMENTO` is the renewal/update population. Rows without either current-state marker retain populated enrolment provvedimento/expiry fields and are treated as listed only after structural parser validation.

## Content-addressed capture

The branch-local source audit fetched the exact official PDF twice from the Prefettura endpoint through the GitHub runner. Both responses were HTTP 200, valid PDF files and byte-identical:

- byte size: `485001`
- SHA-256 fetch A: `f18e1980e6f7f5bc2ac55a55926ab7a221f290fc7a40f5d0781eef4885455468`
- SHA-256 fetch B: `f18e1980e6f7f5bc2ac55a55926ab7a221f290fc7a40f5d0781eef4885455468`
- byte identity: `true`

A subsequent layout-preserving extraction from those pinned bytes established:

- 69 pages;
- layout-text SHA-256 `69df0461a19e6aae14aecfd2ff4d69ae328f9122c00231c4566427daae745d03`;
- the PDF has no extractable ruled tables under `pdfplumber.extract_tables()`, so a table-family parser is not appropriate for this edition.

## Row and population reconciliation

A positioned logical-block audit reconciled the whole pinned edition to **749 source observations** with no remaining structural anomaly under the reviewed block boundaries:

- 401 rows with no explicit current-state marker and populated listed/provvedimento semantics;
- 204 rows explicitly marked `IN AGGIORNAMENTO`;
- 144 rows explicitly marked `AVVIO ISTRUTTORIA`;
- 747 rows begin with a strict 11-digit identifier;
- one source row contains the 10-digit token `0543034730` for `V8 TRASPORTI & LOGISTICA SRL`; it must remain raw and must not be padded or repaired into a canonical identifier;
- one foreign source row, `GRUPPO IDRODEMOLIZIONI SRL - SOCIETA' ESTERA`, has no numeric identifier; no identifier may be fabricated;
- strict identifiers `03690740406` and `04581460260` each occur in two distinct source observations with different current-state evidence and therefore must not be deduplicated by identifier alone;
- all 749 blocks carry one `Provv. ... Scadenza ...` source line and one `Sezioni.: I II III IV V VI VII VIII IX X` line;
- 600 observations carry both a decision/provvedimento date and an expiry date;
- 314 observations carry a separate current-status date line (`DAL`, `AL` or an unprefixed date);
- one `pdfplumber` layout extraction emits `(cid:9)` before the AQUAMET name for identifier `02161921008`; only this exact reviewed extraction artefact is eligible for a localised reconciliation. Broad `(cid:...)` stripping is prohibited.

These denominators independently reconcile the legend-aware status counts in the extracted document: 145 occurrences of `AVVIO ISTRUTTORIA` include one legend occurrence, leaving 144 records, while `IN AGGIORNAMENTO` occurs on 204 records.

## Population treatment

The official surface is treated as a **single combined publication**, not as an invented listed series plus an applicant series. The parser mapping is evidence-backed and fail-closed:

- explicit `AVVIO ISTRUTTORIA` → `pending`;
- explicit `IN AGGIORNAMENTO` → `renewal_update_in_progress`;
- no explicit current-state marker + complete listed provvedimento/date structure → `listed`;
- any unknown status marker, changed structure, asymmetric dates, unreviewed identifier shape or changed denominator must fail validation rather than being inferred or repaired.

The parser preserves the raw 10-digit/blank identifiers without promoting them to canonical identifiers and preserves the two duplicate strict identifiers as separate observations.

## Parser checkpoint

A permanent candidate parser now exists at `src/white_list_archive/parsers/forli_cesena_combined.py`, with permanent semantic tests in `tests/test_forli_cesena_parser_semantics.py`. It is designed against the byte-pinned 11 September edition and asserts the 69-page / 749-observation / 401+204+144 denominators, the reviewed identifier exceptions, duplicate-identifier evidence, provvedimento-date denominator and the single reviewed AQUAMET extraction artefact. Its source-specific fields are constrained to the existing public-record contract rather than widening that contract.

The independent full-source parser-validation workflow is still the gate for changing canonical coverage. Until it succeeds on the exact pinned PDF, do not set `parser_validated`, `observations_loaded`, `population_scopes_complete` or `public_export_enabled`.

## Canonical state constraints

At this checkpoint:

- the current PDF is content-addressed and repeat-fetch verified;
- row/population denominators are reconciled to 749 observations;
- parser implementation and permanent semantic invariants exist;
- canonical coverage remains unchanged while full-source parser validation is pending;
- no national/public integration is yet justified;
- no inferred `NOT_PUBLISHED`, fabricated applicant series, identifier repair or identifier-level deduplication is permitted.

## Next gate

Resume `expansion/forli-cesena-2026-09-13` and inspect the full-source parser-validation result. If it validates the exact pinned PDF and the public-field contract for all 749 observations, freeze that result in this note, then bind the parser/source configuration and perform the canonical/national materialisation with the complete repository test suite and public-registry build. If it fails, preserve the exact failure and correct only the evidence-backed parser/layout assumption on this same branch.

A failed later fetch remains an execution limitation, not evidence of non-publication or incompleteness.
