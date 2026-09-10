# Bari operational source check — 10 September 2026

## Current official publication

The official Prefettura di Bari White List landing page was independently re-resolved from a GitHub-hosted runner on 10 September 2026 with HTTP 200. It positively exposes both current ordinary White List populations and labels both editions **31/08/2026**:

- **Elenco società iscritte al 31/08/2026** — 29-page PDF, SHA-256 `a28fe31e102e601ea0253c3fc93c559c3f964dd28d5cfa55c64e9c309a5517d9`.
- **Elenco richieste di iscrizione al 31/08/2026** — 14-page PDF, SHA-256 `9164ec87debb629291415f0eaf125ee35fd191775466b3582e9e34dea78cf36d`.

Landing page: `https://prefettura.interno.gov.it/it/prefetture/bari/evidenza/white-list`.

The two resources are treated as byte-pinned current editions. A failed fetch from another execution environment is not treated as evidence of non-publication or incompleteness.

## Reviewed logical-row boundary

`pdfplumber` identifies one table per page. Each table contains two non-company administrative rows after the outer page header: the document title and the column header. Those rows are excluded before determining company denominators. The reviewed logical populations are therefore:

- **1,065 listed-population observations** across 29 pages;
- **605 applicant observations** across 14 pages.

The applicant population is complete on the current official surface: all 605 observations have explicit `in istruttoria`/`IN ISTRUTTORIA` source status and are mapped to `pending`.

The listed population contains 753 directly labelled `ISCRITTA`/`iscritta`, 301 variants of `richiesta permanenza`, eight `IN AGGIORNAMENTO`, and three extracted blank-status rows. Physical-row review resolves one blank as `MEDITRANS SRL` with visible `richiesta PERMANENZA`; `RECIKLA S.R.L.` has an explicit `SI` permanence marker and is therefore mapped to `renewal_update_in_progress`; `SAP SRL` belongs to the official listed population and has positive listing/expiry dates, so its reviewed blank status is mapped to `listed`. The resulting reviewed distribution is **754 `listed` + 311 `renewal_update_in_progress` = 1,065**.

## Extraction exceptions and conservative treatment

A small set of rows is visually complete but split by PDF table geometry. Repairs are allowed only at exact page/company-row coordinates and are frozen in the Bari parser. They restore the text visibly present in the same physical row bands, including the MEDITRANS/MEIT split on listed page 19 and the TRIDENTE/TRIVEL/UNICA split on applicant page 14. Six further listed legal names and one applicant legal name are restored from their same-row physical text. Any new split or changed coordinate fails closed.

One applicant observation on page 1 (CF/P.IVA `07906600726`, Bari, Corso Vittorio Emanuele II n. 48) has no recoverable legal-name text in the source extraction; the legal name is deliberately left blank rather than inferred. `ROADTEK SRLS` has no recoverable identifier and likewise retains an empty raw identifier. The `UNIEXPRESS SRL - 08439559727` legal-name field and its separate identifier-column value `08439550727` are preserved exactly as published rather than reconciled.

A further applicant exception was independently reviewed after the parser failed closed on a missing sector marker. Applicant page 8, company row 29 (`INNOVATEC SRL`, CF/P.IVA `07937450729`, application date `26/07/2017`) contains no `X` in any of the ten sector columns in the byte-pinned PDF. Word-level inspection of the exact physical row band confirmed that the neighbouring `X` belongs to the preceding `INDUSTRIE FRACCHIOLLA SPA` row, not to INNOVATEC. The parser therefore preserves INNOVATEC with an empty activity/sector list and records exactly one reviewed sectorless applicant row in its diagnostics; it does not infer a sector. Any other applicant or listed row with all ten sector markers empty continues to fail closed.

Seven malformed or calendar-invalid listed date strings are retained verbatim in provenance and not repaired: `06/'3/2025`, `02/07/024`, `1607/2025`, `19+/06/2027`, `28/01/207`, `04/30/2025`, and `37/04/2027`. The applicant string `18/07/18 - 11/05/23` is handled identically. Blank source dates remain blank. Any other non-empty malformed or calendar-invalid date fails closed.

Identifier normalisation accepts only already-valid contiguous 11-digit numeric or 16-character alphanumeric identifiers found in the raw identifier field. It never pads, truncates or reconstructs an identifier. The complete raw field is always retained.

## Publication boundary

The public archive uses these source-backed observations without claiming national legal-entity deduplication. Canonical hosted-database integration and independent durable-evidence verification remain separately governed under issue #16 and are not implied by this public-source validation.
