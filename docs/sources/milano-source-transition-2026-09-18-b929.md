# Milano source transition — later 18 September 2026 boundary (`b929`)

## Scope

A national fail-closed publication build detected that the official mutable Milano combined White List table no longer matched the approved same-day SHA-256 `8dd6ce95d933f6b892e056bdec5bc78a985bb6485504055cd7cbde0e8cbdad5c`. This review approves only the newly observed official-source boundary. It does not infer any legal effect from a source status transition.

## Independent source captures

Two cache-bypassed captures of `https://whitelist.prefmi.it/elenco/elenco.php` were byte-identical at **969,548 bytes**, SHA-256 `b92945af542b89ca99122d60a6f2d1c4c22359bb2c1bbe7c40672c7738bbc58a`. Two independent captures of the official registered-only sibling, `https://whitelist.prefmi.it/elenco/elenco_iscritte.php`, were also byte-identical at **561,860 bytes**, SHA-256 `20714806f285559da9bbfb51203e7329e990112224643bcb6a0bed7a473ef8e2`.

The combined source remains structurally stable at **10 tables, 4,208 sector rows, 2,611 logical observations and 2,611 strict identifiers**. The reviewed status distribution is **948 listed, 516 renewal/update in progress and 1,147 pending**. There is still one nonblank source note. The registered-only sibling contains **1,464 logical identities**; its identity set exactly equals the 1,464 non-pending identities in the combined source, with no missing or extra identifiers.

## Exact semantic transition from the live public boundary

Comparison with the live 61,591-record public registry found **zero Milano additions, zero removals and ten retained-identity changes**. Each of the following identities moves from `pending` to a source-explicit dated listed row, retaining the same statutory section membership. In every case the current source publishes listing date **18 September 2026** and expiry date **18 September 2027**, and the former application date is no longer represented as the current status field:

- `00772460150` — GIUSEPPE BOSISIO SRL — section 4; previous application date 27 February 2025.
- `03998810612` — MM COSTRUZIONI DI KHALIFA WALID — section 10; previous application date 25 March 2026.
- `06363290963` — MARAZZI ANGELO SRL — sections 1 and 5; previous application date 27 November 2023.
- `06895800966` — MAE ambiente s.r.l. — section 10; previous application date 25 March 2026.
- `07299620158` — Società Gas Metano SGM Impianti Srl — sections 1, 3 and 5; previous application date 27 May 2022.
- `07883430964` — GLOBAL SENDING SRL — section 6; previous application date 16 August 2023.
- `10899610967` — M.G. INSTALLAZIONI S.R.L.S. — section 3; previous application date 23 March 2026.
- `11328240152` — MAGI S.R.L. — section 4; previous application date 6 March 2026.
- `11350850969` — MAFERR SOCIETA' A RESPONSABILITA' LIMITATA — section 4; previous application date 26 November 2025.
- `13102060152` — GLI SPECIALISTI DEL VERDE SRL — sections 3 and 5; previous application date 9 March 2026.

No identity is treated as revoked, denied, cancelled or otherwise legally changed merely because of a mutable-view transition. The repository records only the source-published current status and dates.

`durable_evidence_verified` remains false for Milano pending the separately governed hosted-evidence verification; this source-transition approval concerns the official-source observation boundary only.
