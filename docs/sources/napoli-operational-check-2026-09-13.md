# Napoli White List operational check — 2026-09-13

## Scope

Expansion work for the current public White List publications of the Prefettura di Napoli. This note records only source-positive facts observed from official publication surfaces and byte-level capture. Public integration remains gated until source-layout exceptions are reconstructed and the fail-closed parser is fully validated.

## Current official publication surfaces

The Prefettura publishes the two required populations on distinct official pages:

- listed companies: `https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-iscritte`;
- applicant companies: `https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-richiedenti`.

A live retrieval on 13 September 2026 exposed current attachments dated 11 September 2026:

- listed: `IMPRESE ISCRITTE WHITE-LIST 11_9_2026`, resource `https://prefettura.interno.gov.it/sites/default/files/79/2026-09/whitelistprefnapoli_11_settembre_26.pdf`;
- applicants: `WHITE-LIST RICHIEDENTI 11_9_2026`, resource `https://prefettura.interno.gov.it/sites/default/files/79/2026-09/ditterichiedenti_wl_11_settembre_26.pdf`.

The applicant page positively states that the published applicant list contains the references of all firms that submitted a formal request for White List registration. The listed page positively identifies its attachment as the list of firms registered in the Prefettura's White List. No population status is inferred from search absence or retrieval failure.

## Byte-level capture

The temporary source-audit gate repeated each direct official-resource fetch twice. Both publications were valid `%PDF-1.7` payloads and each pair was byte-identical:

- listed: 3,081,398 bytes; SHA-256 `93a8635c0bd9b00587f9cc60c52752061bd239a7c16cb34b64a11e495a0ab4be`; 60 pages;
- applicants: 3,566,448 bytes; SHA-256 `053be2500b07a7da536c344aede12084dde9b7cf28b4717af99764cbd05e7e6b`; 215 pages.

`pdfinfo` and layout-text extraction succeeded for both byte-pinned publications. The extracted source itself is dated `Napoli, 11 settembre 2026`; the applicant document states that it covers complete applications received through 9 September 2026.

## Full-layout validation

A second full-document audit used the pinned bytes and inspected every page through `pdfplumber` table extraction.

- listed: exactly one table on each of 60 pages; every extracted table row has nine cells; the numbered source rows form the exact, gap-free, non-duplicated sequence 1–2,259;
- applicants: exactly one table on each of 215 pages; every extracted table row has eight cells; the numbered source rows form the exact, gap-free, non-duplicated sequence 1–2,571.

Accordingly **2,259 listed source observations and 2,571 applicant source observations are now frozen as the current source-row denominators**. These are not yet promoted as public-record counts because the semantic audit identified a small but material set of cell-assignment exceptions that the parser must reconstruct rather than silently accept.

## Semantic audit and reviewed parser boundary

The all-row semantic audit confirmed the following extraction diagnostics.

### Listed publication

- 2,259 numbered source rows;
- 2,235 identifiers already match an 11-digit VAT/fiscal-number shape or a 16-character fiscal-code shape; 24 source identifiers are ten-digit raw values and must remain raw-only unless independently resolved;
- five registration-date cells are blank and one extracted value is malformed (`14/0319`);
- three expiry/update-date cells are blank; seven rows expose the source phrase `Iscrizione valida per la durata dell'amministrazione giudiziaria` in that date column rather than a date;
- 792 outcome/update cells are blank and 1,467 are nonblank. The nonblank values include update-in-progress wording as well as positive legal/administrative evidence such as collaborative prevention measures, judicial control/administration, interdittive/diniego wording and revocations. No blanket nonblank→update mapping is therefore permitted;
- seven activity strings and 24 identifier strings fall outside the strict canonical shapes and must be preserved verbatim while any normalised derivation remains conservative;
- plain table extraction reports 17 numbered rows with an empty company-name cell and five with an empty registered-office cell. Layout inspection confirms that at least the reviewed page-boundary examples contain visible company/office text whose cell assignment was lost by table extraction. A parser that publishes blank identities from those cells would be incorrect.

### Applicant publication

- 2,571 numbered source rows;
- 2,559 identifiers match the strict identifier shapes; 12 remain raw-only, including ten-digit values, one foreign-style value (`CHE-101,989.651`) and one 12-digit raw value;
- 2,570 application dates parse as valid source dates and one date cell is blank;
- two activity cells are blank and six activity spellings/layout forms require raw preservation;
- 2,527 `ESITO` cells are blank. Forty-four extracted cells are nonblank, predominantly interdittiva/diniego evidence. At least some long outcome text visually spans more than one table row: for example the text associated with source row 511 continues with `provvedimento` above row 512, while basic table extraction assigns that fragment to row 512. Outcome reconstruction must therefore use reviewed spatial/continuation evidence rather than accept each extracted outcome cell at face value.

## Conservative semantic boundary

The listed population must preserve its positive membership evidence while separately interpreting reviewed status/outcome wording. Blank update/outcome text can support `listed`; reviewed `iscrizione in aggiornamento` wording can support `renewal_update_in_progress`; interdittiva/diniego/revocation/control/administration wording must not be collapsed into that status and requires an explicit reviewed mapping or conservative `other_or_unknown` treatment consistent with the repository taxonomy.

Applicant membership is positively established by the dedicated applicant publication, but a nonblank `ESITO` containing denial/interdiction evidence cannot be represented as ordinary pending merely because the row remains in that publication. The parser must reconstruct outcome continuations first, preserve the complete raw outcome, and map only source-positive semantics.

## Remaining gates

Before admission to publication configuration the expansion still must establish:

1. deterministic reconstruction for the listed identity/office cell-assignment exceptions and applicant outcome continuations;
2. a fail-closed parser family bound to both pinned SHA-256 values and the 11 September 2026 source edition;
3. exact parser status distributions, identifier coverage and reviewed exception counters across the complete sources;
4. parser semantic tests and repository CI;
5. canonical/public national integration and permanent browser/Pages gates.

No national-count increment or public-export state is asserted until those gates pass.
