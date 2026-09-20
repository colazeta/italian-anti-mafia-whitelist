# Ferrara operational source check — 20 September 2026

## Current official surface

The current Ferrara Prefecture publication surface was verified on 20 September 2026 against the official `prefettura.interno.gov.it` host.

Primary landing:

- https://prefettura.interno.gov.it/it/prefetture/ferrara/evidenza/white-list

The current official surface positively exposes three distinct publication pages:

1. ordinary White List — companies entered in the register:
   - https://prefettura.interno.gov.it/it/prefetture/ferrara/white-list-elenco-imprese-iscritte
2. ordinary White List — applicant companies:
   - https://prefettura.interno.gov.it/it/prefetture/ferrara/white-list-elenco-imprese-richiedenti
3. reconstruction White List — companies entered in the register, split across seven activity-sector PDFs:
   - https://prefettura.interno.gov.it/it/prefetture/ferrara/white-list-ricostruzione-elenco-imprese-iscritte

A GitHub-hosted source probe fetched all three publication pages successfully with HTTP 200, required exactly one PDF on each ordinary page and exactly seven PDFs on the reconstruction-listed page, then captured every PDF twice independently with cache bypass. Both captures of every resource were byte-identical. Failed future searches or fetches must not be interpreted as evidence that a population is not published.

The official surface verified in this check positively establishes an ordinary applicant population. It also positively establishes a reconstruction listed population. This check does **not** infer that a reconstruction applicant population is absent, unpublished or empty merely because no such series is exposed by the verified pages above.

The page-rendered update metadata observed by the runner included `24 Agosto 2026` on all three verified publication pages. Search-index metadata for the reconstruction page was not fully consistent with that rendering. For that reason this operational check uses **20 September 2026 only as the verification timestamp** and does not assign a source-reference/legal-effect date from page metadata alone. Individual dates remain source fields and must be parsed conservatively.

## Verified current resources

All byte counts and SHA-256 values below are from two independent byte-identical captures on 20 September 2026.

### Ordinary listed

- URL: https://prefettura.interno.gov.it/sites/default/files/0/2026-08/white-list-provinciali-elenco-imprese-iscritte-agg11112024_0.pdf
- bytes: `1,344,441`
- pages: `87`
- SHA-256: `0d631e678b7f85bb84d265b09b8de6fcffa09cc4a49b84be37c6c1d7b9dcd6d9`
- positive content: Ferrara ordinary White List, sectioned listed-company table with company name, registered office, tax/VAT identifier, registration date, expiry date and notes; rows can explicitly carry `RINNOVO IN CORSO`.

### Ordinary applicants

- URL: https://prefettura.interno.gov.it/sites/default/files/0/2026-08/white-list-elenco-imprese-richiedenti_0.pdf
- bytes: `187,470`
- pages: `5`
- SHA-256: `c7437cdeebd1a64d4a6de8bbe5e8c108a688269409b7c772e8a6c87162e588e7`
- positive content: `WHITE LIST – ELENCO IMPRESE RICHIEDENTI`, with company name, registered office, tax/VAT identifier, application date and requested activities.

### Reconstruction listed — sector A

- URL: https://prefettura.interno.gov.it/sites/default/files/0/2026-08/h-bis-a-fornitura-moduli-prefabbricati-e-dei-relativi-arredi_is_0.pdf
- activity: supply of prefabricated modules and related furnishings
- bytes: `261,640`
- pages: `8`
- SHA-256: `4fdf292b1538892c7b5ff79d3c0c14e0ed3b5830effb791316b0fddb8c90ae01`

### Reconstruction listed — sector B

- URL: https://prefettura.interno.gov.it/sites/default/files/0/2026-08/h-bis-b-demolizione-di-edifici-ed-altre-strutture_is_0.pdf
- activity: demolition of buildings and other structures / site preparation
- bytes: `634,868`
- pages: `35`
- SHA-256: `97d9af0d587af0b7d93d31df33bd612440bf5be5b48b57872d436e2afeb164ec`

