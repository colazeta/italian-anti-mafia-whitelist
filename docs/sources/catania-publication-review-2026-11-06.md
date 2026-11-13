# Catania — candidate public White List edition, 6 November 2026

> Status: **source-backed release candidate, pending exact public selection**. This note is not an administrative certificate or an invented public approval.

## Primary-source identity

Official authority: Prefettura — Ufficio territoriale del Governo di Catania. The official [White List Provinciale](https://prefettura.interno.gov.it/it/prefetture/catania/comunicazioni/white-list-provinciale) publication endpoint exposes the following two exact official attachments; the dated notice identifies them as updated on **6 November 2026**. The Prefecture robot successfully fetched and archived both attachments on 13 November 2026 and verified the SHA-256 identities before the parser executed.

| Source key | Logical population | SHA-256 | Exact published document |
|---|---|---|---|
| `catania-listed` | listed | `ccd1a9abbf8144ae4edb43c7df07c1648c0273196a7aff278c03c62b39b733ff` | `white-list-iscritti-aggiornato-06-novembre-2026.xlsx` |
| `catania-applicants` | applicant | `adb590642773f68047e207beeb6aace3555ece674b6b64872c1347c0c7d4ffbb` | `white-list-richiedenti-aggiornato-06-novembre-2026.xlsx` |

These are source-file identities, **not** approved administrative `SourceEdition` rows or legal effective dates. The date is an explicitly observed official publication boundary, not an imputed date for individual company decisions.

## Strict extraction and quality

The November parser lives in `src/white_list_archive/parsers/catania_openxml_november.py`, with distinct parser keys from the frozen September implementation. Each input requires an exact full-byte match. Spreadsheet sheet, dimensions, headers, range of company rows, 11-row footer and all nonempty cells outside the company block are checked before publication records are produced.

| QA measure | Listed file | Applicant file |
|---|---:|---:|
| Source observations | **1,864** | **173** |
| Source status | 1,662 listed; 202 source-explicit renewal/update in progress | 173 pending |
| Strict identifiers | 1,819 | 172 known-named rows, with one blank source name |
| Notable retained source anomalies | 4 nonstandard sector-cell values; 2 malformed listing dates; 2 blank offices; 5 nonrenewal raw notes | One raw source row with blank company name; its observed identifier, office and date are not projected into an inferred company name |
| Source-derived formulas | 1,581 standard expiry formulas and their cached calendar dates checked | Not applicable |

Four exact listed-source sector cells are pinned by **row number and SHA-256 of the raw cell**. Only valid source-explicit sector tokens are retained; fused/invalid tokens are not split to invent sectors. Malformed dates remain raw and are not normalised. Blank names are not populated from identifier, office or adjacent rows.

Expiry or appearance/disappearance between editions is not evidence of revocation, refusal, cancellation, interdiction, automatic renewal or any other new legal event. This dataset is an observation of the official file at its reference date.

## Public change boundary

The previously selected public derivative contains **74,347** source observations across **74 Prefectures and 77 registers**. The November Catania candidate contains **74,428** across the same authorities/registers. The incremental acceptance check compares all non-Catania record payloads (not just aggregate counts) with the SHA-pinned previous public snapshot and requires them to remain identical. Both Catania populations must be present, and their SHA/date, counts, statuses and raw blank-name count must reconcile exactly.

All geographic geocoding, ANNCSU/ISTAT matching and coordinates are optional and intentionally excluded. Official source address fields are preserved without derived geographic interpretations.

The public contract remains closed to unreviewed fields. Build includes parser/row checks, integrity, public schema/privacy-field checks, cross-source consistency, browser checks and official-link diagnostics. A passing candidate build is **not** in itself permission to promote new individual observations.

## Controlled release selection

The existing public selector `data/publication/public_snapshot.json` must continue to name the last approved release until a separate release-specific decision. After all candidate checks pass on the main exact commit, the `Public registry candidate` workflow produces immutable public CSV/JSON derivatives and their five-file SHA/byte manifest. Promotion should be done by changing only that selector to the exact verified manifest and letting the single `Public retro portal` publisher validate and deploy. Preserve the previous selector and previous release for immediate rollback.

No change in the underlying archive is construed as automatic authorisation to redistribute original bytes. The public candidate contains only approved-field representations of the already publicly accessible Prefecture observations. The specific new release still needs recorded owner clearance before public promotion.
