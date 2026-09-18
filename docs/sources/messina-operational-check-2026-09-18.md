# Messina White List operational source check — 2026-09-18

## Scope

This note records the positive-evidence review used to prepare the Messina ordinary White List for public integration. It covers both populations published by the Prefettura di Messina: companies already listed and companies whose applications are currently published as requests for registration.

Official landing page:

- `https://prefettura.interno.gov.it/it/prefetture/messina/evidenza/white-list`

The landing page was independently fetched twice on 18 September 2026. Both captures were byte-identical at 121,973 bytes, SHA-256 `3fbd45c92d1a863a021463f30f2a58ef40ea647888f3faaa5513f6e5ab1260d0`. The page exposes the two current attachments labelled for 11 September 2026:

- applicants: `https://prefettura.interno.gov.it/sites/default/files/0/2026-09/richieste-iscrizione-white-list-11.09.2026.pdf`
- listed companies: `https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-whitelist-iscritte-tutte-le-sezioni-online-11.09.2026.pdf`

The landing-page publication date and the listed-PDF internal source-update marker are kept distinct. The listed PDF states `ULTIMO AGGIORNAMENTO 10/09/2026` on every page; 10 September is therefore the listed source's own update boundary, while 11 September is the current attachment/landing-page edition boundary. No company event or legal-effect date is inferred from either marker.

## Capture identity

Two independent full GETs were performed for each current PDF on 18 September 2026. Each pair was byte-identical.

| population | bytes | SHA-256 | pages |
| --- | ---: | --- | ---: |
| applicants | 838,948 | `852f8f59db96f134fae8e2f95ef3b75b041699a1eb4115639d5eb3a0c5e699e4` | 3 |
| listed | 1,057,826 | `cf1219ccdfb4f6abafd1bb23edf325fdb8dc16d5611a7498378aeed51754644e` | 9 |

The raw hashes are the immutable approval boundary for publication. A later mutable official response must not silently replace these reviewed bytes.

## Listed population

The current listed PDF has one reviewed eight-column company table on each page, with the source columns for company name, registered office, secondary office, codice fiscale/partita IVA, registration date, expiry date, update-in-progress marker and statutory sections. Administrative/legend/header rows are structurally separate from company rows.

The reviewed company-row denominator is **880**, distributed by page as:

`88, 101, 102, 102, 102, 102, 101, 102, 80`.

All 880 observations contain exactly one structured identifier and all 880 identifier values are unique within this source edition. Registration and expiry fields on the reviewed company rows are valid `dd/mm/yyyy` source dates; no malformed company-date value was found in this edition.

The source's update column contains only two reviewed company values:

- blank: **663** observations → `listed`;
- `SI`: **217** observations → `renewal_update_in_progress`.

This status mapping is positive-evidence only. An old or elapsed displayed expiry date is not independently converted into an expiry legal status. The PDF itself includes legend text such as `IN AGGIORNAMENTO`, `IN CORSO DI VALIDITA'` and `SCADUTA`; those legend labels are not company rows and are not used to infer a status absent a company-level source marker.

## Applicant population

The current applicant PDF contains one five-column ruled company table per page (plus a statutory-section legend on page 1). The application date is printed in a sixth visual column immediately to the right of the ruled table. The date tokens are positionally aligned with the company rows and were separately verified from the PDF text coordinates.

The reviewed applicant denominator is **154**, distributed by page as:

`44, 69, 41`.

There are exactly 154 aligned application-date tokens, with the same page distribution. All are valid `dd/mm/yyyy` dates. The applicant publication provides positive evidence that these entities are applicants and no decision/outcome field; the 154 observations are therefore represented conservatively as `pending`.

Identifier evidence is intentionally not repaired:

- **153/154** applicant observations contain at least one structured identifier;
- there are **154 unique structured identifier values** because `AVIOMARKETING S.P.A. UNIPERSONALE` publishes two values in the same identifier cell: `02578720837 03122600830`;
- `SITEC S.R.L.` (Terme Vigliatore; sections `III-IV-V`) is the single positively identified company row with a genuinely blank source identifier cell and is retained as such rather than dropped or imputed.

## Public candidate boundary

Messina contributes **1,034 source-backed public observations** in this edition:

- listed side: 880 = 663 `listed` + 217 `renewal_update_in_progress`;
- applicant side: 154 `pending`.

Against the current live national boundary of 60,557 observations, Messina would produce a candidate national boundary of **61,591 observations**, **53 published Prefectures**, **55 registers** and **53 mapped Prefectures**, subject to parser, registry, browser, source-link, CI and deployment gates.

## Methodological constraints

- Raw source values are preserved where anomalous or blank; no identifier, address, date or legal status is reconstructed from contextual plausibility.
- Applicant status is based on positive publication in the applicant series, not on failed searches or absence from the listed series.
- Listed renewal/update status is based only on the company-level `SI` marker.
- Source hashes, page/row denominators, identifier coverage and status counts are fail-closed parser boundaries.
- The temporary expansion audit workflow is not part of the permanent integration and must be removed before a pull request is considered merge-ready.
