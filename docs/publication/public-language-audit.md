# Public-language audit — 8 September 2026

Baseline: `3cfdcc1` / PR #37. All nine live sections inspected. The former static
payload is preserved in `public-portal-baseline-2026-09-08.json`; source evidence,
canonical identities, database, parsers and private Explorer are unchanged.

## Inventory and disposition

| Visible item before | Classification | Denominator / after |
|---|---|---|
| 4 published Prefectures (registry, overview, coverage, footer) | PUBLIC_CORE | Distinct authority keys in published observations; compact registry line and directory |
| 5 published registers (registry, overview, footer) | PUBLIC_CONTEXT | Distinct register keys; retained in footer and filters |
| 5,052 public observations | PUBLIC_CORE | Presenze negli elenchi; explicitly not nationally distinct companies |
| 8 current source versions | PUBLIC_CONTEXT | Eight distinct source-series/reference-date/content identities; enumerated in edition tables, not called permanently archived editions |
| 107 national authorities | MISLEADING_OR_UNNECESSARY | Includes the Ministry’s `sito-tipo` website template. Exact-key public exclusion yields 106 territorial authorities; the raw discovery evidence is unchanged |
| 34 mapped sources; 30 mapped but unpublished; 73 unmapped (72 after excluding the template) | PUBLIC_CONTEXT | Availability filter counts computed from directory rows; labels explain publication separately from source discovery |
| 59 source series | TECHNICAL_ONLY | Removed from public display/payload; versioned source inventory retained |
| 35 register scopes; 30 complete; 5 incomplete | TECHNICAL_ONLY | Listed/applicant discovery completeness, not ingestion completeness; internal ledger and #20 retained |
| Mapped yes/no alongside mapping status | MISLEADING_OR_UNNECESSARY | Redundant column removed |
| Series count and publication-model codes per authority | TECHNICAL_ONLY | Removed from directory display; already approved directory downloads retained |
| Last project check | PUBLIC_CORE | Relabelled “Pagina verificata il”; explicitly a recorded page-path verification, not monitoring freshness |
| Last source update | MISLEADING_OR_UNNECESSARY | Replaced by approved edition reference date; page modification date no longer masquerades as edition date |
| Static build date / PUBLIC EXPERIMENTAL VIEW | MISLEADING_OR_UNNECESSARY | Removed from display; generated-at is not called successful source monitoring |
| Eleven numbered Cosenza history links, 2024–2026 | PUBLIC_CORE | Individuated editions with official links; no claim all bytes are permanently archived or all company rows searchable |
| `official_current` / `official_historical` | TECHNICAL_ONLY | Human description of discovered edition; prior evidence retained |
| 1,298 canonical addresses, 624 candidates, 674 not-found | TECHNICAL_ONLY | Removed from site payload/display; frozen Cosenza evidence retained in repository |
| 48.07% coverage, 82.49% weighted precision, 39.65% estimated yield | TECHNICAL_ONLY | Linked from secondary technical documentation; no national quality claim |
| 0 auto-accepted; class samples 36/28/14, correct 36/16/12, precision 100/57.14/85.71% | TECHNICAL_ONLY | Same treatment; no underlying review deletion |
| Status filter counts, result counts, page/row ranges | PUBLIC_CORE | Published observations after the applicable filters; behaviour preserved |
| Company status, dates, expiry, edition, row reference | PUBLIC_CORE | Same values and semantics; clearer surrounding labels |
| Public locator, hash, parser/version in company detail | PUBLIC_CONTEXT / TECHNICAL_ONLY | Existing detail provenance retained, labels clarified; no identity changes |
| Source-field JSON in company detail | PUBLIC_CONTEXT | Existing approved source observations preserved; not reviewer notes |
| Parser diagnostics and identifier coverage in JSON metadata | TECHNICAL_ONLY | Kept in build-work diagnostics, outside Pages artifact |
| Contract version and SOURCE → CORE → PUBLICATION footer | TECHNICAL_ONLY | Replaced by ordinary loading/status text |
| Numbered core/geo processing stages | MISLEADING_OR_UNNECESSARY | Ordinary Italian description of collection and interpretation |

## Added information and reproducibility

- Latest available edition is the maximum reference date among published observations.
- “Ultima verifica completata dei documenti pubblicati” is the latest successful
  document verification timestamp in a fully completed build. It is unknown if any
  source lacks such a timestamp. It is **not** a successful landing-page monitoring
  check or proof that no newer edition exists.
- All aggregate computations are tested independently of supplied metadata counters.
- Company observations are checked against an explicit recursively closed field
  contract. Unknown nested fields fail closed. The full Pages directory has an
  exact filename allow-list; internal diagnostics cannot enter via another file.
- National canonical company deduplication remains unasserted by the existing
  public source-observation product. The canonical database is untouched.

## Validation record

- Baseline: all 117 existing Python tests passed locally.
- Revised suite: all 127 Python tests passed locally before CI.
- All 5,052 previously published company observations survive the closed contract
  with exact dictionary equality; no source-record or canonical-identity edits.
- JavaScript syntax checks and full artifact allow-list validation pass locally.
- Commit a895aff passed all CI, the full eight-document source rebuild and the
  unchanged Cosenza canonical integration benchmark (run 34251565208).
- GitHub browser tests passed at 1440×900 and 390×900. All fourteen screenshots
  were manually inspected: registry, detail and five other sections at both widths.
  Search, filters, keyboard detail access and public-boundary assertions passed.
  Live deployment inspection remains a post-merge check.
- The bounded link audit returned HTTP 200 for all 128 territorial/source links.
  The sole HTTP 403 was the non-territorial sito-tipo template, now excluded.
  These results are availability checks, not current-edition monitoring claims.
- Phase 1 remains open until the required CI, rendered checks and link results have
  been reviewed. National expansion has not started.

Operational checkpoints: [working record](working-record.md).

The browser gate caught and corrected cursor placement after search-field redraw;
continuous typing now preserves both focus and selection in both searches.

The baseline published directory contains the Ministry entry `sito-tipo` / “Sito tipo”,
a website template rather than a territorial authority. The publication directory
excludes this exact key. The acquisition/discovery code and original row remain
unchanged; no canonical authority or company is removed.
