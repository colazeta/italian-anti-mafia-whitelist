# Piacenza White List operational source check — 2026-09-21

## Scope

This checkpoint records the positive official-source evidence used for the Piacenza expansion. It does not infer non-publication, completeness or legal status from search failure. The current official Prefettura landing page positively exposes separate listed and applicant populations.

Official landing page:

- `https://prefettura.interno.gov.it/it/prefetture/piacenza/evidenza/white-list`

The landing page returned HTTP 200 in the direct source probe on 21 September 2026 and exposed exactly the two source links used below.

## Listed population

Official resource:

- `https://prefettura.interno.gov.it/sites/default/files/65/2026-09/ditte-white-list-copia_2.zip`
- link label: `ditte-white-list-copia.zip`
- repeated independent captures: byte-identical
- captured ZIP SHA-256: `e53d2f0a1c044efb2b28adf058893c4d482b2262396f936dc17a93a43f7aaea8`
- captured ZIP size: 44,285 bytes
- ZIP member: `Ditte white list - Copia.xls`

The legacy XLS source contains the official listed table. The audited logical table has 552 source observations. The only observed source status marker in the `Note` field is `IN FASE DI RINNOVO`; blank notes remain listed observations. The observed status boundary is therefore 455 `listed` and 97 `renewal_update_in_progress`.

The source contains malformed or non-standard identifiers and date strings. These are preserved raw and are not repaired by inference. Seven listing-date values and seven expiry-date values are not safely normalisable. Activity values are source section numerals; the reviewed `III.V` source anomaly is preserved rather than silently rewritten.

The official page-level `Ultimo aggiornamento` timestamp is not treated as an edition date for this resource. The attachment is independently content-addressed and the project uses the 21 September 2026 observation/capture date as the reference date rather than inventing a legal or publication date from file metadata.

## Applicant population

Official resource:

- `https://prefettura.interno.gov.it/sites/default/files/65/2026-02/elenco_imprese_richiedenti_l-iscrizione_nell-elenco_dei_fornitori-prestatori_di_servizi_ed_esecutori_di_lavori_non_soggetti_a_tentativi_di_infiltrazione_mafiosa-i.zip`
- link label: `elenco_imprese_richiedenti_l-iscrizione_nell-elenco_dei_fornitori-prestatori_di_servizi_ed_esecutori_di_lavori_non_soggetti_a_tentativi_di_infiltrazione_mafiosa-i.zip`
- repeated independent captures: byte-identical
- captured ZIP SHA-256: `99e2809359df95497ea921fdc69b2c4e826112ab4cd5d31209b38110a3c4d335`
- captured ZIP size: 6,997 bytes
- ZIP member: `ELENCO_IMPRESE_RICHIEDENTI_L'ISCRIZIONE_NELL'ELENCO_DEI_FORNITORI,_PRESTATORI_DI_SERVIZI_ED_ESECUTORI_DI_LAVORI_NON_SOGGETTI_A_TENTATIVI_DI_INFILTRAZIONE_MAFIOSA - Copia.xls`

The applicant workbook contains 18 source-positive applicant observations. All 18 contain a company name, office, identifier, requested section(s) and an application date. Because the current official surface positively identifies these firms as applicants, they map to `pending`; no applicant population or status is inferred from absence or failed search.

The February resource path and workbook metadata are not interpreted as evidence that the current official link is stale or incomplete. The source is treated only as the current applicant population positively exposed by the Prefettura at the time of capture.

## Parser and fail-closed boundary

The Piacenza parser reads the byte-pinned ZIP directly and requires the audited legacy XLS member and workbook/sheet structure. It preserves formatted-but-empty workbook extent without mistaking formatting cells for source observations, requires the reviewed header/title and source-status vocabulary, and fails closed on unknown activity or status values.

Expected current parser boundary after exact-source validation:

- listed observations: 552
- applicant observations: 18
- total observations: 570
- listed: 455
- renewal/update in progress: 97
- pending: 18

No public integration is authorised from this document alone. Publication remains gated on exact-source parser validation, repository tests, national candidate build, public contract/browser gates and post-merge Pages verification.
