# Como White List operational check — 17 September 2026

## Scope and current official sources

The Prefettura di Como publishes the two populations required for a complete ordinary White List treatment on two dedicated official HTML pages:

- registered companies: `https://prefettura.interno.gov.it/it/prefetture/como/elenco-ditte-iscritte-white-list`;
- companies requesting registration: `https://prefettura.interno.gov.it/it/prefetture/como/elenco-ditte-fase-iscrizione-white-list`.

Both pages expose the current table directly in the official Prefecture site and carry the current source date/update of 10 September 2026. The registered and applicant populations are therefore positively identified independently; applicant publication is not inferred from absence, search failure or table semantics.

## Independent capture and immutability check

On 17 September 2026 each official page was fetched twice independently with a two-second separation. The raw response bytes were stable across the two GETs:

| Population | Raw SHA-256 | Bytes | Physical company rows |
| --- | --- | ---: | ---: |
| Registered-company page | `276fcec3a27893b0b57af24ff8d69ebb64338fd5bc955e4722bd48eb33535413` | 210,592 | 391 |
| Applicant-company page | `a4ed63b8e04a277af0221288c40552027437c31064d89ddbc44da432eada42c7` | 85,699 | 18 |

Because these are mutable HTML publication surfaces, production approval is semantic as well as provenance-aware: raw capture SHA-256 remains attached to each observation, while the current reviewed parsed semantics are pinned to:

- registered population semantic SHA-256: `653dc491b25dd4afdd88c7848a42e0ea5b997b51cc2fdc4ef71dcf63bc9c9ad4`;
- applicant population semantic SHA-256: `fe4dcf2b862696df0aac87b43af0037b272c26285b87360f0d5a75cee613a24b`.

A later wrapper-only HTML change may therefore be accepted only if the reviewed semantic digest remains identical. Any semantic drift fails closed and requires a new source review.

### Later same-day semantic revalidation

A later independent validation on 17 September 2026 fetched each official page twice again. The mutable HTML wrappers had changed relative to the first reviewed captures, but the two new GETs were byte-stable within that validation cycle and the reviewed parsed semantics remained exactly unchanged:

| Population | Later raw SHA-256 (both GETs) | Semantic SHA-256 | Result |
| --- | --- | --- | --- |
| Registered-company page | `f4273fc06277244db3380ec3c7d2bf450b85c3820be3a7b9a04360873ff5323e` | `653dc491b25dd4afdd88c7848a42e0ea5b997b51cc2fdc4ef71dcf63bc9c9ad4` | wrapper-only drift |
| Applicant-company page | `475d6cb07b1e73479e6bc5398a61e43dfdb8764a305696a0f9ec0084b8b978cf` | `fe4dcf2b862696df0aac87b43af0037b272c26285b87360f0d5a75cee613a24b` | wrapper-only drift |

Record counts, declared-count diagnostics, status distributions, identifier coverage and malformed-date diagnostics were unchanged. This revalidation therefore supports the semantic-approval model for the mutable HTML source without treating changed wrapper bytes as new company evidence.

## Source-declared counts versus the physical table population

The registered table declares `NUMERO AZIENDE ISCRITTE: 388`, but contains 391 company rows after the exact eight-column header. The applicant table declares `NUMERO AZIENDE IN FASE ISCRIZIONE: 12`, but contains 18 company rows after its exact eight-column header. Inspection of the captured DOM found no hidden or `display:none` company rows that would justify excluding the additional rows.

The parser therefore preserves the complete positive source population actually published in the tables and records the declared-count discrepancies as diagnostics (`+3` and `+6`). It does **not** truncate the data to stale counters, nor reinterpret the counters as evidence that later rows are invalid.

## Parsed observation boundary

The current edition yields **409 source-backed public observations**:

- 391 registered-population rows: **359 `listed`** and **32 `renewal_update_in_progress`**;
- 18 applicant-population rows: **18 `pending`**.

Renewal/update status is assigned only where the source note explicitly contains `fase di rinnovo` (case-insensitive). A separate `VARIAZIONE COMPAGINE SOCIETARIA` note remains `listed`; no broader legal status is inferred from that text.

Identifier coverage is **405/409 structured identifiers**. The remaining four observations are retained as source evidence rather than repaired:

- one registered row has a blank identifier;
- `ANGOLO VERDE ...` carries the ten-digit raw identifier `1659340135`;
- `MA.RI. TRASPORTI s.a g.l.` carries `CHE-114.109.939`;
- `PAÑALON, S.A.` carries `-`.

The source also assigns raw identifier `04187480134` to two different company names (`EDA TRASPORTI s.r.l.` and `E.F.F. S.R.L.S.`). Both observations are retained. The parser does not deduplicate, repair or adjudicate this source conflict.

## Dates, sectors and conservative normalisation

Only explicit valid source dates are normalised. Two registered rows contain malformed listing-date text:

- `BANFI S.R.L.` — `12/08/21024`;
- `MANI D'ARTIGIANO INSTALLAZIONI S.R.L.S.` — `07 gosto 2026`.

Their malformed raw values are retained in provenance and the corresponding normalised listing date is left blank; neither typo is silently repaired. Valid slash-format and Italian abbreviated-month dates are normalised deterministically.

White List activities are retained from the explicit Roman-section labels. Applicant application evidence is month-only (`apr-26`, `set-26`, etc.); it remains raw month-level provenance and is **not** expanded to an invented day or full date. The same rule applies to month-only renewal evidence in the registered table.

## Integration checkpoint and external national-build blocker

The Como production integration was checkpointed on the dedicated expansion branch after the Como semantic tests and the complete repository test suite passed. The scoped integration changes only the Como-related catalogue, coverage, publication/source-registry, parser binding and corresponding source-registry tests.

The candidate national build is **not** considered validated yet. During the same transaction, the already integrated `potenza-combined` mutable source returned 1,035 rows while the canonical Potenza approval remains pinned to 1,034 rows. The national builder therefore failed closed on Potenza before a candidate Como public registry could be approved. No Potenza source status, completeness or legal effect is inferred from this row-count change, and Potenza is not modified or treated as Como evidence on this branch. Como publication remains implemented but not national-validated or live until that independent external source drift is reconciled on the canonical baseline and the complete national build is rerun successfully.

## Publication decision

Como is suitable for ordinary-regime national integration because both current registered and applicant populations are positively identified on official dedicated pages and the parser boundary has been independently re-fetched and semantically validated. Production publication must retain the complete 409-row current table population, the declared-count discrepancies as diagnostics, all malformed/raw identifier and date evidence, and semantic fail-closed approval for the mutable HTML surfaces.
