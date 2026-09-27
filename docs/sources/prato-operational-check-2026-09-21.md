# Prato White List operational source check — current boundary verified 2026-09-22

The Prefettura di Prato official White List landing page positively exposes separate listed-company and applicant series. On 22 September 2026 both dedicated official series pages resolved to attachments dated 21 September 2026. Each selected attachment was fetched twice with independent cache-busting requests; both pairs were byte-identical. No legal effect, non-publication or completeness is inferred from failed search.

## Listed population

Official series page: `https://prefettura.interno.gov.it/it/prefetture/prato/white-list-elenco-imprese-iscritte`. Current resource: `https://prefettura.interno.gov.it/sites/default/files/78/2026-09/white_list_iscritti-21-09-2026.xlsx`. SHA-256: `f3d5644d57f9162d35de7f7f972deecda969824324d1b82c3cb3c21cac99c540`; size: 79,441 bytes; source reference date: 21 September 2026.

The workbook preserves ten audited section sheets and contains 236 physical company-by-section rows, grouped conservatively into 137 exact logical observations. The current status boundary is 123 `listed` and 14 `renewal_update_in_progress`; all 137 logical observations have structured identifiers. Relative to the preliminary 14 September boundary there are no identity additions or removals. Four source identifiers move from explicit renewal/update wording to ordinary listed representation with 21 September listing dates and 20 September 2027 expiry dates: `00508880978`, `02198650976`, `02292830979`, and source identifier field `03930500487 00333910974`. `02198650976` also gains section VI while remaining in section X. These are source-representation observations only.

## Applicant population

Official series page: `https://prefettura.interno.gov.it/it/prefetture/prato/white-list-elenco-imprese-richiedenti-iscrizione`. Current resource: `https://prefettura.interno.gov.it/sites/default/files/78/2026-09/elenco-imprese-richiedenti-iscrizione-21-09-2026.doc`. SHA-256: `cbf5c84522db544adb495272ebe170d105d35a9131e1853396b0584b7865a27d`; size: 101,888 bytes; source reference date: 21 September 2026.

The legacy Word table contains 23 exact seven-field applicant observations, all with structured identifiers and blank `Esito`. The additional current observation is `BC Srls`, identifier `02535330977`, application date 20 August 2026, published in the applicant population. Status maps to `pending` solely from the explicit applicant-population context, not from blank `Esito`.

## Public observation boundary

The current Prato public-source boundary is 160 observations: 137 listed-series observations and 23 applicant-series observations. Statuses are 123 `listed`, 14 `renewal_update_in_progress`, and 23 `pending`. The 236 listed section memberships remain preserved in `source_fields` rather than duplicated as separate company observations.

Canonical hosted-database integration and independent durable-evidence verification remain governed separately; this checkpoint validates the public-source observation layer and its fail-closed publication contract.
