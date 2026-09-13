# Forlì-Cesena operational source check — 2026-09-13

## Scope

This note freezes the official-source, byte-capture and parser-validation evidence used for the Forlì-Cesena national-expansion candidate. Publication approval still requires the national integration, repository and public-portal gates.

## Current official publication surface

Official Prefettura landing page:

- https://prefettura.interno.gov.it/it/prefetture/forli-cesena/evidenza/white-list

The page was verified on 2026-09-13. It exposes one current attachment labelled **“White list dell'11 settembre 2026”** (473.63 KB) and reports a page update timestamp of **11 September 2026, 13:22**.

Current official attachment:

- https://prefettura.interno.gov.it/sites/default/files/44/2026-09/wlp-al-11-09-2026.pdf
- stated edition date: 2026-09-11

The publication itself provides the semantics needed for the two non-default current-state markers: `AVVIO ISTRUTTORIA` is the application/instruction-stage population and `IN AGGIORNAMENTO` is the renewal/update population. Rows without either current-state marker retain populated enrolment provvedimento/expiry fields and are treated as listed only after structural validation.

## Content-addressed capture

The branch-local source audit fetched the exact official PDF twice from the Prefettura endpoint through the GitHub runner. Both responses were HTTP 200, valid PDF files and byte-identical:

- byte size: `485001`
- SHA-256 fetch A: `f18e1980e6f7f5bc2ac55a55926ab7a221f290fc7a40f5d0781eef4885455468`
- SHA-256 fetch B: `f18e1980e6f7f5bc2ac55a55926ab7a221f290fc7a40f5d0781eef4885455468`
- byte identity: `true`

A layout-preserving extraction from those pinned bytes established:

- 69 pages;
- layout-text SHA-256 `69df0461a19e6aae14aecfd2ff4d69ae328f9122c00231c4566427daae745d03`;
- no extractable ruled tables under `pdfplumber.extract_tables()`, so a table-family parser is not appropriate for this edition.

## Row and population reconciliation

The full-source parser validation reconciles the pinned edition to exactly **749 source observations**:

- 401 `listed` observations;
- 204 observations explicitly marked `IN AGGIORNAMENTO`, mapped to `renewal_update_in_progress`;
- 144 observations explicitly marked `AVVIO ISTRUTTORIA`, mapped to `pending`;
- 747 observations contain a strict 11-digit identifier;
- one source row contains the 10-digit token `0543034730` for `V8 TRASPORTI & LOGISTICA SRL`; it remains raw and is not padded or repaired into a canonical identifier;
- one foreign source row, `GRUPPO IDRODEMOLIZIONI SRL - SOCIETA' ESTERA`, has no numeric identifier; no identifier is fabricated;
- strict identifiers `03690740406` and `04581460260` each occur in two distinct source observations and remain separate observations;
- all 749 logical blocks carry one `Provv. ... Scadenza ...` source line and one `Sezioni.: I II III IV V VI VII VIII IX X` line;
- 600 observations carry both a decision/provvedimento date and an expiry date;
- **320** observations carry a separate current-status date line. Audited source forms include bare dates and the prefixes `DAL`, `DA`, `AL`, `DEL` and `IL`;
- the exact malformed source value `DAL 11/04/20226` is preserved raw, with no inferred or repaired normalised date;
- one `pdfplumber` layout extraction emits `(cid:9)` before the AQUAMET name for identifier `02161921008`; only this exact reviewed extraction artefact is reconciled. Broad `(cid:...)` stripping remains prohibited.

The status denominator also reconciles the document legend: 145 textual occurrences of `AVVIO ISTRUTTORIA` include one legend occurrence, leaving 144 record-level pending observations; `IN AGGIORNAMENTO` occurs on 204 records.

## Population treatment

The official surface is treated as a **single combined publication**, not as an invented listed series plus an applicant series. The mapping is evidence-backed and fail-closed:

- explicit `AVVIO ISTRUTTORIA` → `pending`;
- explicit `IN AGGIORNAMENTO` → `renewal_update_in_progress`;
- no explicit current-state marker + complete listed provvedimento/date structure → `listed`;
- unknown status markers, changed block structure, asymmetric provvedimento dates, unreviewed identifier shapes or changed audited denominators fail validation rather than being inferred or repaired.

Addresses are cleaned and joined conservatively from source text only. The parser does not geocode or infer missing address components.

## Parser validation checkpoint

The permanent parser is `src/white_list_archive/parsers/forli_cesena_combined.py`, with semantic tests in `tests/test_forli_cesena_parser_semantics.py`.

The independent full-source parser-validation gate completed successfully against the exact pinned PDF. The frozen invariants are:

- `parser_gate=VALIDATED`;
- 69 pages;
- 749 public-contract-valid records;
- statuses `401 listed / 204 renewal_update_in_progress / 144 pending`;
- identifier kinds `747 strict_11_digit / 1 reviewed_10_digit_source_exception / 1 reviewed_blank_identifier_foreign_exception`;
- duplicate strict identifiers exactly `03690740406` ×2 and `04581460260` ×2;
- 600 dated provvedimento rows;
- 320 standalone current-status date rows;
- one reviewed AQUAMET CID extraction artefact;
- `fabricated_identifier_rows=0`.

The parser is byte-edition-specific and keeps the reviewed irregular identifier/date values raw where the source itself is irregular. Its source-specific fields fit the existing public-record contract; validation does not widen that contract.

## Canonical-state constraints

At this checkpoint:

- source identification, repeatable byte capture and full-source parser validation are complete;
- the single combined population is defensibly complete for the published 11 September edition;
- canonical/public integration is not considered complete until the national materialisation and full repository/public-registry gates pass;
- canonical hosted-database integration and independently durable evidence remain separate governance work under the existing infrastructure issue and are not inferred from public-source validation;
- no inferred `NOT_PUBLISHED`, fabricated applicant series, identifier repair, date repair or identifier-level deduplication is permitted.

## Next gate

Resume `expansion/forli-cesena-2026-09-13` and complete the transactional national materialisation from this validated source/parser state. The candidate must pass the full repository suite and national public-registry build before any production files are committed. Only after those gates pass should the permanent Pages/browser expectations be updated, temporary expansion workflows and `tmp/forli_cesena_*` artefacts be removed, the branch be audited as production-only and a PR be opened.

A failed later fetch remains an execution limitation, not evidence of non-publication or incompleteness.
