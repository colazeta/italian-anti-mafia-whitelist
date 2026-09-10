# Avellino White List operational check — 10 September 2026

## Official publication surfaces

The Prefettura di Avellino exposes two distinct current official series:

- listed companies: `https://prefettura.interno.gov.it/it/prefetture/avellino/white-list-elenco-imprese-iscritte`;
- companies requesting registration: `https://prefettura.interno.gov.it/it/prefetture/avellino/white-list-elenco-imprese-richiedenti`.

Both pages were resolved directly from the official Ministry domain on 10 September 2026. Their current attachment labels explicitly identify an edition at **1 September 2026**.

## Current byte identities

Listed population:

- resource: `https://prefettura.interno.gov.it/sites/default/files/24/2026-09/per_pubblicazione_iscritte_av_01-09-2026_note.pdf`;
- SHA-256: `9ada9195d72ba3b773448df0f0f46bab5efdd72ad7da35236bad389ad860eaf0`;
- size observed by the source audit: 990,198 bytes;
- PDF pages: 9.

Applicant population:

- resource: `https://prefettura.interno.gov.it/sites/default/files/24/2026-09/per_pubblicazione_richiedenti_iscrizione_av_01-09-2026.pdf`;
- SHA-256: `b541e057787e9d26982eb1e87c1233002e88a376e865b637d223c027a6b210be`;
- size observed by the source audit: 387,247 bytes;
- PDF pages: 5.

## Parser boundary

The source PDFs expose positioned text but do not yield their substantive rows through the repository's ordinary `pdfplumber.extract_tables()` path. A dedicated positioned-text parser is therefore used. It is bound to the byte-pinned current sources and fails closed on page-count changes, ambiguous primary-date anchors, missing essential identity fields, invalid primary dates or unexpected row counts.

For the listed PDF, the source's `Data scadenza` column is used as the row anchor. This yields **383 complete listed observations**, with the approved public fields: name, raw identifier, registered office, activities, source expiry date and the source update field retained as `outcome_raw`. The source page itself explicitly defines this as the registered-company population. Free-text notes and page-layout metadata remain outside the public contract, and no free-text field is interpreted to manufacture a different legal status. Canonical identifier extraction succeeds for 381 observations; the remaining two retain their raw identifier field without repair.

For the applicant PDF, the source's application-date column yields **244 complete request observations**. All are represented as `pending` because the dedicated applicant publication does not itself establish a final outcome. Canonical identifier extraction succeeds for 243 observations; the remaining raw identifier is retained without repair.

## Verification evidence

- source-resolution and structural audit: successful Actions run `34420174051`;
- aggregate positioned-layout audit: successful Actions run `34420703937`;
- parser semantic tests plus execution against both pinned official PDFs: successful Actions run `34420996848`;
- semantic unit tests: `tests/test_avellino_parser_semantics.py`.

No claim is made here that the Avellino observations have been integrated into the separately governed hosted canonical database or independently durable evidence store. Those controls remain under issue #16 and are not prerequisites for the source-backed public observation layer.
