# Potenza White List operational check — 15 September 2026

## Official source evidence

The Ministry/Prefecture White List landing page is:

- https://prefettura.interno.gov.it/it/prefetture/potenza/white-list

The Prefettura di Potenza exposes its current public register through the official UTG Potenza web application:

- public application: https://www.utgpotenza.it/_whitelist.php
- list script: https://www.utgpotenza.it/assets/js/vis_whitelist.js
- current jTable data endpoint: `https://www.utgpotenza.it/data/vis_imprese.php?action=list&jtStartIndex=0&jtPageSize=2000&jtSorting=ragione_sociale%20ASC&cerca_ragione_sociale=&cerca_sede_legale=&cerca_stato_richiesta=0&cerca_sezione=0`

Independent live inspection on 15 September 2026 returned `Result="OK"` and `TotalRecordCount="1034"`. The public UI independently displayed `1034 records`. This is positive evidence for a current combined public population, not an inference from search failure or from an unavailable attachment.

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

The endpoint publishes `data_istanza`, `data_iscriz` and `data_scad_iscriz` as ISO dates or null. Null dates remain absent. The parser does not reconstruct missing dates. Raw identifiers are preserved. Only syntactically valid 11-digit VAT/tax identifiers or 16-character alphanumeric tax codes enter the normalised identifier list; malformed source strings are neither padded nor repaired.

The list response does not expose sector membership in each returned company object. The first parser stage therefore leaves `requested_activities` empty rather than imputing a sector. The application separately exposes sector filters and a per-company `vis_sezioni.php` child view; sector enrichment must be based on positive source evidence before it can be added to canonical observations and is not inferred from the list response.

## Parser and validation state

Parser: `src/white_list_archive/parsers/potenza_webapp.py` (`potenza_combined`, version 2).

The parser requires a complete response (`TotalRecordCount == len(Records)`), unique positive numeric source ids, the reviewed field schema, valid source date typography and one of the positively reviewed status patterns. It uses the stable source id in `record_locator` so alphabetical reordering cannot relabel an observation.

The current 1,034-record and status denominators have been established from the official endpoint through the source-validation workflow. Exact date, identifier and note denominators are intentionally not frozen here until the version-2 parser completes two independent live captures and the full validation suite on the branch.

`canonical_integration_validated=false` at this stage. `durable_evidence_verified=false`; immutable evidence promotion remains a separate infrastructure control and is not inferred from live-source availability.
