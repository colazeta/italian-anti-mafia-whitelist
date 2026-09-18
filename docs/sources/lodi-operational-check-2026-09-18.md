# Lodi operational source transition — 18 September 2026

## Scope

This note records the evidence review required after the mutable official Lodi registered-company Google Sheet changed after the 16 September approval. The observation date is not treated as an inferred publication date.

## Positive official-source evidence

The Prefettura di Lodi White List publication surface remains `https://prefettura.interno.gov.it/it/prefetture/lodi/evidenza/white-list`, which positively exposes separate registered-company and requesting-company Google Sheet populations. The source exports themselves were independently fetched twice with cache bypass on 18 September 2026.

## Registered-company transition

The two current listed captures are byte-identical at SHA-256 `a9f6a0977ce0d1a26a6a86450643496cc70f2a1a3eba017e89812eb6f203276e` and size 36,420 bytes. The approved 16 September capture is SHA-256 `c3695018c56ba754614eff988011e0f9b2f6cb2d8e0f22a9823275c8659da613` and size 36,372 bytes. The preserved 16 September workflow artifact (`Lodi source drift audit (temporary)`, run `35112659448`) permits an exact historical comparison.

The current structure is unchanged: 324 physical CSV rows, seven columns per row, and 291 positively identifiable statutory-section memberships. Exact old/new comparison identifies three changed membership rows and no insertions or removals:

1. `F.LLI BORCHIA DI FRANCO E IVANO BORCHIA & C. S.n.c.` — identifier `01495270157`, source rows 62 and 169: dates remain `21/10/2025`–`21/10/2026`; both blank status markers become `in aggiornamento`.
2. `CENTRO EDILE LODI S.r.l.` — identifier `04301190965`, source row 103: dates remain `28/10/2025`–`28/10/2026`; the blank status marker becomes `in aggiornamento`.

The source-row status denominators therefore move from 254 listed / 37 renewal-update to 251 listed / 40 renewal-update. Conservative grouping by exact identifier/date/status remains 169 observations with the same occurrence distribution; the grouped status split moves from 146 listed / 23 renewal-update to 144 listed / 25 renewal-update because the two BORCHIA memberships represent one grouped observation and the CENTRO EDILE membership represents another.

No legal consequence is inferred beyond the source-explicit `in aggiornamento` marker.

## Applicant population

The applicant export is unchanged. Both 18 September captures are byte-identical to the approved boundary at SHA-256 `55aeab7e809cb90cc1ebd1ad9c1f08db78e91648a2c2e1a2b603188c77846228`, size 1,388 bytes. The four positively identified observations remain two explicit denials and two records explicitly in istruttoria. No applicant status or completeness is inferred from failed search.

## Approval boundary

The Lodi public-source record denominator remains 173 observations: 169 registered-company observations plus 4 applicant observations. Only two grouped registered-company statuses change, so the national record count is unchanged. Parser version 3 freezes the new raw SHA-256 and the new source/grouped status denominators while retaining all existing structural, date, grouping and identifier checks. Durable evidence verification remains a separate governance control under issue #16.
