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

The public application exposes two explicit request states in its interface: `Richiesta in corso` and `Iscritta`. The current list endpoint provides both `stato_richiesta` and `agg_incorso`. The parser therefore uses only the following positively reviewed combinations:

- `stato_richiesta=1`, `agg_incorso=0` → `pending`;
- `stato_richiesta=2`, `agg_incorso=0` → `listed`;
- `stato_richiesta=2`, `agg_incorso=1` → `renewal_update_in_progress`.

Any other combination fails closed pending review. `iscriz_scaduta` contains opaque source markers such as `NE`, `G` and `R`; these are retained as provenance and are not assigned a legal meaning. Free-text `note` is likewise provenance only and cannot override the source-status mapping.

The endpoint publishes `data_istanza`, `data_iscriz` and `data_scad_iscriz` as ISO dates or null. Null dates remain absent. The parser does not reconstruct missing dates. Raw identifiers are preserved. Only syntactically valid 11-digit VAT/tax identifiers or 16-character alphanumeric tax codes enter the normalised identifier list; malformed source strings are neither padded nor repaired.

The list response does not expose sector membership in each returned company object. The first parser stage therefore leaves `requested_activities` empty rather than imputing a sector. The application separately exposes nine sector filters; sector enrichment must be based on positive source evidence before it can be added to canonical observations.

## Parser and validation state

Parser: `src/white_list_archive/parsers/potenza_webapp.py` (`potenza_combined`, version 1).

The parser requires a complete response (`TotalRecordCount == len(Records)`), unique positive numeric source ids, the reviewed field schema, valid source date typography and one of the reviewed status combinations. It uses the stable source id in `record_locator` so alphabetical reordering cannot relabel an observation.

The current 1,034-record denominator has been established from the official endpoint and UI. Exact status, date, identifier and note denominators are intentionally not frozen in this note until the branch source-validation workflow parses the entire live endpoint on a GitHub runner. This prevents manual transcription or partial-page inspection from becoming canonical evidence.

`canonical_integration_validated=false` at this stage. `durable_evidence_verified=false`; immutable evidence promotion remains a separate infrastructure control and is not inferred from live-source availability.
