# Napoli White List operational check — 2026-09-13

## Scope

Expansion work for the current public White List publications of the Prefettura di Napoli. This note records only source-positive facts observed from official publication surfaces and byte-level capture. Parser validity, reviewed row denominators and public-integration readiness remain gated separately until established below.

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

`pdfinfo` and layout-text extraction succeeded for both byte-pinned publications. The extracted source itself is dated `Napoli, 11 settembre 2026`. The listed document visibly numbers its observations through 2,259; the applicant document states that it covers complete applications received through 9 September 2026 and visibly numbers observations through 2,571. Those terminal ordinals are reconnaissance evidence only at this stage: production record denominators will be frozen only after parser-family/layout validation establishes row boundaries and reviewed exceptions across every page.

## Conservative semantic boundary

The current listed publication exposes company identity, legal/secondary seat, fiscal identifier, requested/registered activities, registration date, registration/renewal deadline and an `Aggiornamento in corso` field. Any mapping of the latter to a canonical status must be based on reviewed source-positive lexemes rather than blank/nonblank inference alone.

The current applicant publication positively defines the applicant population and exposes company identity, legal/secondary seat, fiscal identifier, requested activities, application date and an `ESITO` field. Applicant membership itself supports `pending` only for rows successfully parsed from this explicitly identified applicant publication; source outcome text must still be preserved verbatim.

## Remaining gates

Before admission to publication configuration the expansion still must establish:

1. full-page table/layout invariants and reviewed exception classes;
2. a fail-closed parser family bound to both pinned SHA-256 values and the 11 September 2026 source edition;
3. exact company-observation denominators, status distributions and identifier coverage from the complete sources;
4. parser semantic tests and repository CI;
5. canonical/public national integration and permanent browser/Pages gates.

No national-count increment or public-export state is asserted until those gates pass.
