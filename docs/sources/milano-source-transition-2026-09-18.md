# Milano source transition — 18 September 2026

## Scope

Operational re-verification of the official mutable Milano White List web application after the national fail-closed build detected a SHA change. This note approves only the positively observed current source boundary; it does not infer legal effects from absence or status changes.

## Official sources

- Landing page: https://prefettura.interno.gov.it/it/prefetture/milano/evidenza/white-list
- Combined listed/applicant view: https://whitelist.prefmi.it/elenco/elenco.php
- Registered-only corroborative view: https://whitelist.prefmi.it/elenco/elenco_iscritte.php

## Reproducible boundary

Repeated cache-bypassed captures on 18 September 2026 were byte-identical within each official view. The combined view is 969,618 bytes, SHA-256 `8dd6ce95d933f6b892e056bdec5bc78a985bb6485504055cd7cbde0e8cbdad5c`; the registered-only sibling is 558,574 bytes, SHA-256 `bfad4880c80cf465d6356e7ae518149f150781de69a712c8551320f25a92b195`. A later independent recheck reproduced both exact byte identities and ten source tables in each view.

The production Milano parser, with only the new reference-date and frozen status denominators supplied at runtime, accepted the combined source without relaxing any structural invariant: 10 tables, 4,208 sector rows, 2,611 logical observations, 2,611 structured identifiers and one logical non-blank note. The resulting status distribution is 938 `listed`, 516 `renewal_update_in_progress`, and 1,157 `pending`; listing-date and expiry-date coverage are each 938, and application-date coverage remains 1,157.

## Exact semantic transition

No identifier was added or removed relative to the live 17 September boundary. The official source explicitly changed exactly two previously dated listed identities to `IN AGGIORNAMENTO`:

- `00936150150` — IMPRESA GUERINI & C. SRL
- `13072070157` — TECNOTER SRL

For both, the current source no longer supplies listing/expiry dates in those cells; the parser therefore records `renewal_update_in_progress` with blank observed listing/expiry dates. No legal consequence beyond the source-published wording is inferred.

The registered-only sibling contains 1,454 logical identities, and that identity set exactly matches the non-pending identities in the combined view. It remains corroborative and is not co-ingested as a second population.

`durable_evidence_verified` remains false pending the separate hosted-evidence governance work; this transition approval concerns official-source observations only.
