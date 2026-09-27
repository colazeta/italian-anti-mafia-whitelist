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

## Current-boundary revalidation — 17 September 2026

A fresh current-boundary check was performed against the same official UTG Potenza data endpoint already established through the Ministry White List chain. Two independent complete GETs were byte-identical: **438,471 bytes**, SHA-256 **`24fbb61f7ae028a0a2fee8d7d4c89d42ceefdf18fc6d69298a1df0549b78c820`**, `Result=OK`, `TotalRecordCount=1035`, and 1,035 distinct numeric source ids. The parser contract and source schema are unchanged. With the 17 September observation/reference boundary, the approved production semantic SHA-256 is **`96b5227dd78fc83b78a2fd1516e8a5cfae6d482be97351f1e8c71c641e7e6316`**.

The current parsed population is **1,035 observations**: **216 listed**, **376 pending**, and **443 renewal/update in progress**. Identifier coverage is **1,034/1,035**, with the same single raw-only malformed identifier already preserved conservatively; all 1,035 observations expose an application date, while listing and expiry dates remain present for 659 observations. Requested activities remain empty because the combined endpoint still does not expose positive per-company statutory-section evidence.

The change against the approved 15 September public boundary is narrow and source-identifiable. **No source ids were removed.** Source id **656**, `SCAVONE & C. S.R.L.` (`01652690767`), is newly present with `stato_richiesta=1`, `agg_incorso=0`, and application date **2026-09-16**; it is therefore recorded as `pending`. Existing source id **359**, `MALASPINA S.R.L.`, now exposes `stato_richiesta=2`, `agg_incorso=1`, retaining its explicit listing and expiry dates; the parser therefore records the already-supported source state `renewal_update_in_progress` instead of `listed`. This records only the current public-source observation. It does **not** infer revocation, cancellation, denial, removal, or any other legal effect.


## Fresh current-source revalidation — 18 September 2026

The official UTG Potenza endpoint was captured twice independently at approximately 00:35 CEST. The complete responses were byte-identical at **438,471 bytes**, raw SHA-256 **`cb3a1816dbe54bb0a1260a63e326385bcc435e52d8928a775f7c5bc259655d30`**, `Result=OK`, `TotalRecordCount=1035`, with 1,035 distinct source ids. The strict production parser returned **216 listed**, **376 pending**, and **443 renewal/update in progress**; 1,034 validated identifiers plus one conservatively retained raw-only identifier; 1,035 application dates; 659 listing dates; 659 expiry dates; and no per-company activity inference.

The full parsed source-semantic SHA-256 is **`8b3a129f54dfb889740a6f16fddcd53294fc4269a7e311353e72dc9c7b81dd2e`**, replacing **`96b5227dd78fc83b78a2fd1516e8a5cfae6d482be97351f1e8c71c641e7e6316`**. Direct comparison with the currently served Potenza projection established that the public-relevant transition remains exactly the already-reviewed one: source id **656**, `SCAVONE & C. S.R.L.`, is the sole added id and remains pending; source id **359**, `MALASPINA S.R.L.`, is the sole existing record changing across the reviewed public fields, from `listed` to `renewal_update_in_progress`; **no source ids were removed**. The earlier raw response was not retained, so the exact auxiliary source-field value responsible for the whole-source digest drift cannot be reconstructed. The current source is therefore reapproved on fresh positive evidence rather than on an assumption of byte stability. No revocation, cancellation, denial, removal, or other legal effect is inferred.


## Current-source revalidation — 20 September 2026

The mutable official UTG Potenza endpoint was revalidated again after it caused the Palermo national candidate to fail closed on a source-row mismatch. Two independent complete no-cache captures were byte-identical: **438,054 bytes**, raw SHA-256 `aeac0b690c28fa84d317d52d79382b4b9e51de9a4c7cbfef2a841bd9a7aa1d6a`, `Result=OK`, `TotalRecordCount=1034`, and **1,034 distinct numeric source ids**.

The unchanged strict production parser yields **1,034 source-backed observations**: **215 listed**, **376 pending**, and **443 renewal/update in progress**. Structured identifiers are present on **1,033/1,034** observations; application dates on **1,034/1,034**; listing dates on **658**; expiry dates on **658**. The production parsed semantic SHA-256 is `5f8d3c7deada39f95b1da000c727b9c1f5e42bf7fe3deff06cb0ff825b1bf389`.

A direct id-level comparison against the currently approved/public 1,035-row Potenza projection isolates the change exactly: source id **237**, `PATANELLA ANTONIO & C. S.N.C.` (`01749860712`), previously observed as `listed` with application date `2019-07-04`, listing date `2019-09-19`, and expiry date `2026-09-19`, is absent from the current endpoint. There are **no new source ids** and **no source-status changes among the 1,034 surviving ids**. The disappearance is therefore recorded strictly as a change in the current mutable source population. It is **not** interpreted as revocation, cancellation, denial, withdrawal, expiry, or any other legal effect without positive official evidence of that effect.

The approved current observation boundary is therefore 1,034 rows at reference date 20 September 2026. Publication remains fail-closed on the full parsed semantic digest above; the raw digest is provenance for this capture rather than a claim that the mutable endpoint is immutable.


