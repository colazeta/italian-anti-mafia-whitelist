# Milano source transition — 17 September 2026

## Scope

This note records a fail-closed transition of the current mutable Milano White List web application. It does not infer legal status, cancellation grounds or completeness from search failure. The official combined table remains the sole ingested source; the registered-only view is used only as independent corroboration.

## Official surfaces

- Prefettura landing page: https://prefettura.interno.gov.it/it/prefetture/milano/evidenza/white-list
- combined listed/applicant table: https://whitelist.prefmi.it/elenco/elenco.php
- registered-only sibling: https://whitelist.prefmi.it/elenco/elenco_iscritte.php

## Independent captures

Two independent no-cache captures on 17 September 2026 were byte-identical for each current official view.

| view | bytes | SHA-256 | logical identities | physical/sector rows |
| --- | ---: | --- | ---: | ---: |
| combined | 970,799 | `37fd59b67b153dd642298c7143de4aa1bc57bb1cced0a9310bc9539a79078215` | 2,612 | 4,213 |
| registered-only sibling | 557,481 | `7f5c7dcc3288387d15125aee1f8aee4e271e5743ecc3a6e9da229873cc1f4848` | 1,450 | 2,454 |

The combined table parses to exactly **933 listed + 517 renewal/update in progress + 1,162 pending = 2,612** observations, all with strict identifiers. The registered-only sibling parses to **977 listed + 473 renewal/update in progress = 1,450** observations. Its identity set is exactly equal to the combined table's non-pending identity set; no pending identity appears in the sibling.

## Exact transition from the approved 16 September boundary

The approved combined edition contained 2,618 logical observations and 4,220 sector rows at SHA-256 `b360e209f3997894a3e7408e5be7f07d77cddca0c3490581ff3410218a02d9a8`. The current edition adds no identity and changes no status among the 2,612 retained identities. Six previously listed identities are absent from both current official views:

| identifier | name in approved edition | previous sections |
| --- | --- | --- |
| 04793740962 | RIZZI TOBIA DI RIZZI PIETRO SRL | Sezione 4 |
| 06960770961 | V.M.V. Costruzioni Generali Srl | Sezioni 3, 10 |
| 07693660156 | AIR ENTERPRISE SRL | Sezione 6 |
| 09835880155 | SAVING SHIPPING & FORWARDING SRL | Sezione 6 |
| 10674330963 | KRUGER A/S | Sezione 3 |
| 11016700152 | SPREAFICO TRASPORTI SRL | Sezione 6 |

All six records carried a source-explicit expiry date of **17 September 2026** in the approved edition. This is recorded as source evidence only: absence from the current views is not interpreted as a cancellation, adverse decision or any other legal conclusion. V.M.V. Costruzioni Generali Srl appeared in two sections, so six logical removals correspond to seven fewer sector rows.

The registered-only sibling also changed byte identity from the previously corroborated SHA-256 `4509948e4baf91ed5c92bd5940a2fca1cd5f9a6fd21f553c4864e68735e36608` to the current hash above while preserving exact cross-view identity consistency.

## Provenance and retention

The parser remains fail-closed on source structure, denominators, statuses and configured content identity. `durable_evidence_verified` remains false: the current official web application is mutable and this transition does not claim independent immutable archival custody. The 17 September date is a capture/reference boundary, not an inferred company event or legal-effect date.
