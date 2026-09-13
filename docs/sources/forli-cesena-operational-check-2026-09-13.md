# Forlì-Cesena operational source check — 2026-09-13

## Scope

This note records source reconnaissance for the next national-expansion candidate. It is **not** publication approval and does not yet mark Forlì-Cesena as parser-validated, complete or publicly integrated.

## Current official publication surface

Official Prefettura landing page:

- https://prefettura.interno.gov.it/it/prefetture/forli-cesena/evidenza/white-list

The current page was verified on 2026-09-13. It exposes one current attachment labelled **“White list dell'11 settembre 2026”** (473.63 KB) and reports a page update timestamp of **11 September 2026, 13:22**.

Current official attachment identified from that page:

- https://prefettura.interno.gov.it/sites/default/files/44/2026-09/wlp-al-11-09-2026.pdf
- stated edition date: 2026-09-11

A live semantic PDF extraction during the initial reconnaissance exposed 69 pages. The document positively contains multiple official state labels, including `ISCRITTA`, `RINNOVO`, `AGGIORNAMENTO` and `AVVIO ISTRUTTORIA`. This is positive evidence that the current attachment is not merely a clean list of enrolled firms: it also carries records in an instruction/application-stage state.

## Content-addressed capture

The branch-local source audit subsequently fetched the exact official PDF twice from the Prefettura endpoint through the GitHub runner. Both responses were HTTP 200, valid PDF files and byte-identical:

- byte size: `485001`
- SHA-256 fetch A: `f18e1980e6f7f5bc2ac55a55926ab7a221f290fc7a40f5d0781eef4885455468`
- SHA-256 fetch B: `f18e1980e6f7f5bc2ac55a55926ab7a221f290fc7a40f5d0781eef4885455468`
- byte identity: `true`

This is sufficient to freeze the current edition's raw-byte identity. The first capture runner did not have the PDF text utilities needed for a layout-preserving extraction, so row semantics, page count from the captured bytes and parser binding remain separate gates rather than being inferred from the successful byte capture.

## Population treatment

The current evidence supports treating the attachment provisionally as a **combined publication surface** pending row-level validation. In particular:

- do not infer that applicant records are `NOT_PUBLISHED`;
- do not invent a separate applicant series merely because the landing page exposes a single attachment;
- do not yet set `population_scopes_complete=true`;
- enumerate all distinct official status labels and their row semantics before binding canonical statuses;
- preserve source status text and ambiguous/negative outcomes until an evidence-backed mapping is reviewed.

## Canonical state constraints

At this checkpoint:

- the current PDF is content-addressed and repeat-fetch verified;
- `source_verified` may be supported for this exact edition, but no canonical coverage transition should be committed until the population and parser gates are complete;
- `parser_validated`, `observations_loaded` and `public_export_enabled` must remain false;
- no canonical record count is asserted;
- no parser-family binding is approved;
- no national/public integration is justified.

## Next gate

Resume `expansion/forli-cesena-2026-09-13` and:

1. reproduce a layout-preserving text extraction from the byte-pinned PDF and freeze page count/text diagnostics;
2. enumerate every observed official status and identify the row boundaries/columns used by each status;
3. confirm whether all relevant listed/renewal/update/instruction populations are represented in the single edition;
4. identify source anomalies that must remain raw or be handled by explicit evidence-backed exceptions;
5. only then bind or implement a fail-closed parser and add semantic invariants before any canonical/public loading.

A failed later fetch must remain an execution limitation, not evidence of non-publication or incompleteness.
