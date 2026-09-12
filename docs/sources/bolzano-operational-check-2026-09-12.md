# Bolzano/Bozen operational source check — 12 September 2026

## Current official evidence

The current official White List landing of the Commissariato del Governo per la Provincia di Bolzano was directly resolved on 12 September 2026. It positively exposes distinct consultation surfaces for companies registered/under renewal and for companies requesting registration. The current attachments are both dated **11 September 2026**. Each attachment was independently fetched twice during the source audit and produced the same SHA-256 on both requests.

- Landing page: https://prefettura.interno.gov.it/it/prefetture/bolzano/evidenza/white-list
- Listed/renewal DOCX: https://prefettura.interno.gov.it/sites/default/files/0/2026-09/2026.09.11-elenco-white-list-da-sez-1-a-sez-10_iscritti-rinnovi.docx
- Listed/renewal SHA-256: `96992db4caac16200fbebfa573bb602e1e396961ff854bbf006cb42e011c1e04`.
- Applicant DOCX: https://prefettura.interno.gov.it/sites/default/files/0/2026-09/2026.09.11-elenco-richiesta-iscrizione-wl.docx
- Applicant SHA-256: `8b7321745edb19db688a001b9a1a706e84bee95cb457f9fdca1af144521ef3ae`.

## Population boundary and parser result

The listed/renewal DOCX contains ten statutory section tables. The reviewed denominator is 1,706 section rows: 307, 144, 219, 158, 269, 226, 21, 10, 165 and 187 rows across sections 1–10 respectively. Exact grouping across sections yields **871 company observations**: **620 `listed`** and **251 `renewal_update_in_progress`**.

The applicant DOCX contains **351 source rows**, yielding **351 applicant observations**, all represented as **`pending`**. No applicant outcome is inferred from absence or search behaviour.

The combined Bolzano public candidate therefore contains **1,222 observations**.

## Conservative exceptions and fail-closed behaviour

The parser freezes the current table count, section-row vector, semantic observation counts, status counts and the complete observed update-status lexicon. Unknown update tokens, new table layouts, row-count drift, same-section exact duplicates and unreviewed date typography fail closed.

Nine malformed listing-date strings and eleven malformed expiry-date strings are explicitly reviewed and preserved raw rather than repaired. The expiry set includes the syntactically complete but impossible calendar value `16/19/2026`, independently identified by the calendar audit. The applicant file contains the reviewed malformed application-date token `14/032025`; it also remains raw and uninferred.

Identifiers are promoted only when the source value is exactly an 11-digit numeric identifier or a 16-character alphanumeric identifier. Other source strings remain available in the raw identifier field and are not reconstructed. Grouping is exact; there is no fuzzy company matching or address-based deduplication.

## Verification state

The parser was validated against the two byte-pinned official documents on 12 September 2026. The real-source validation yields 871 listed-population observations and 351 applicant observations with the expected status distribution. The national public build remains a separate integration gate and must pass before Bolzano/Bozen is marked live.
