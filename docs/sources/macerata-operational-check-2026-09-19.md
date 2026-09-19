# Macerata White List operational source check — 19 September 2026

## Scope

This note records the evidence reviewed for adding the Prefettura di Macerata to the public multi-Prefecture White List registry. The observation boundary is the official edition exposed by the Prefettura landing page on 19 September 2026. The document reference date is **21 August 2026**; 19 September is only the verification/capture date and is not interpreted as a legal-effect date.

## Official landing page

Official page: `https://prefettura.interno.gov.it/it/prefetture/macerata/white-list-elenco-imprese-iscritte`

The page positively exposes two distinct current series:

- `iscrizioni al 21 agosto 2026` — listed-company population;
- `presentazioni al 21 agosto 2026` — applicant population.

The page itself reports `Venerdì 21 Agosto 2026, ore 16:36` as its last update. Applicant coverage is therefore based on positive first-party publication evidence, not inferred from search failure, absence, or a listed-only document.

## Byte-pinned resources

### Listed companies

Resource: `https://prefettura.interno.gov.it/sites/default/files/52/2026-08/iscrizioni-21.08.2026.pdf`

Two independent cache-bypassed GETs on 19 September 2026 both returned HTTP 200, exactly **1,733,039 bytes**, and the same SHA-256:

`7b1518847ea0bcc6bd76bd354ded1ae0e0cc7e7092cb9b7077dbcc689bfe1bce`

The PDF has 50 pages and ten sector sections. `pdfplumber` identifies **2,150 company×section rows**. The public parser groups only rows whose complete source identity/date/status cells are byte-semantically identical across sector repetition; it does not reconcile conflicting dates, names, identifiers, or statuses across otherwise similar rows. This yields **1,274 public source observations**:

- 879 `listed`;
- 394 `renewal_update_in_progress`;
- 1 `other_or_unknown` because the source status cell contains only `i`, which is deliberately not expanded or repaired.

Structured identifier extraction is available for **1,240/1,274** observations. Thirty-seven reviewed identifier cells are non-standard at the observation boundary and remain raw; where a malformed multi-token cell still contains independently valid 11-digit tokens, only those explicit valid tokens are exposed as structured candidates. Ten expiry cells are blank or non-standard; the source value `ISCRIZIONE 05/01/2027` is preserved raw and is not reinterpreted as an expiry date.

### Applicant companies

Resource: `https://prefettura.interno.gov.it/sites/default/files/52/2026-08/presentazioni-21.08.2026.pdf`

Two independent cache-bypassed GETs on 19 September 2026 both returned HTTP 200, exactly **290,457 bytes**, and the same SHA-256:

`4d432d015c09060967da156d9ee54718645a22a623656c6def5a9fc58367aa17`

The PDF has 20 pages and **84 company observations**. Three activity cells continue over a page break and are attached only to the immediately preceding source row; the parser freezes the reviewed continuation pages (8, 12 and 20) and page-level company denominators.

The source outcome column is blank for 83 observations, which remain `pending` within the positively published applicant series. One row — `E.M.G. SERRAMENTI SRLS` — explicitly states `Iscritta il 14/08/2026`; that observation is therefore represented as `listed`, with 14 August 2026 retained as the observed listing date. Its application-date cell reads `27/01/206`; this is preserved as raw evidence and is **not** repaired to a four-digit year. Four applicant identifier cells are non-standard and remain raw-only. Structured identifiers are available for **80/84** applicant observations.

## Candidate public boundary

Macerata contributes **1,358 source-backed observations** in total:

- 880 `listed` (879 from the listed series plus the one explicitly listed applicant observation);
- 394 `renewal_update_in_progress`;
- 83 `pending`;
- 1 `other_or_unknown`.

Structured identifier coverage is **1,320/1,358 observations**.

The intended national candidate boundary, from the live Lucca baseline of 65,267 records / 61 published Prefectures / 63 registers / 61 mapped Prefectures, is therefore:

**66,625 records / 62 published Prefectures / 64 registers / 62 mapped Prefectures.**

## Fail-closed parser boundary

`src/white_list_archive/parsers/macerata_tables.py` freezes and validates:

- page counts for both PDFs;
- one extracted table per page;
- exact per-page company denominators;
- the ten listed-sector headings and their order;
- 2,150 listed company×section rows and 1,274 exact grouped observations;
- reviewed raw listed status vocabulary;
- reviewed malformed identifier ordinals;
- reviewed non-standard/blank expiry cells;
- 84 applicant observations and continuation pages;
- applicant outcome vocabulary;
- the four malformed applicant identifiers and the one malformed application-date cell.

Any source-shape, denominator, vocabulary or reviewed-exception drift fails publication rather than being silently repaired.
