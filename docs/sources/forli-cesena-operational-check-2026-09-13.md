# Forlì-Cesena operational source check — 2026-09-13

## Scope

This note records source reconnaissance for the next national-expansion candidate. It is **not** publication approval and does not mark Forlì-Cesena as validated, captured or complete.

## Current official publication surface

Official Prefettura landing page:

- https://prefettura.interno.gov.it/it/prefetture/forli-cesena/evidenza/white-list

The current page was verified on 2026-09-13. It exposes one current attachment labelled **“White list dell'11 settembre 2026”** (473.63 KB) and reports a page update timestamp of **11 September 2026, 13:22**.

Current official attachment identified from that page:

- https://prefettura.interno.gov.it/sites/default/files/44/2026-09/wlp-al-11-09-2026.pdf
- stated edition date: 2026-09-11

A live semantic PDF extraction during the same check exposed 69 pages. The document positively contains multiple official state labels, including `ISCRITTA`, `RINNOVO`, `AGGIORNAMENTO` and `AVVIO ISTRUTTORIA`. This is positive evidence that the current attachment is not merely a clean list of enrolled firms: it also carries records in an instruction/application-stage state.

## Population treatment

The current evidence supports treating the attachment provisionally as a **combined publication surface** pending row-level validation. In particular:

- do not infer that applicant records are `NOT_PUBLISHED`;
- do not invent a separate applicant series merely because the landing page exposes a single attachment;
- do not yet set `population_scopes_complete=true`;
- enumerate all distinct official status labels and their row semantics before binding canonical statuses;
- preserve source status text and ambiguous/negative outcomes until an evidence-backed mapping is reviewed.

## Byte-level evidence still required

The current run did **not** complete the content-addressed capture gate. Raw PDF download through the available direct-download path was blocked by the execution environment, and the temporary branch-local audit workflow had not executed at checkpoint time.

Therefore, at this checkpoint:

- no SHA-256 is asserted for the 2026-09-11 PDF;
- `source_verified`, `capture_completed`, `parser_validated`, `observations_loaded` and `public_export_enabled` must remain false in canonical coverage state;
- no record count is asserted;
- no parser-family binding is approved;
- no national/public integration is justified.

## Next gate

Resume `expansion/forli-cesena-2026-09-13` and:

1. fetch the exact official PDF bytes twice through an independently repeatable route;
2. require matching SHA-256 values and byte identity;
3. freeze byte size/page count and a layout-preserving text extraction;
4. enumerate every observed official status and identify the row boundaries/columns used by each status;
5. confirm whether all relevant listed/renewal/update/instruction populations are represented in the single edition;
6. only then bind or implement a fail-closed parser and add semantic invariants before any canonical/public loading.

A failed fetch must remain an execution limitation, not evidence of non-publication or incompleteness.