### Reconstruction listed — sector C

- URL: https://prefettura.interno.gov.it/sites/default/files/0/2026-08/h-bis-c-movimenti-di-terra_is_0.pdf
- activity: earthmoving
- bytes: `443,763`
- pages: `23`
- SHA-256: `99f519101dccff84dddd9753f0d6fa27170c33b1982858afe9fdf9ebbc63c57e`

### Reconstruction listed — sector D

- URL: https://prefettura.interno.gov.it/sites/default/files/0/2026-08/h-bis-d-noleggio-con-coducente-mezzi-speciali_is_0.pdf
- activity: hire of special vehicles with driver
- bytes: `225,912`
- pages: `7`
- SHA-256: `07c27b38e48a879aa0d1efff4710bf7dbbf1bb323e59f62eb0b0b796a75a46d8`

### Reconstruction listed — sector E

- URL: https://prefettura.interno.gov.it/sites/default/files/0/2026-08/h-bis-e-fornitura-e-posa-in-opera-impianti-fotovoltaici_is_0.pdf
- activity: supply and installation of photovoltaic systems
- bytes: `343,103`
- pages: `13`
- SHA-256: `9cea950d37f653d0356edb9a46a7f43665a382e771c969bc93f7027f95fecf9e`

### Reconstruction listed — sector F

- URL: https://prefettura.interno.gov.it/sites/default/files/0/2026-08/h-bis-f-fornitura-e-manutenzione-impianti-tecnologici_is_0.pdf
- activity: supply and maintenance of technological systems
- bytes: `382,744`
- pages: `14`
- SHA-256: `ac7dd77f1c4633c27a62c0ad7e074f507a10b091a327c2fc1072cfb52fd45664`

### Reconstruction listed — sector G

- URL: https://prefettura.interno.gov.it/sites/default/files/0/2026-08/h-bis-g-fornitura-beni-necessari-ricostruzione_is_0.pdf
- activity: supply of goods needed for reconstruction
- bytes: `180,998`
- pages: `3`
- SHA-256: `0657c7e0f0b9fb8ad7f0b341682716d695132e61131adc92407627a5cae82bae`

## Parser boundary to preserve

The Ferrara sources are table-like PDFs but the reconstruction population is distributed across seven sector documents. Parser/integration work must therefore distinguish **physical sector rows** from **public company observations**.

The same company can recur across reconstruction sectors. Repetitions must not be collapsed merely because company name or identifier matches. A defensible grouping may combine sector occurrences only when the company identity, interpreted outcome and normalised source date pair are compatible. Conflicting date pairs must remain distinct source-backed observations. Sector membership should remain provenance, not be discarded.

The following anomalies were positively observed during source verification and must be preserved or explicitly reviewed rather than silently repaired:

- ordinary listed contains the 12-digit raw identifier `010215770387`; it must not be padded, truncated or reinterpreted merely to satisfy an identifier format;
- reconstruction sector B contains `05/03/204` for `W.E.W.S. DI MUSAKU ESMIRALDA`; the malformed date must not be silently changed to a guessed year;
- listed and reconstruction rows can explicitly carry `RINNOVO IN CORSO`; this is evidence for the repository's `renewal_update_in_progress` outcome rather than a reason to drop the row;
- sector PDFs can contain the same company with different registration/expiry pairs; those conflicts are substantive source variation and must remain visible;
- PDF line wrapping can split company names, localities, identifiers and notes across visual lines, so line-count heuristics alone are not an approved parser.

No source-row, logical-observation or outcome denominator is approved by this document. Those counts become authoritative only after a fail-closed parser has been bound to the pinned resources above and validated against their actual table geometry/semantics.

## Evidence boundary

This check verifies the current official source surface and immutable byte identities needed for parser work. It does not infer legal effects from expiry dates, renewal notes, missing rows or future source changes. It does not infer completeness beyond the positively verified series and attachments. Any later source drift must fail closed and be reviewed rather than absorbed automatically.
