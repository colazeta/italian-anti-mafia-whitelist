# Modena operational source check — 17 September 2026

## Official publication surface

The current official source surface is the Prefettura di Modena page:

- https://prefettura.interno.gov.it/it/prefetture/modena/white-list-elenchi-provinciali-ed-elenchi-ricostruzione-post-sisma

The page was observed as last updated on 16 September 2026 at 11:16 and positively exposes four current source populations. The project therefore treats Modena as two distinct registers, each with both a listed and an applicant population:

1. ordinary provincial White List — listed companies;
2. ordinary provincial White List — applicant companies;
3. post-earthquake White List — listed companies;
4. post-earthquake White List — applicant companies.

This is a positive-evidence classification. No population is inferred from a missing or failed search.

The four official current attachments are:

- provincial listed: https://prefettura.interno.gov.it/sites/default/files/0/2026-09/iscritti-elenchi-wl-provinciali.pdf
- provincial applicants: https://prefettura.interno.gov.it/sites/default/files/0/2026-09/richiedenti-iscrizione-elenchi-wl-provinciali.pdf
- post-sisma listed: https://prefettura.interno.gov.it/sites/default/files/0/2026-08/iscritti-elenchi-wl-ricostruzione-post-sisma_5.pdf
- post-sisma applicants: https://prefettura.interno.gov.it/sites/default/files/0/2026-08/richiedenti-iscrizione-elenchi-wl-ricostruzione-post-sisma_3.pdf

The directory dates embedded in attachment URLs are not treated as edition dates. The project reference date is 16 September 2026, based on the current official Modena publication surface. The attachment bytes were independently reverified on 17 September 2026.

## Independent current-source capture

Each attachment was fetched twice independently with no-cache headers. Each pair was byte-identical. The approved current byte identities and document boundaries are:

| source series | SHA-256 | bytes | pages |
| --- | --- | ---: | ---: |
| provincial listed | `84f7ffa41f8e14b7cb1b3f5817d46e20c721b43a1a77280955999be331f2380a` | 5,356,482 | 225 |
| provincial applicants | `323c1dace295b50f4baff85545879be920dc05ef9072f34b4d98449acf11f79f` | 1,563,570 | 88 |
| post-sisma listed | `658e24f8342c04dc8c16dba8d4e3660c16fbff89722507a30dfba1d9a43274d0` | 7,225,240 | 274 |
| post-sisma applicants | `e21f47c956dd355fc2400ef110916349632ad6f31eb7878c99a3d05834eb5bf1` | 993,647 | 40 |

The resources are mutable official attachments. Raw SHA-256 approval is therefore deliberately fail-closed: a future byte change requires a new evidence review rather than silent ingestion. The current run does not claim independent durable archival evidence; `durable_evidence_verified` remains false.

## Source structure and observation boundary

The listed documents expose company name, registered office, tax/VAT identifier, listing date, measure/protocol, observed expiry date and notes. The applicant documents expose company name, registered office, tax/VAT identifier, application date and notes. The ordinary register is divided into ten statutory sections. The post-sisma listed register is divided into seven reconstruction-sector sections; the post-sisma applicant file is a pooled `ULTERIORI SETTORI` population.

The same company can be physically repeated across sectors. Publication therefore groups only repetitions that share the exact company name, raw identifier, relevant source dates and source-status note, while preserving all contributing sections and physical locators. This produces source-backed observations rather than a claim of nationally deduplicated legal entities.

The reviewed denominator is:

| source series | physical sector/source rows | logical public observations | status boundary |
| --- | ---: | ---: | --- |
| provincial listed | 2,174 | 1,181 | 634 listed; 547 renewal/update in progress |
| provincial applicants | 803 | 502 | 502 pending |
| post-sisma listed | 2,927 | 1,679 | 926 listed; 753 renewal/update in progress |
| post-sisma applicants | 432 | 430 | 430 pending |
| **total** | **6,336** | **3,792** | **1,560 listed; 1,300 renewal/update; 932 pending** |

The official page expressly explains that an `Aggiornamento in corso` company remains valid beyond the nominal expiry while renewal controls are being completed. The parser maps only source-explicit `Aggiornamento in corso` or `rinnovo in corso` to `renewal_update_in_progress`. Other notes, including references to prevention measures, collaborative prevention or judicial control, are preserved as source evidence but are not promoted into inferred legal statuses. Applicant-series observations remain `pending` because their positive population evidence is the applicant register.

## Identifier policy

Identifiers are never repaired or inferred. Standard 11-digit VAT/tax identifiers and 16-character fiscal codes are exposed as structured identifiers only when positively present in the source. Short numeric strings and foreign identifiers remain in `identifier_field_raw` without attempted reconstruction.

The reviewed logical-observation identifier distributions are:

- provincial listed: 1,169 observations with one strict identifier; 12 raw-only;
- provincial applicants: 498 with one strict identifier; 4 raw-only;
- post-sisma listed: 1,660 with one strict identifier; 19 raw-only;
- post-sisma applicants: 424 with one strict identifier; 6 raw-only.

Examples of raw-only evidence include foreign identifiers such as `ES-B12371126` and San Marino operator codes. These values are retained as published rather than normalised into Italian identifiers.

## Reviewed malformed source dates

Four physical listed rows are genuine source observations but contain visibly malformed printed dates. They are retained exactly and fail-closed by source key, page/table/row locator and complete extracted row. The malformed field is preserved in the raw source fields; the corresponding normalised date is left empty. No correction is inferred from the protocol text or neighbouring rows.

- provincial listed, page 154 table 1 row 11 — `EDIL GP LA MODENESE SRL`, CF/P.IVA `03807930361`: printed listing date `02/10/20218`; observed expiry `31/08/2023`; `Aggiornamento in corso`.
- post-sisma listed, page 32 table 1 row 5 — `ARTE E RESTAURO S.R.L.S.`, CF/P.IVA `03903570368`: listing date `22/10/2024`; printed expiry `18/008/2027`; ordinary listed note `-`.
- post-sisma listed, page 62 table 1 row 4 — the same `EDIL GP LA MODENESE SRL` observation with printed listing date `02/10/20218`.
- post-sisma listed, page 144 table 1 row 4 — the same `EDIL GP LA MODENESE SRL` observation repeated in another source section with printed listing date `02/10/20218`.

Dropping these rows would understate the source populations. Correcting the dates would invent evidence. The approved parser therefore does neither.

## Reviewed repeated-row variation

A small number of otherwise equivalent sector repetitions contain protocol-text or casing variants. These variants are retained in provenance fields and do not alter the grouping key. The reviewed boundary contains one such group in the provincial listed series and six in the post-sisma listed series. For example, the provincial repetitions of `M.S. PLANT TECHNOLOGY S.R.L.` (`03677930368`) carry inconsistent protocol-date text while sharing the same entity, listing/expiry dates and update status. The parser preserves both protocol strings and does not choose a corrected value.

## Integration contract

The intended canonical publication treatment is:

- `modena-provincial`: ordinary provincial register, listed + applicant populations;
- `modena-post-sisma`: separate post-earthquake register, listed + applicant populations;
- four independently byte-pinned source series;
- 3,792 source-backed public observations in total;
- no cross-register deduplication between the ordinary and post-sisma registers;
- `durable_evidence_verified=false` until independent durable evidence is established under the repository's evidence-governance work.

At the pre-integration boundary, adding Modena would move the public registry from 54,183 to 57,975 observations, from 47 to 48 published Prefectures, from 48 to 50 published registers, and from 47 to 48 mapped Prefectures. Those national totals are only production claims after the complete national build and publication gates pass.
