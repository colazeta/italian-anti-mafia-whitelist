# L'Aquila White List operational check — 18 September 2026

## Official source boundary

The current official Prefettura dell'Aquila landing page is `https://prefettura.interno.gov.it/it/prefetture/laquila/white-list-elenchi-imprese`. On 18 September 2026 it exposes both **Elenco imprese iscritte nella white list** and **Elenco imprese richiedenti iscrizione** and reports **Ultimo aggiornamento: 11 September 2026, 14:45**. This is positive evidence for both logical populations; no publication status is inferred from failed search.

The current listed PDF is `https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-imprese-iscritte-nella-white-list-nuovo-07_0.pdf` and is approved only at raw SHA-256 `15636d4d353f41f35e3c755fb4c671f3f9d5f1e03ffed32b639b9a804796c453`. The current applicant PDF is `https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-imprese-richiedenti-iscrizione-nuovo-07_0.pdf` and is approved only at raw SHA-256 `dd3c9bdd8304bb610aa941a7eed6593c9b7feea171136960a3db6f628b1e7081`. Two independent cache-bypassed captures of each resource in GitHub Actions run `35385059787` were byte-identical and each matched the approved digest. Earlier bounded source/export/parser verification runs were `35325002233`, `35325206429`, and `35325892149`.

## Parsed population boundary

The fail-closed parser produces **695 company observations**: **419 listed-side** and **276 applicant**. The listed-side population contains **209 `listed`** and **210 `renewal_update_in_progress`** observations, based only on the source note vocabulary. All 276 applicant observations are represented conservatively as `pending`; the source outcome spellings `IN ISTRUTTORIA` (273), `IN STRUTTORIA` (1), `N ISTRUTTORIA` (1), and `IN ISTRTUTTORIA` (1) are preserved as source text and are not interpreted as legal outcomes.

Structured identifier coverage is **417/419** on the listed side and **273/276** on the applicant side. Five malformed source identifiers remain raw-only rather than being repaired or guessed. The listed source contains one reviewed malformed expiry token, `28/06/207`; it is retained in the raw source field while the normalised observed expiry is deliberately left blank. The parser also freezes page count, per-page row denominators, table shape, duplicate strict-identifier sets, the exact status boundary and three source-explicit collaborative-measure notes.

## Integration and evidence posture

Both populations are bound to `laquila-ordinary` with reference date `2026-09-11`. Public integration remains evidence-first and content-addressed: publication must fail closed if either raw digest or any frozen parser boundary changes. `durable_evidence_verified` remains `false`; canonical hosted-database integration and independent durable-evidence verification remain governed separately under issue #16 and are not inferred from public-source validation.
