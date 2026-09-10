# Agrigento White List operational check — 10 September 2026

## Official current surface

The official Prefettura di Agrigento White List landing page was re-read from a GitHub-hosted runner on 10 September 2026: https://prefettura.interno.gov.it/it/prefetture/agrigento/evidenza/white-list. It positively exposed exactly two relevant current attachments, one labelled `elenco-richiedenti-iscrizione-4-settembre-2026.pdf` and one labelled `elenco-iscritte-4-settembre-2026.pdf`. This direct live resolution supersedes stale search-engine indexing of older August attachments and provides current-edition evidence for both ordinary White List populations.

## Byte-pinned resources

Registered-company resource: `https://prefettura.interno.gov.it/sites/default/files/100/2026-09/elenco-iscritte-4-settembre-2026.pdf`, SHA-256 `23ceb5785bb39ca2da2eef5a80ad0468b03a191ad2cc36c571524587dbafca81`, 858,929 bytes, 63 pages.

Applicant resource: `https://prefettura.interno.gov.it/sites/default/files/100/2026-09/elenco-richiedenti-iscrizione-4-settembre-2026.pdf`, SHA-256 `cfbf0dc1f9059437eb0d7801ff9867f9243f2fb83a91f2342e88ec9ed75416e9`, 340,513 bytes, 16 pages.

## Parser boundary and source observations

Both PDFs use landscape ruled tables with stable semantic x-coordinate bands even where the PDF drawing layer creates 9-, 12-, 19- or 21-cell micro-grid artefacts. Generic table extraction can therefore split one company over physical continuation rows. The approved parser boundary is position-aware: it reconstructs text within the full logical ruled-row vertical extent and accepts a company observation only where the registered-office column is populated. Continuation fragments without their own office are not promoted to additional companies.

On the byte-pinned edition, this boundary yields 855 registered-company observations and 329 applicant observations. The listed population is source-explicit and is published as `listed`. The applicant table reports `Istruttoria in corso` for 328 observations and the source typo `Istruttoria n corso` once; both contain the explicit `istruttoria` marker and are published as `pending`, while the raw outcome text is retained.

Source anomalies are not repaired. Non-canonical numeric identifiers and source-case fiscal codes remain in the raw identifier field unless they independently satisfy the canonical identifier shape. The applicant source includes date typography such as `06.08. 2020` and `26.062026`; only whitespace removal is allowed where it leaves every digit and punctuation mark unchanged, while the latter remains uncoded and is preserved as a raw date variant. Listed-company malformed date strings include `25.05.206`, `01..04.2026`, `02.2022`, `20,08,2026`, `19,10,2024` and expiry `22,01,2027`; these remain raw variants and are not reconstructed. The source also contains activity/section typography such as a lone comma; no missing sector number is inferred.

## Publication gate

Publication must pin both exact resource SHA-256 values and the validated denominators of 855 listed plus 329 applicant observations. Page-count drift, source-byte drift, changed denominators, loss of the explicit applicant `istruttoria` outcomes, or a new table geometry without the reviewed office-anchored logical-row boundary fails closed. Canonical hosted-database promotion and independent durable-evidence recovery verification remain separate under issue #16 and are not claimed complete here.
