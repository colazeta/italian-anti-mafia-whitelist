# Torino White List operational check — 15 September 2026

## Official publication surface

The current official Prefettura di Torino White List landing page was verified directly at:

- `https://prefettura.interno.gov.it/it/prefetture/torino/evidenza/white-list`

Two independent GETs during the source-validation pass returned the same 116,919-byte HTML response. The current official page positively exposes two distinct populations:

1. **White List provinciale / listed population**
   - resource: `https://prefettura.interno.gov.it/sites/default/files/90/2026-09/w.l-11.09.2026.pdf`
   - SHA-256: `5c8341cd984de01f6472e049b9fa22569798ebc41761e6f85763796c8a90ba0d`
   - bytes: 2,967,519
   - pages: 37
2. **Elenco imprese richiedenti iscrizione / applicant population**
   - resource: `https://prefettura.interno.gov.it/sites/default/files/90/2026-09/w.l-11.09.2026-i.pdf`
   - SHA-256: `f84d6da09090d557ba85cd216bc1e4962935f0f43ddb2614e77995b613ed2f51`
   - bytes: 676,216
   - pages: 7

Each attachment was acquired twice independently; the paired captures were byte-identical. The `11.09.2026` date is taken from the official current resource filenames and is used only as the source-edition/reference date. It is not inferred to be an individual company decision date, legal-effect date or completeness date.

## Source structure and denominator

Both resources are landscape PDF tables with stable ruled geometry. `pdfplumber` resolves exactly one table on every page. The first page contains the column header and subsequent pages continue the table without repeating it. The parser is byte-pinned and additionally freezes the per-page company-row denominators, exact column widths, current status lexemes and reviewed anomalies.

### White List provinciale

The current listed attachment yields **1,501 source-backed observations**. The source status distribution is:

- 1,237 `listed`, represented by a blank `Esito` cell;
- 264 `renewal_update_in_progress`, represented exactly by `In corso istruttoria per rinnovo iscrizione`.

All 1,501 source rows have a non-blank expiry date; 1,500 have a source listing date. Application-date coverage is 260/1,501: four of the 264 renewal rows have no printed application date. Blank source cells are preserved and are not reconstructed from surrounding rows.

Strict identifier coverage is **1,496/1,501**. Seven identifier fields contain reviewed source anomalies and are retained verbatim rather than repaired:

- `BENA SNC` — `0526550017`;
- `CAL.E.S.A. SRL` — `6197640011`;
- `EDIL TRIVAL SRLS` — `1228500019`;
- `G.V. TRASPORTI DI GALVAGNO VITTORIO` — `GLVVTR77S12L219-08560640016`;
- `ORIGLIA SERGIO AZIENDA AGRICOLA` — `RGLSRG67C31777X-07050560015`;
- `PICCO BARTOLOMEO SRL` — `1280650050`;
- `SOCIETA’ COOPERATIVA EUROPA` — `9800980014`.

For the two mixed fields containing one malformed fiscal-code fragment plus a valid 11-digit identifier, only the strictly valid source token is structured; the complete raw field remains preserved. No identifier digit or character is inferred.

Activity cells use Roman-number section tokens. Two current source cells have non-canonical separator typography and are accepted only as byte-pinned reviewed exceptions while preserving their source meaning:

- `DUAL SRL` — `I - III - V-VI-X`;
- `EDIL VIO SAS` — `I--II-III-V`.

Eight rows also contain source-explicit legal-basis annotations: six print `“iscrizione ai sensi dell’art.34 bis del d.lgs. n.159/2011”` and two print `"iscrizione ai sensi dell’art. 94 bis d.lgs. 159/2011"`. These strings are preserved as notes. They do not override the status derived from the separate `Esito` field.

### Elenco imprese richiedenti iscrizione

The current applicant attachment yields **162 application observations**. Every row carries exactly the source outcome `In corso istruttoria per iscrizione`, mapped conservatively to `pending`.

All 162 observations have a non-blank, valid `dd/mm/YYYY` application date, a non-blank activity field and at least one strictly valid source identifier. No applicant identifier-field residue or unreviewed activity typography is present in the byte-pinned edition.

## Candidate publication boundary

The current defensible Torino source boundary is therefore **1,663 observations**:

- 1,501 listed-series observations;
- 162 applicant-series observations;
- combined statuses: 1,237 `listed`, 264 `renewal_update_in_progress`, 162 `pending`.

This is the source boundary used by the validated national candidate. The branch-level candidate build has established 50,054 national observations, 44 published Prefectures, 45 registers and 47 mapped Prefectures, including exactly 1,663 Torino observations and 1,663 distinct Torino locators. This is not yet a claim of live public deployment: PR, merge and post-merge Pages verification remain required. No applicant population, legal status, missing value, identifier repair or completeness conclusion is inferred from search absence or failed retrieval. Publication remains fail-closed on the pinned byte identities and reviewed structural denominators.

## Integration state

The current branch has established the official-source boundary, implements a byte-pinned parser with semantic regression invariants, and has passed the fail-closed national candidate build and denominator checks. `canonical_integration_validated` is therefore true for this branch-level candidate. `durable_evidence_verified` remains false: successful retrieval and candidate publication validation are not treated as proof of a separate immutable evidence archive. Live verification remains pending PR, merge and successful GitHub Pages deployment.
