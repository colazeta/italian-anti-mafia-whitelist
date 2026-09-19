# Grosseto White List operational check — 19 September 2026

## Official publication surface

The current official Prefettura di Grosseto White List page positively exposes two separate resources: **Elenco imprese iscritte** and **Elenco imprese richiedenti iscrizione**. The landing-page metadata states **Ultimo aggiornamento: 27 August 2026, 09:56**. On 19 September 2026 the page itself resolved directly from the official domain and the two current attachments resolved from the official `/2026-09/` path. Their HTTP Last-Modified headers are 15 September 2026. Because the attachment labels do not state an edition date, neither the September path nor HTTP metadata is promoted to a substantive source-edition, company-decision or legal-effect date. The publication configuration therefore uses 19 September only as the reviewed observation/capture boundary and separately preserves the landing-page update date.

## Content-addressed evidence

Two independent cache-bypassed GETs for each resource were byte-identical. The listed workbook is **61,019 bytes**, SHA-256 `4e5221c25c669c062dd8512ea77bdf5760130bc8f1c2bcdb9ef456b66f5f6c18`; the applicant workbook is **13,878 bytes**, SHA-256 `814b53753a5ec3cb962d63564b24d0f0b5104f47213d160dca8218a102028248`. Publication remains fail-closed on those exact hashes.

## Reviewed parser boundary

Both workbooks use `Foglio1` and repeat companies across White List sections. The listed workbook has a frozen shape of 800 × 19 and 762 company-section rows. Following the existing conservative repeated-section methodology, rows are grouped only when normalised company identity, source identifier, legal and secondary offices, listing and expiry dates, source status and source note agree. This yields **406 observations: 328 listed and 78 renewal/update in progress**. There are **371/406 structured identifiers**; 35 source identifier values remain raw-only, including one blank source value. Eight grouped observations have source-blank listing dates and the same eight have source-blank expiry dates; blanks remain blanks. Source disagreements across sections are therefore retained as distinct observations rather than reconciled.

The applicant workbook has a frozen shape of 72 × 11 and positively identifies the applicant population. Its 35 company-section rows conservatively group to **12 pending observations**, all with structured identifiers. Section VIII is present in the source layout but has no applicant company row.

The resulting Grosseto public candidate contains **418 observations** with 383 structured identifiers. No applicant population, legal effect, missing date, identifier digit or address is inferred or repaired.
