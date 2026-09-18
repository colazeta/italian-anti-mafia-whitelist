# Taranto operational source check — 18 September 2026

## Scope

This note freezes the evidence boundary used to integrate the current official Taranto White List populations into the public national registry. It concerns source-backed observations only and does not infer legal effect from absence, malformed source fields, or a status transition.

## Official sources

- Listed population: https://prefettura.interno.gov.it/it/prefetture/taranto/white-list-elenco-imprese-iscritte
- Applicant population: https://prefettura.interno.gov.it/it/prefetture/taranto/elenco-imprese-richiedenti-liscrizione-nella-white-list

Both resources are mutable official HTML pages. Repeated independent no-cache captures were used before approval. Publication therefore fails closed on the complete parsed semantic digest; the raw capture SHA-256 is retained as provenance rather than used as the approval boundary.

## Registered-company table

Repeated captures were byte-identical at 150,817 bytes with raw SHA-256 `545d6db44a8f68ec1e9ef460a4a8129e64d77385bfab318f8d050051219643c9`. The parser yields exactly 388 observations: 212 `listed` and 176 `renewal_update_in_progress`. Structured identifier coverage is 381/388; seven source identifier values remain raw-only. Eight rows contain at least one malformed source date. Those strings are retained in provenance and are not repaired by inference. The approved contract-safe semantic SHA-256 is `27211daaa4734c29bc0f48d9a86e229d04671a150fcad997b8045d997e6bab92`.

The parser accepts only the explicitly observed note semantics: blank note -> `listed`; `In fase di rinnovo` and `In fase di aggiornamento` -> `renewal_update_in_progress`. A new status lexeme is a fail-closed error.

## Applicant table

Repeated captures were byte-identical at 107,423 bytes with raw SHA-256 `ade85a5326dc8aa99c4cc2695bad87aee897964cd4c10c59b665793ec3d900f6`. The parser yields exactly 212 pending observations. Structured identifier coverage is 211/212; one source identifier remains raw-only. No malformed application dates were observed in the approved boundary. The approved contract-safe semantic SHA-256 is `b6bfcea34e1ff19a79164b4b0b13acbd55a8985c2cec66048d719e6704155982`.

## Publication boundary

The combined Taranto publication population is 600 source-backed observations: 212 listed, 176 renewal/update in progress, and 212 pending. There are 592 observations with a structured identifier and eight with a non-empty raw identifier that deliberately does not pass strict identifier normalisation. All 600 record locators must remain unique.

At the pre-Taranto live national baseline of 59,042 records / 50 published Prefectures / 52 registers, successful integration produces the candidate boundary 59,642 records / 51 published Prefectures / 53 registers / 51 mapped Prefectures. Canonical hosted-database integration and durable-evidence governance remain separate from this public-source validation boundary.
