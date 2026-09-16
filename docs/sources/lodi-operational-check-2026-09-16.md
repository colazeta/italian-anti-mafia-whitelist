# Lodi operational source transition — 16 September 2026

## Scope

This note records the evidence review required after the mutable official Lodi registered-company Google Sheet changed after the 15 September approval. It does not infer a legal publication date from the observation date.

## Official publication surface

- Authority: Prefettura di Lodi.
- Official White List page: `https://prefettura.interno.gov.it/it/prefetture/lodi/evidenza/white-list`.
- The page continues to positively expose separate registered-company and requesting-company Google Sheet tabs.
- Both populations were fetched twice independently with cache-bypass parameters on 16 September 2026.

## Registered-company transition

The two current captures are byte-identical:

- SHA-256: `c3695018c56ba754614eff988011e0f9b2f6cb2d8e0f22a9823275c8659da613`.
- Size: 36,372 bytes.
- Physical CSV rows: 324, all exactly seven columns.
- Positively identifiable statutory-section membership rows: 291.
- Section denominators are unchanged: I 44; II 24; III 47; IV 18; V 55; VI 54; VII 6; VIII 1; IX 3; X 39.
- Source-row status totals are unchanged: 254 ordinary listed memberships and 37 explicitly in aggiornamento.
- Conservative grouping remains exactly 169 public observations: 146 `listed` and 23 `renewal_update_in_progress`.

Exact comparison with the preserved 15 September approved capture (`ad64ab8669084bc31b80938a384b41849be4db28b448e9b2c0ce199f6af1d6ec`) yields exactly two changed CSV rows and no insertions or removals:

1. `KUMAR S.n.c. di Kumar Devinder e C.` — identifier `03030560969`: dates remain `23/10/2025` to `23/10/2026`; the status marker changes from blank to `in aggiornamento`, so the source status becomes `renewal_update_in_progress`.
2. `Z.A. AUTOTRASPORTI S.r.l.` — identifier `04220560967`: the previous `13/08/2025` to `13/08/2026` row marked `in aggiornamento` is replaced by an ordinary listed row dated `16/09/2026` to `16/09/2027`.

The two changes offset in the aggregate status counts; therefore the 169-record listed-series denominator and its 146/23 status split remain unchanged. The project nevertheless approves the new raw byte identity explicitly rather than treating equal denominators as evidence of unchanged content.

## Applicant population

The two current applicant captures are byte-identical and also identical to the 15 September approved capture:

- SHA-256: `55aeab7e809cb90cc1ebd1ad9c1f08db78e91648a2c2e1a2b603188c77846228`.
- Size: 1,388 bytes.
- Physical CSV rows: 8.
- Positively identifiable observations: 4.
- Statuses remain two explicit denials and two `pending` / `IN ISTRUTTORIA` observations.

No applicant transition is inferred because none is observed.

## Approval boundary

The current Lodi public-source boundary remains 173 observations: 169 registered-series observations plus 4 applicant-series observations. The registered-series bytes are promoted only after the two independent captures, exact historical comparison, parser tests and national publication build pass. `durable_evidence_verified` remains a separate control and is not promoted by this source transition.