## Current-source revalidation — 21 September 2026

The mutable official UTG Potenza endpoint was revalidated after it caused the Lodi combined national candidate to fail closed on a source-row mismatch. The official Ministry Potenza White List landing remained positively available. Two independent complete cache-bypassed endpoint captures were byte-identical at **438,469 bytes**, raw SHA-256 `53b1792ff14c6dd99013bee525fd8064667ec25742fd9ee12a52fe258e7c82ca`, `Result=OK`, `TotalRecordCount=1035`, and **1,035 distinct numeric source ids**.

The unchanged strict production parser yields **1,035 source-backed observations**: **214 listed**, **377 pending**, and **444 renewal/update in progress**. Structured identifiers are present on **1,034/1,035** observations; application dates on **1,035/1,035**; listing dates on **658**; expiry dates on **658**. The production parsed semantic SHA-256 is `2be600833127711c7eb27bb49ca7af6fd69e07410de6cbf980c62261d47a2c36`.

A source-id comparison against the live approved 20 September 1,034-row Potenza projection isolates the public-semantic transition exactly. There are **no removed ids**. Source id **399**, `LABELLA TRASPORTI S.R.L.` (`01720980760`), is newly present as `pending`, with application date `2026-09-17`, registered office `Contrada Palettieri, snc, Rionero in Vulture`, `stato_richiesta=1` and `agg_incorso=0`. Retained source id **887**, `2 C COSTRUZIONI S.R.L.` (`01643430760`), changes only from `listed` to `renewal_update_in_progress`; its application date (`2019-10-17`), listing date (`2020-11-12`), expiry date (`2026-11-12`) and registered office remain unchanged, while the current source explicitly publishes `stato_richiesta=2` and `agg_incorso=1`.

These observations are recorded strictly as the current mutable-source state. No revocation, cancellation, denial, withdrawal, expiry, ownership equivalence or other legal effect is inferred beyond the source-published status wording. The approved current observation boundary is therefore 1,035 rows at reference date 21 September 2026. Publication remains fail-closed on the full parsed semantic digest above; the raw digest remains capture provenance.


## Current-source revalidation — 21 September 2026 (1,036-row boundary)

Two further independent cache-bypassed captures of the official UTG Potenza endpoint were byte-identical at **438,877 bytes**, raw SHA-256 `44a242d7fa8c3e7af0b5df779430a20e7ab61939aaca9cd5ac005025ddf07420`, with `Result=OK`, `TotalRecordCount=1036` and 1,036 distinct source ids. The unchanged production parser yields **1,036 observations: 214 listed, 378 pending and 444 renewal/update in progress**. The full parsed semantic SHA-256 is `05cd1ad5e0cb472d17386d76fb279b13d7e8302b73fd3e47f3a06f5175aba247`.

Relative to the live 20 September projection, source ids **399** (`LABELLA TRASPORTI S.R.L.`, `01720980760`) and **1584** (`SOLARO S.R.L.`, `05974780651`) are newly present as pending; retained source id **887** remains the previously reviewed listed-to-renewal/update transition. Relative to the already reviewed 1,035-row 21 September snapshot, **1584 is the sole residual addition**, with application date `2026-09-12`, registered office `Via Gallizzi, 31/A, Viggianello`, `stato_richiesta=1` and `agg_incorso=0`. No source ids are removed. These are current-source publication facts only; no withdrawal, denial, cancellation, revocation or other legal effect is inferred.


## 22 September 2026 current-boundary revalidation

The official Ministry Potenza White List landing remains the positive institutional discovery surface for the UTG Potenza public White List web application. On 22 September 2026 the complete combined endpoint was acquired twice independently with cache-bypassing query tokens and no-cache headers. The two responses were byte-identical at **438,877 bytes**, SHA-256 **`1d6dbaf66350aab1e62c3191695850927638412ed2750848bbcc401e1067123a`**. The production parser accepted both without schema relaxation and returned exactly **1,036 observations: 212 listed, 378 pending and 446 renewal/update in progress**, with **1,035/1,036** observations carrying a structured identifier.

Relative to the approved 21 September boundary, the source-id universe is unchanged: there are **no additions and no removals**. Exactly two retained observations change public source status, and only because the current source exposes `stato_richiesta=2` together with `agg_incorso=1`: source id **715**, **L'EUROCOMES S.R.L.**, and source id **884**, **MARGHERITA S.R.L.**, both move from `listed` to `renewal_update_in_progress`. Their current records also expose `iscriz_scaduta=G`. No revocation, suspension, cancellation, adverse measure, expiry effect or other legal consequence is inferred from these fields.

The 22 September observation boundary is approved only as a fresh mutable-source snapshot. Raw-byte provenance is pinned to `1d6dbaf66350aab1e62c3191695850927638412ed2750848bbcc401e1067123a` and public publication remains fail-closed on the full parsed semantic digest **`a044e9aa0386d0fe8deddb0a3bccd94e24ea43c002c90d91e4139d387c0dd814`** computed using the 22 September reference boundary.
