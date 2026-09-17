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

## Verified current-source transition — 16 September 2026

The two mutable official attachments were independently captured twice without cache on 16 September 2026 in GitHub Actions run `35071860118` (retained audit artifact `10437035495`). Each pair was byte-identical and parser-identical. This is a new source-content transition and therefore required a new reviewed semantic approval; it is not treated as harmless wrapper-byte drift.

- Listed: current witnessed SHA-256 `49b94a13c20354cd1c0c29c0b8ec7551813e5ec4d87ab51a1da1227ba05b298c`; 243 complete observations = 222 `listed` + 21 `renewal_update_in_progress`; identifier coverage 243/243. With the verified-current reference date set to 16 September 2026, approved semantic SHA-256 `1105371866a74157a427b0e885817d5446a8a7a51d9c59a8bed3ad5b62eeb50a`.
- Applicants: current witnessed SHA-256 `0132bd120fd34208b8f07556bcc44a2731db390d799a72c365db952481f09344`; 139 complete observations = 115 with source-explicit subsequent enrolment + 24 `pending`; identifier coverage 139/139. With the verified-current reference date set to 16 September 2026, approved semantic SHA-256 `09901d8ea7caa54b6ca4509611e9312b54051d8ebab116bd065838d3d005ab1b`.

A row-level comparison against the last live-verified public artifact isolates the transition. `DEMA Srl` (`01191640075`) leaves the listed series and appears in the applicant series with application date 4 September 2026, activity `E-F-G` and explicit outcome `Istruttoria in corso`. `DE FAZIO CRISTIAN (impresa individuale)` (`01227090071`) leaves the applicant series and remains listed with explicit `In corso istruttoria per rinnovo iscrizione`. Three further existing listed identities — `PIETRA DI MORGEX Srl` (`01060840079`), `URBANIA HABITAT DI STEFANO MATTIOLI & C. Sas` (`00611790072`) and `V.I.T.A. S.P.A.` (`00035670074`) — newly carry the same explicit renewal-in-progress text. No other listed identity is added or removed and no other common listed identity changes in the audited public semantic fields; the applicant row count remains 139.

The attachment PDFs remain undated mutable current resources. `2026-09-16` is therefore a verified-current/capture reference date, not an asserted administrative publication or decision date. Raw capture SHA-256 remains attached to observations as provenance. Publication remains fail-closed on any future semantic change. Canonical hosted-database integration and independent durable-evidence verification remain separately governed and are not claimed by this source transition.

## Second verified current-source transition — 16 September 2026

Immediately after the first 16 September transition was merged, the post-merge public build failed closed because the mutable official listed attachment had changed again. A dedicated same-Prefecture audit in GitHub Actions run `35083259611` independently captured both official attachments twice without cache. Each source pair was byte-identical and parser-identical.

- Listed: witnessed SHA-256 `7b107f612d5336dd21a7db6fef105759e65057ef8147b165fea47e4ccab0ebc4`; 242 complete observations = 221 `listed` + 21 `renewal_update_in_progress`; identifier coverage 242/242; approved semantic SHA-256 `db0db749e75a09fce8dcdaffc6ef2c7e5d7da58bd6978e111b3d66dadc8b4f93`.
- Applicants: witnessed SHA-256 `d514dd66b7248f0f3a46f56c582ccd9ba986a031b6676fb8aca560158b0a1e55`; 140 complete observations = 115 with source-explicit subsequent enrolment + 25 `pending`; identifier coverage 140/140; approved semantic SHA-256 `1519a119b34b4b3340feaf5cf2f391de84803592060720f6c9660492d192be93`.

The row-level delta is exact and internally coherent. `IMPRESA HENRIET GERMANO & C. Sas` (`00090050071`) is the only identity removed from the listed series; its previous listed observation carried listing date 16 September 2025 and expiry date 15 September 2026. The same identity is the only addition to the applicant series, with application date 20 August 2026, activities `C–D–G-H` and explicit outcome `Istruttoria in corso`. No other common listed or applicant identity changes in the audited public semantic fields. The Aosta observation total therefore remains 382 while its status composition changes from 337 listed / 24 pending / 21 renewal-update to 336 listed / 25 pending / 21 renewal-update.

The attachments remain undated mutable current resources, so 16 September 2026 remains a verified-current/capture reference date rather than an asserted administrative publication date. This second transition is approved only from the independently reproduced current source semantics; raw capture SHA-256 remains attached as provenance and future semantic drift continues to fail closed.

## Verified current-source transition — 17 September 2026

The mutable official Aosta attachments changed again after the second 16 September approval. Two independent no-cache captures in audit run `35237973404`, followed by a second independent re-verification in finalisation run `35238612322`, reproduced the same byte- and parser-stable state before this checkpoint.

- Listed: witnessed SHA-256 `9e034f0e681d5352fe2c610982ca6726488e31db796e5e3d875e500edd9b18d9`; 241 complete observations = 220 `listed` + 21 `renewal_update_in_progress`; identifier coverage 241/241; approved semantic SHA-256 `dce8394a53a92476f662830b10e659e3249f8ecbf9f16faa1492c792c7e250f2`.
- Applicants: witnessed SHA-256 `34a6277e6b956a82d76279c283f6fb8d4fa75c7395b0897a4eefef88448db32a`; 141 complete observations = 115 with source-explicit subsequent enrolment + 26 `pending`; identifier coverage 141/141; approved semantic SHA-256 `9c27558e5506203e3f0799e1470f5526d1efa4ef19fedc183b9e81e1fe7bffd7`.

The row-level transition is narrowly identified. `CHATRIAN ONORANZE FUNEBRI DI CHATRIAN EMY S.A.S. siglabile CHATRIAN ONORANZE FUNEBRI S.A.S` (`01077930079`) is the only identity removed from the current listed series; its previous listed observation carried listing date 17 September 2025 and expiry date 16 September 2026. The same identity is the only addition to the current applicant series, with application date 31 August 2026, requested activity `I-bis` and explicit outcome `Istruttoria in corso`. No other common listed semantic field changed. Among common applicant rows, the only semantic source-string change is the registered office of `IMPREAM DI AMATO FRANCESCO FABRIZIO (impresa individuale)` (`MTAFNC78D18A326L` / `01121190076`), where the official string now ends in `(Ao)`; its 7 January 2026 application and `Iscritta dal 29/04/2026` outcome are unchanged.

The Aosta observation total therefore remains 382, while the status composition changes from 336 listed / 25 pending / 21 renewal-update to **335 listed / 26 pending / 21 renewal-update**. Absence from the current listed attachment is not interpreted as revocation, cancellation, denial or any other legal effect. The undated attachment URLs remain mutable current resources; 17 September 2026 is a verified-current/capture reference date only. Future semantic drift continues to fail closed.
