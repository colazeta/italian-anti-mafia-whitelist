# Ravenna operational source check — 20 September 2026

## Current official publication

- Authority: Prefettura di Ravenna.
- Verified landing page: https://prefettura.interno.gov.it/it/prefetture/ravenna/evidenza/white-list
- The landing page returned HTTP 200 in the source probe and exposed exactly one current attachment labelled **Nuova tabella unica aggiornata**.
- Current attachment: https://prefettura.interno.gov.it/sites/default/files/64/2026-09/nuova_tabella_unica_17-sett-2026.pdf
- Attachment date represented by the official file name: **17 September 2026**.
- Two independent cache-bypassed GETs returned 2,235,879 bytes each and were byte-identical.
- SHA-256: `8d249118ca1fc90cb744a5a630a3c991eee44a963576a031596c9209910ac555`.
- PDF extent: 29 pages.

## Population model

Ravenna publishes one combined current table rather than distinct listed-company and applicant attachments. The table itself positively exposes `DATA PRIMA RICHIESTA`, `DATA ISCRIZIONE/RINNOVO`, `NOTE` and statutory sections I–X. The approved publication series is therefore `ravenna-combined` with population scope `listed_and_applicant`; no separate applicant publication is inferred from search results or from an absent second attachment.

The complete audited source boundary is **706 logical rows**. The permanent fail-closed parser produces exactly:

- **430** `listed`;
- **212** `renewal_update_in_progress`;
- **63** `pending`;
- **1** `other_or_unknown`;
- **692/706** records with at least one structurally valid identifier;
- **706/706** unique record locators;
- **0** dropped source rows.

`pending` is assigned only where the row positively contains a first-application date while the registration/renewal field is absent. The two explicit renewal-note spellings are classified as renewal/update in progress. The remaining explicit judicial-control note is retained as `other_or_unknown` rather than receiving an inferred legal effect.

## Reviewed source anomalies

One table-extraction boundary miss affects progressive 1199 on page 26. The table extractor leaves the company-name cell blank while the same byte-pinned page text contains `RESOLVE SALVAGE & FIRE (NETHERLANDS) B.V.`. The parser repairs only this exact reviewed signature, and fails closed if the page number, row shape, address, application date, section marker or same-page text signature changes. This is an extraction repair from the identical source bytes, not an inferred company identity.

One malformed application-date token, `23/06/026`, is preserved in provenance and deliberately left unnormalised. Fourteen rows lack a structurally valid identifier after conservative extraction; their raw company identity remains unchanged. No digit padding, truncation or identifier reconstruction is performed.

## Integration contract

- Parser: `src/white_list_archive/parsers/ravenna_combined.py` (`ravenna_combined`, version 1).
- Parser semantic tests: `tests/test_ravenna_parser_semantics.py`.
- Source registry: `data/source_registry/source_series_inventory.csv` and `verified_primary_pages.csv`.
- Publication configuration: `data/publication/multi_prefecture_pilot.json`.
- Public observation layer: `public_source_observations`.
- Hosted-database canonical integration remains **not validated**; public source validation must not be represented as durable-evidence or canonical-database validation.

The expected public national candidate after Ravenna is **72,456 records / 70 mapped and published authorities / 73 registers**, subject to the national builder, browser acceptance and Pages gates.
