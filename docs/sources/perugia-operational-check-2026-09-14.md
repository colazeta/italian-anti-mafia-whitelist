# Perugia White List operational check — 2026-09-14

## Scope

This note records the current official Prefettura di Perugia White List publication boundary. It is an evidence checkpoint only: no parser, row denominator, legal-status classification or completeness claim is inferred beyond what is positively established below.

## Official publication surface

- Official landing page: `https://prefettura.interno.gov.it/it/prefetture/perugia/evidenza/white-list`
- The official page was directly fetched twice from GitHub Actions on 14 September 2026. Both responses were byte-identical: 118,868 bytes, SHA-256 `9de2ef541d81f5af9905d999fa95e17fdbf05ec8ef8ddcc8a3ce17f055b935d0`.
- The current official page positively exposes two separately labelled populations, both explicitly dated **3 September 2026**:
  - registered companies: “Elenco delle imprese iscritte alle white list al 3 Settembre 2026”;
  - requesting companies: “Elenco delle imprese richiedenti l'iscrizione alle white list al 3 Settembre 2026”.
- The official page reports `Ultimo aggiornamento` as 4 September 2026.

The capture and source-structure evidence was produced by GitHub Actions run `34872232759` (`Perugia source capture`), artifact `perugia-source-capture-1` / artifact id `10359622134`.

## Current registered-company source

- Positive-evidence anchor text: `Elenco delle imprese iscritte alle white list al 3 Settembre 2026`
- Resource URL: `https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-delle-imprese-iscritte-white_list_perugia_0.pdf`
- Media type: `application/pdf`
- Size: **2,279,077 bytes**
- SHA-256: `c9cd39452fb2f751c2b9e105c10ecf0b9e57569006138af7f766d6851748029f`
- PDF pages: **224**
- `pdftotext -layout` lines: 8,221
- Extracted-text SHA-256: `aa4f444cdbeff8829863969a0f3a03970d861ba91ebe010928b525741ac26b2c`
- An independent second GET returned exactly the same byte length and SHA-256.

Initial structural inspection confirms a sectioned table containing company name, legal address, foreign secondary establishment field, fiscal/VAT identifier, registration date, expiry date and an `Aggiornamento in corso` field. These observations do **not** yet establish the logical-row denominator because multi-page continuation rows and repeated section membership must first be audited comprehensively.

## Current requesting-company source

- Positive-evidence anchor text: `Elenco delle imprese richiedenti l'iscrizione alle white list al 3 Settembre 2026`
- Resource URL: `https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-delle-imprese-richiedenti-l-iscrizione_0.pdf`
- Media type: `application/pdf`
- Size: **1,897,032 bytes**
- SHA-256: `003e2ee6614302b1a1f8a504baae2b0c5d38752c70cfb509f693e1b4c1374f14`
- PDF pages: **184**
- `pdftotext -layout` lines: 7,840
- Extracted-text SHA-256: `ef6fe093d28d3725bb517387b7b823e70f0b920fe0f03d6b1978513ac71836b5`
- An independent second GET returned exactly the same byte length and SHA-256.

Initial structural inspection confirms a table containing company name, legal address, foreign secondary establishment field, fiscal/VAT identifier, requested activities, application date and an outcome field. The outcome column visibly includes renewal/registration outcomes as well as rows without a displayed outcome near the current tail. Accordingly, this source must not be treated mechanically as `pending`: row-level source semantics require an exhaustive audit before status mapping.

## Methodological boundary

The official source positively establishes both the listed and requesting-company series and therefore supports a defensible two-population Perugia treatment. The following remain deliberately unresolved at this checkpoint:

- exact physical and logical row denominators;
- treatment of cross-page continuation fragments;
- whether repeated companies across statutory sections represent one or multiple source observations under the project observation model;
- the complete finite vocabulary and distribution of requesting-company outcomes;
- any malformed identifiers/dates, chronology anomalies or extraction losses;
- parser family and fail-closed source bindings;
- company-observation loading and national/public integration.

No `NOT_PUBLISHED`, status, completeness or record-count conclusion is inferred from search or from partial extraction. The next gate is a full structure/row audit against these exact byte-pinned PDFs.
