# Aosta operational source check — 2026-09-10

## Authority and official series

In Valle d’Aosta the President of the Region exercises prefectural functions. The Regione autonoma Valle d’Aosta institutional Prefecture service exposes two distinct White List series: an **Elenco imprese iscritte nella White list** page and an **Elenco imprese richiedenti l’iscrizione** page. Both were reachable during this check and each linked a current official PDF attachment.

## Current official attachments

- Listed: `https://www.regione.vda.it/allegato.aspx?pk=84307` — SHA-256 `6733bf1e0783f02bb86edfa09155d0625946bd5a1da565704111e98979cccc2f`; 49 pages in the 2026-09-10 acquisition; 245 complete source rows with exact listing/expiry dates and a company identifier; 17 rows explicitly carry update/renewal text.
- Applicants: `https://www.regione.vda.it/allegato.aspx?pk=84309` — SHA-256 `77d4abb04467d58af4a702e6fec291f19022adff96cfe87b3f88eb929a7f82cd`; 21 pages; 139 complete request observations. The source outcome field contains 117 observations indicating subsequent White List enrolment and 22 marked in istruttoria.

The attachment URLs are stable identifiers and the PDFs themselves do not expose an edition date suitable for a stronger dating claim. Therefore `2026-09-10` is used as the **verified-current/capture reference date**, not as an asserted administrative publication or decision date. The byte hashes, source-row dates and source-page provenance remain the controlling evidence.

## Parser boundary

The listed parser only accepts rows carrying name, raw identifier, source activities, exact source listing date and exact source expiry date. It maps an explicit update/renewal cell to `renewal_update_in_progress`; otherwise the row remains `listed`, without deriving expiry from the clock. Layout-only table material without company identity is not attached to a neighbouring company.

The applicant parser only accepts complete 13-column request rows with the source application date and raw identifier. `IN ISTRUTTORIA` maps to `pending`; an explicit source outcome indicating White List enrolment maps to `listed`; negative/cancellation outcomes are mapped only when the corresponding source text is present. The archive remains source-observation based and does not deduplicate applicant outcomes against the listed series as if a canonical LegalEntity had already been established.

No durable-evidence or canonical-database completion is asserted by this source check.
