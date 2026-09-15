# Potenza White List operational check — 15 September 2026

## Official source evidence

The Ministry/Prefecture White List landing page is:

- https://prefettura.interno.gov.it/it/prefetture/potenza/white-list

The Prefettura di Potenza exposes its current public register through the official UTG Potenza web application:

- public application: https://www.utgpotenza.it/_whitelist.php
- list script: https://www.utgpotenza.it/assets/js/vis_whitelist.js
- current jTable data endpoint: `https://www.utgpotenza.it/data/vis_imprese.php?action=list&jtStartIndex=0&jtPageSize=2000&jtSorting=ragione_sociale%20ASC&cerca_ragione_sociale=&cerca_sede_legale=&cerca_stato_richiesta=0&cerca_sezione=0`

Independent live inspection on 15 September 2026 returned `Result="OK"` and `TotalRecordCount="1034"`. The public UI independently displayed `1034 records`. This is positive evidence for a current combined public population, not an inference from search failure or from an unavailable attachment.

The branch source-validation gate subsequently captured the complete endpoint twice independently. Both raw responses were byte-identical at SHA-256 `483f71b0481573651dc62e382e3e7a45cfd84509ec79f51a07194dbb3af0a6`; the normalised parser output was also identical across the two captures at semantic SHA-256 `c033d7b1f2d758f42e9b0a97d70e8f7f2278cb08608db86c2e7b600e1857cb34`.

The endpoint also exposes the server-side population predicate in its response. The material scope is `imprese.eliminato = 0` and at least one of: an enrolment expiry date not earlier than the current date; `stato_richiesta = 1`; or `agg_incorso = 1`. This means the current public response intentionally combines unexpired enrolled firms, applications in progress and enrolled firms whose update/renewal is in progress.

## Source semantics

The public JavaScript renders `stato_richiesta=1` as `in Istruttoria`, `stato_richiesta=2` as `Iscritta`, and independently renders `agg_incorso=1` as a checked `in Agg.` flag. The 15 September 2026 public response contained exactly these source combinations:

- `stato_richiesta=1`, `agg_incorso=0`: 375 rows → `pending`;
- `stato_richiesta=2`, `agg_incorso=0`: 217 rows → `listed`;
- `stato_richiesta=2`, `agg_incorso=1`: 441 rows → `renewal_update_in_progress`;
- `stato_richiesta=1`, `agg_incorso=1`: one reviewed row, source id `903`, `GAP S.R.L.S.`.

The sole `1/1` row has explicit prior-enrolment evidence: `data_iscriz=2024-11-28`, `data_scad_iscriz=2025-11-28`, while the public UI simultaneously marks the practice `in Istruttoria` and `in Agg.`. It is therefore represented conservatively as `renewal_update_in_progress`, not as a first-time pending applicant. Parser version 2 generalises that reviewed evidence only to a `1/1` row that also has both an explicit prior listing date and expiry date. A future `1/1` row lacking those prior-enrolment dates fails closed pending review.

The resulting reviewed status boundary is therefore 375 `pending`, 217 `listed` and 442 `renewal_update_in_progress`, totalling 1,034 observations.

`iscriz_scaduta` contains source markers including `NE`, `G` and `R`. Their display behaviour is observable in the official JavaScript, but the parser retains the raw marker as provenance and does not assign it an additional legal status. Free-text `note` is likewise provenance only and cannot override the source-status mapping.

The endpoint publishes `data_istanza`, `data_iscriz` and `data_scad_iscriz` as ISO dates or null. Null dates remain absent. The parser does not reconstruct missing dates. The validated current coverage is 1,034/1,034 for application dates and 659/1,034 for both listing and expiry dates.

Raw identifiers are preserved. The current endpoint has no blank identifier fields; 1,033/1,034 observations expose a syntactically valid normalised identifier and one observation retains only its malformed raw identifier. That value is not padded, truncated or repaired. Exactly one current observation has a non-empty source `note`.

The list response does not expose sector membership in each returned company object. The first parser stage therefore leaves `requested_activities` empty rather than imputing a sector. The application separately exposes sector filters and a per-company `vis_sezioni.php` child view; sector enrichment must be based on positive source evidence before it can be added to canonical observations and is not inferred from the list response.

## Parser and validation state

Parser: `src/white_list_archive/parsers/potenza_webapp.py` (`potenza_combined`, version 2).

The parser requires a complete response (`TotalRecordCount == len(Records)`), unique positive numeric source ids, the reviewed field schema, valid source date typography and one of the positively reviewed status patterns. It uses the stable source id in `record_locator` so alphabetical reordering cannot relabel an observation.

The live validation established 1,034 distinct source ids, the status distribution above, 1,033 normalised identifiers plus one raw-only malformed identifier, date coverage of 1,034/659/659 for application/listing/expiry, one non-empty note, and zero activity assignments from the combined list response. Potenza semantic tests pass on parser version 2. The ordinary repository CI on the same branch state is green; the source-validation workflow uses the same repository test extras so its full-suite result remains a separate gate before national candidate integration.

`canonical_integration_validated=true`: the national candidate build completed successfully with 51,088 public observations, 45 published Prefectures, 46 registers and 47 mapped Prefectures, including exactly 1,034 Potenza observations and 1,034 distinct Potenza record locators. `durable_evidence_verified=false`; immutable evidence promotion remains a separate infrastructure control and is not inferred from live-source availability.
