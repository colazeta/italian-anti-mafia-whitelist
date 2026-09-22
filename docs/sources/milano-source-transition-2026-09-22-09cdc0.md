# Milano White List source transition — 22 September 2026 (`09cdc0…`)

## Official-source evidence

- Official landing: `https://prefettura.interno.gov.it/it/prefetture/milano/evidenza/white-list`.
- Combined listed/applicant register: `https://whitelist.prefmi.it/elenco/elenco.php`.
- Registered-only sibling: `https://whitelist.prefmi.it/elenco/elenco_iscritte.php`.
- Two independent cache-bypassed combined captures were byte-identical at **971,247 bytes**, SHA-256 **`09cdc0bf9a9cb5ee4df661d25972b9d1730f5a2158c052a75e42802960c44f46`**.
- Two independent registered-only captures were byte-identical at **561,865 bytes**, SHA-256 **`5c76ede7a994f7717a8f3d4f0cc20e6c3b63a0cdedfb23a84790ef0ab13b5e2d`**; their 1,464 identifiers exactly match the combined source's complete non-pending identity set.

## Reviewed boundary

The combined source contains **10 sections**, **4,215 company-sector rows**, and **2,615 logical observations**, all with structured identifiers: **941 listed**, **523 renewal/update in progress**, and **1,151 pending**.

Relative to the approved 21 September boundary, five identifiers are newly present, all as source-explicit `RICHIESTA ISCRIZIONE (22/09/2026)`: `00752950154` (S.M.T. STRUTTURE METALLICHE TUBOLARI srl), `03427300797` (DFG SERVIZI S.R.L.), `11933680966` (FRATELLI SOCIETA' A RESPONSABILITA' LIMITATA SEMPLIFICATA), `13808490968` (ASEEL SRL), and `13977410961` (ITAL INTERNATIONAL S.R.L.). Identifier `13826570965` (NUCERA TRASPORTI S.R.L.), previously observed pending with application date 11 May 2026, is **not present in the current source**; no withdrawal, rejection, cancellation, revocation or other legal effect is inferred. Identifiers `02657900243` (INEO SCLE FERROVIAIRE SNC), `11354220961` (TORO CAVE E IMPIANTI S.R.L) and `12210120155` (TAGLIABUE S.P.A.) are now source-explicit `IN AGGIORNAMENTO`, therefore normalised to `renewal_update_in_progress`; former listing/expiry dates are not carried into the current observations.

The net effect is **+4 observations**, moving Milano from 2,611 to 2,615. Parser grammar remains unchanged and fail-closed; only the reviewed denominators/reference boundary advance. A Milano-only national candidate contains **73,836 records**, while published authority/register/mapped counts remain **73 / 76 / 73**. This is not live until exact-head public/browser/source-link gates and deployment succeed.
