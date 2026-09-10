# Aosta operational source check — 2026-09-10

## Authority and official series

In Valle d’Aosta the President of the Region exercises prefectural functions. The Regione autonoma Valle d’Aosta institutional Prefecture service exposes two distinct White List series: an **Elenco imprese iscritte nella White list** page and an **Elenco imprese richiedenti l’iscrizione** page. Both were reachable during this check and each linked a current official PDF attachment.

The HTML page metadata are not treated as edition dates for the attachments: the registered-company page reports its own page update as 28 August 2026 and the applicant page as 1 September 2026, while the linked attachment bytes can change independently. The archive therefore treats the attachment URLs as mutable current resources and uses direct capture plus parsed-source semantics as the approval boundary.

## Current official attachments and verified transition

Repeated independent GitHub-hosted captures on 10 September 2026 returned the same current source state:

- Listed: `https://www.regione.vda.it/allegato.aspx?pk=84307` — current witnessed SHA-256 `de10b4fe05ff6e77c1698d3b0d98c1a5603578417166440439e28107db4d354e`; 244 complete source rows; 227 map to `listed` and 17 explicitly carry update/renewal text and map to `renewal_update_in_progress`; approved semantic SHA-256 `b82caff9c3c491dc8d44b407801b6d1f9e6a1c7620f3ce2270b10bb332b7e047`.
- Applicants: `https://www.regione.vda.it/allegato.aspx?pk=84309` — current witnessed SHA-256 `6c2aaca63aa7bad2b7a95eed43ed31401b497f27167718275fd10ba736236d01`; 139 complete request observations; 116 have a source outcome indicating subsequent White List enrolment and 23 are in istruttoria; approved semantic SHA-256 `06cc1155e2abc3e38c3d552d2009fa9e06a1d958aefaf13f080d6c7475b12b00`.

This is a genuine source-content transition, not harmless wrapper-byte drift. Compared with the last live-verified capture, `IMPRESA COSTRUZIONI SAN GIORGIO Srl` (`00562570077`) is absent from the current listed series. The same identity remains in the applicant series, but its source observation has changed from an application dated 25 September 2024 with an outcome indicating enrolment from 26 August 2025 and activities `C`, `E`, `F`, `G H`, to a new application dated 3 September 2026 for activity `C` with the explicit outcome `Istruttoria in corso`. No other listed identity was added or removed and no other common listed identity changed in the audited public semantic fields; the applicant identity set remained unchanged.

The current row counts, raw hashes, semantic hashes and this row-level transition were reproduced on separate GitHub-hosted runs before approval. A subsequent full current-source national build also completed successfully with the revised Aosta state, producing 8,822 observations across 12 published authorities and 13 registers.

The attachment PDFs do not expose an edition date suitable for a stronger dating claim. Therefore `2026-09-10` remains the **verified-current/capture reference date**, not an asserted administrative publication or decision date.

## Approval and parser boundary

Because the official attachment endpoints are mutable, Aosta now uses `semantic_sha256` approval. The raw SHA-256 of every downloaded attachment remains attached to the resulting source observations as capture provenance. Publication remains fail-closed: a future capture may differ at the byte level only if the parsed source semantics still match the separately approved semantic digest; any semantic change blocks publication until it is independently reviewed and approved.

The listed parser only accepts rows carrying name, raw identifier, source activities, exact source listing date and exact source expiry date. It maps an explicit update/renewal cell to `renewal_update_in_progress`; otherwise the row remains `listed`, without deriving expiry from the clock. Layout-only table material without company identity is not attached to a neighbouring company.

The applicant parser only accepts complete 13-column request rows with the source application date and raw identifier. `IN ISTRUTTORIA` maps to `pending`; an explicit source outcome indicating White List enrolment maps to `listed`; negative/cancellation outcomes are mapped only when the corresponding source text is present. The archive remains source-observation based and does not deduplicate applicant outcomes against the listed series as if a canonical LegalEntity had already been established.

No durable-evidence or canonical-database completion is asserted by this source check.
