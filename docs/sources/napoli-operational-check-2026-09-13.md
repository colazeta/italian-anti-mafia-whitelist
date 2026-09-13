# Napoli White List operational check — 2026-09-13

## Scope

Expansion reconnaissance for the current public White List publications of the Prefettura di Napoli. This note records only source-positive facts observed from official publication surfaces. It does not establish byte identity, parser validity, row counts, completeness beyond the positively identified populations, or public-integration readiness until the corresponding gates are completed.

## Current official publication surfaces

The Prefettura publishes the two required populations on distinct official pages:

- listed companies: `https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-iscritte`;
- applicant companies: `https://prefettura.interno.gov.it/it/prefetture/napoli/white-list-elenco-imprese-richiedenti`.

A live retrieval on 13 September 2026 exposed current attachments dated 11 September 2026:

- listed: `IMPRESE ISCRITTE WHITE-LIST 11_9_2026`, resource `https://prefettura.interno.gov.it/sites/default/files/79/2026-09/whitelistprefnapoli_11_settembre_26.pdf`;
- applicants: `WHITE-LIST RICHIEDENTI 11_9_2026`, resource `https://prefettura.interno.gov.it/sites/default/files/79/2026-09/ditterichiedenti_wl_11_settembre_26.pdf`.

The applicant page positively states that the published applicant list contains the references of all firms that submitted a formal request for White List registration. The listed page positively identifies its attachment as the list of firms registered in the Prefettura's White List. No population status is inferred from search absence or retrieval failure.

## Capture gate

Byte-level capture is still pending at this checkpoint. Before either source can be admitted to publication configuration, the expansion must establish for each current attachment:

1. successful direct acquisition from the official resource URL;
2. valid PDF identity;
3. two independent retrievals with identical bytes;
4. SHA-256 and byte size;
5. page/layout diagnostics sufficient to bind or implement a fail-closed parser;
6. reviewed source-row and semantic invariants before any company-observation count is declared.

Until those checks pass, no SHA-256, record denominator, parser binding, national-count increment or public-export state is asserted here.
