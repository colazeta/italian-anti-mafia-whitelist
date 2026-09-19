# Lucca White List operational check — 19 September 2026

## Official publication surface

The current official Prefettura di Lucca page was fetched successfully from:

`https://prefettura.interno.gov.it/it/prefetture/lucca/elenco-imprese-iscritte-e-richiedenti`

The live page positively exposed both populations required for a complete current treatment:

- **Elenco imprese iscritte 11 settembre 2026**
- **Elenco imprese richiedenti 8 settembre 2026**

The landing page reported **Ultimo aggiornamento: Martedì 15 Settembre 2026, ore 12:12**. This landing timestamp is provenance for the publication surface only. It is not promoted to a company decision date, enrolment date, application date or legal-effect date.

## Byte-pinned current resources

### Listed population

- URL: `https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-imprese-iscritte-agg-l-40-del-2020-al-11-settembre-2026.pdf`
- source marker: `Aggiornato al 11/09/2026`
- bytes: `532170`
- SHA-256: `d5a0f11c68a0a3dfb01d10b30f35130c7899795bb46e0239226ad5ea575b5c67`
- pages: 26
- source rows: 331

The source contains 102 rows with positive `IN AGG.` evidence. These are classified as `renewal_update_in_progress`; the remaining 229 listed-source rows are `listed`. Two rows contain completed company-structure update notes rather than an in-progress marker and remain `listed`. One in-progress row contains no parseable expiry date beyond the raw `IN AGG.` note, so its normalised expiry date remains blank.

Structured identifier evidence is available on 324/331 listed observations. Seven observations remain raw-only because the source is blank at identifier level or contains malformed numeric typography. The parser does not concatenate split numeric fragments or pad malformed identifiers.

### Applicant population

- URL: `https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-imprese-richiedenti-agg-l-40-del-2020-al-08-settembre-2026.pdf`
- source marker: `Aggiornato al 08/09/2026`
- bytes: `179370`
- SHA-256: `fd9cdc163e09c411ce5fd1f716d85811a15503f3527ac0f5abdaec909de4f084`
- pages: 6
- source rows: 71

The dedicated applicant table positively establishes the applicant population. All 71 observations are classified `pending`; no applicant population is inferred from search failure or absence. Structured identifier evidence is available on 69/71 observations. The two malformed numeric identifiers remain raw-only.

## Parser boundary

The reviewed combined boundary is therefore **402 observations**:

- 331 listed-source observations
  - 229 `listed`
  - 102 `renewal_update_in_progress`
- 71 applicant-source observations
  - 71 `pending`

Structured identifiers are present on **393/402** observations.

The parser is fail-closed on page counts, page geometry, one-table-per-page layout, exact page-row denominators, document markers, reviewed status vocabulary, identifier coverage/raw-only anomalies, duplicate structured-identifier boundary and the single reviewed missing-expiry case. It preserves source text and does not infer missing identifiers, dates, status or legal effect.

## Re-verification

The source-validation worker performed two independent cache-bypassed GETs for each official attachment and required both captures to match the approved byte length and SHA-256. The focused parser tests and the complete 402-observation boundary passed against those independently re-fetched official bytes.
