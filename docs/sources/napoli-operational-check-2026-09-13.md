# Napoli White List operational check — 2026-09-13

## Scope

Expansion work for the current public White List publications of the Prefettura di Napoli. This note records only source-positive facts observed from official publication surfaces and byte-level capture. Public integration remains gated until source-outcome continuations are fully reviewed and the fail-closed parser is validated.

## Current official publication surfaces

The Prefettura publishes the two required populations on distinct official pages:

- listed companies: `https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-iscritte`;
- applicant companies: `https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-richiedenti`.

A live retrieval on 13 September 2026 exposed current attachments dated 11 September 2026:

- listed: `IMPRESE ISCRITTE WHITE-LIST 11_9_2026`, resource `https://prefettura.interno.gov.it/sites/default/files/79/2026-09/whitelistprefnapoli_11_settembre_26.pdf`;
- applicants: `WHITE-LIST RICHIEDENTI 11_9_2026`, resource `https://prefettura.interno.gov.it/sites/default/files/79/2026-09/ditterichiedenti_wl_11_settembre_26.pdf`.

The applicant page positively states that the published applicant list contains the references of all firms that submitted a formal request for White List registration. The listed page positively identifies its attachment as the list of firms registered in the Prefettura's White List. No population status is inferred from search absence or retrieval failure.

## Byte-level capture

The source-audit gate repeated each direct official-resource fetch twice. Both publications were valid `%PDF-1.7` payloads and each pair was byte-identical:

- listed: 3,081,398 bytes; SHA-256 `93a8635c0bd9b00587f9cc60c52752061bd239a7c16cb34b64a11e495a0ab4be`; 60 pages;
- applicants: 3,566,448 bytes; SHA-256 `053be2500b07a7da536c344aede12084dde9b7cf28b4717af99764cbd05e7e6b`; 215 pages.

`pdfinfo` and layout-text extraction succeeded for both byte-pinned publications. The extracted source itself is dated `Napoli, 11 settembre 2026`; the applicant document states that it covers complete applications received through 9 September 2026.

## Full-layout validation

A full-document audit used the pinned bytes and inspected every page through `pdfplumber` table extraction.

- listed: exactly one table on each of 60 pages; every extracted table row has nine cells; the numbered source rows form the exact, gap-free, non-duplicated sequence 1–2,259;
- applicants: exactly one table on each of 215 pages; every extracted table row has eight cells; the numbered source rows form the exact, gap-free, non-duplicated sequence 1–2,571.

Accordingly **2,259 listed source observations and 2,571 applicant source observations are frozen as the current source-row denominators**. These are not yet promoted as public-record counts until the parser and national integration gates pass.

## Semantic audit and spatial reconstruction

Plain table extraction exposed a small number of vertically misassigned cells. A second reconstruction therefore used the table's x-column geometry, the numbered source-row anchors and row-boundary geometry, on the same pinned bytes. It recovered the complete, ordered sequences 1–2,259 and 1–2,571 and removed the false identity/office gaps without inventing content.

### Listed publication

The spatial reconstruction yields 2,259 numbered observations with nonblank company, office and identifier cells for every numbered row. Identifier evidence is 2,068 eleven-digit values, 167 sixteen-character alphanumeric fiscal-code-shaped values and 24 other raw values. The 24 noncanonical values are preserved as raw-only evidence rather than padded or otherwise repaired.

The reconstructed outcome/update column contains 785 blank cells and 1,474 nonblank cells. The dominant positive update wording is `iscrizione in aggiornamento` (1,375 rows) plus 30 rows with `iscrizione in aggiornamento per variazione societaria`. The remaining nonblank values include source-positive collaborative-prevention, judicial-control/administration, interdittiva/diniego and revocation language, together with several long legal notes that visibly continue across source-row vertical space. Consequently a blanket nonblank→`renewal_update_in_progress` rule is prohibited.

The spatial reconstruction also shows why the plain table result could not be used directly: previously apparent blank identities and offices are recovered from visible words on the source page. Conversely, some long legal/outcome notes are still represented as fragments on neighbouring numbered rows by simple midpoint assignment. Those fragments must be grouped only through an explicitly reviewed continuation rule before their row ownership or canonical status is asserted.

### Applicant publication

The spatial reconstruction yields 2,571 numbered observations with nonblank company, office and identifier cells for every numbered row. Identifier evidence is 2,298 eleven-digit values, 261 sixteen-character alphanumeric values and 12 raw-only values. The raw-only set includes ten-digit values, `CHE-101,989.651`, the source value `011117840767` and `ZZVLR78S46F839J`; no alternative identifier is fabricated.

The reconstructed `ESITO` column contains 2,530 blank rows and 41 nonblank rows. All 41 nonblank values expose explicit adverse administrative wording such as `DINIEGO DI ISCRIZIONE` or `Provvedimento interdittivo`; they therefore cannot be represented as ordinary pending observations merely because they remain physically present in the applicant publication. Any public status assignment must use an existing reviewed repository status/treatment and retain the raw outcome; no new status is introduced ad hoc.

The spatial method corrects the previously observed continuation error around rows 511–513: row 511 retains `DINIEGO DI ISCRIZIONE Provv. 0135353 del 05/07/2017 confermato con provvedimento`; row 512 has a blank outcome; row 513 retains its own `DINIEGO DI ISCRIZIONE Provv. di conferma n.0214725 del 06/06/2024`. One of the 41 applicant outcomes still ends with an apparently incomplete date phrase (`...399217 del`), so complete outcome preservation requires targeted neighbouring-row review before parser promotion.

## Conservative semantic boundary

The listed population is positively identified by its dedicated publication, but membership evidence and current legal/status wording must remain separate. Blank update/outcome text can support ordinary listed treatment; source-positive update wording can support `renewal_update_in_progress`; interdittiva/diniego/revocation/control/administration evidence must not be collapsed into update status and must follow the repository's existing reviewed status semantics after row ownership has been reconstructed.

Applicant membership is positively established by the dedicated applicant publication. Rows with blank `ESITO` are candidates for `pending` once the parser passes its full invariants. The 41 adverse-outcome rows require separate reviewed treatment and complete raw outcome preservation.

## Remaining gates

Before admission to publication configuration the expansion still must establish:

1. deterministic, reviewed continuation ownership for the exceptional listed legal notes and the one apparently truncated applicant outcome;
2. a fail-closed parser family bound to both pinned SHA-256 values and the 11 September 2026 source edition;
3. exact parser status distributions, identifier coverage and exception counters across the complete sources;
4. parser semantic tests and repository CI;
5. canonical/public national integration and permanent browser/Pages gates.

No national-count increment or public-export state is asserted until those gates pass.
