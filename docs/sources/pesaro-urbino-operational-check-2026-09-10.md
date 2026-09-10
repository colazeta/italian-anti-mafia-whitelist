# Pesaro-Urbino White List operational check — 10 September 2026

## Official publication surface

The current official Prefettura di Pesaro e Urbino page is:

`https://prefettura.interno.gov.it/it/prefetture/pesaro-urbino/white-list-elenco-imprese-iscritte`

The page was verified directly on 10 September 2026. It identifies the White List publication and states that the publication covers companies enrolled and companies requesting enrolment. The current linked attachment is labelled **“Elenco imprese iscritte \"white list\" Pesaro Urbino - aggiornamento 31.08.2026”**.

The attachment itself is titled **“Elenco delle imprese iscritte e di quelle richiedenti l'iscrizione nelle White List provinciali di Pesaro Urbino”** and states **“Aggiornato al 31 agosto 2026”**. These are positive source-level signals that the publication surface is a combined listed/requesting series. They do not, by themselves, justify assigning an applicant status to individual rows without a row-level source marker.

## Current byte identity

- resource: `https://prefettura.interno.gov.it/sites/default/files/72/2026-08/elenco-wl-ditte-iscritte-31.08.2026.pdf`;
- content type: `application/pdf`;
- SHA-256: `7cadfb4d4473f9100691793b0b695d0c71bf93eebf7b7351060b28196dbe149a`;
- size observed: 685,269 bytes;
- pages: 21.

The resource is therefore treated as a byte-pinned edition. A changed byte identity must fail the public build until the new edition is re-audited.

## Table structure and row count

The PDF has one stable company table on every page. The primary columns are:

1. `Ragione Sociale`;
2. `Sede legale`;
3. `Codice Fiscale / Partita IVA`;
4. `Data iscrizione`;
5. `Data scadenza iscrizione`;
6. `Sezioni`;
7. `Aggiornamento in corso`.

The page-level data-row counts are:

`10, 24, 24, 24, 24, 24, 24, 24, 24, 24, 24, 24, 24, 24, 24, 24, 24, 24, 24, 24, 18`

This yields **484 source rows**.

The audited row shapes are:

- **406** rows with an explicit listing-date and expiry-date pair and no update marker;
- **42** rows with an explicit listing-date and expiry-date pair plus `X` in `Aggiornamento in corso`;
- **36** rows without a listing/expiry pair but with `X` in `Aggiornamento in corso`;
- **0** rows with neither a date pair nor an update marker.

The parser therefore maps an explicit date pair without `X` to `listed`, while `X` is represented conservatively as `renewal_update_in_progress`. It does **not** infer `pending` or applicant status from blank dates. This is intentional: the document title establishes a combined source population, but the table does not expose a separate row-level applicant flag.

## Conservative data handling

Two source date pairs use dot separators rather than slash separators. The parser accepts both explicit `DD/MM/YYYY` and `DD.MM.YYYY` typography and normalises them to ISO without changing source digits; the raw source forms remain in provenance.

The current attachment contains 388 eleven-digit numeric identifiers and 94 sixteen-character alphanumeric identifiers that meet the normalisation contract. Two source identifier fields have longer compound forms. They remain only in `identifier_field_raw`; they are not padded, truncated, split or otherwise repaired by inference.

One row has no section value. The observation is retained with an empty activity list rather than assigning a neighbouring or inferred section.

## Fail-closed boundaries

The approved parser requires:

- exactly 21 pages;
- exactly one company table per page with the audited header structure;
- exactly 484 source rows;
- non-empty name, registered office and raw identifier for every row;
- complete date pairs when dates are present;
- only explicit `X` as the update marker;
- no row lacking both a date pair and an update marker.

Any violation stops publication and requires a new source audit. The parser does not treat failed extraction, blank cells or missing fields as evidence of a legal status.
