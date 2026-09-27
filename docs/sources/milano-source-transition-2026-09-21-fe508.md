# Milano source transition — 21 September 2026 current boundary (`fe508`)

## Scope

This review concerns the mutable official Milano combined White List table at `https://whitelist.prefmi.it/elenco/elenco.php`. It records source publication state only. Disappearance from the table or a move into the source-explicit renewal/update state is not interpreted as withdrawal, denial, cancellation, revocation or any other legal effect.

## Independent current-source verification

Two independent no-cache captures on 21 September 2026 were byte-identical at **968,796 bytes**, SHA-256 `fe508b739494d6af29e494f90ac45646a3d24c6bd7bd5448ccaed4d779096b6d`. The separately published registered-only sibling was also captured twice byte-identically at **561,865 bytes**, SHA-256 `5c76ede7a994f7717a8f3d4f0cc20e6c3b63a0cdedfb23a84790ef0ab13b5e2d`. Its 1,464 identifiers exactly equal the combined table's non-pending identity set.

The current combined parser boundary is 10 tables, **4,205 sector rows and 2,611 logical observations**: 944 `listed`, 520 `renewal_update_in_progress` and 1,147 `pending`. Strict identifier coverage remains 2,611/2,611. The maximum source application date is 21 September 2026; the maximum listed/expiry dates remain 18 September 2026 / 18 September 2027.

## Semantic transition

The preceding independently observed `f8573b80106db7d9ccaed82460aefe77256f17656dd00f8cedff9c3a9a812e64` boundary had 4,204 sector rows and 2,610 observations. Before canonical promotion, the mutable official source advanced again to the current `fe508` boundary. Relative to `f857`, the current source adds one pending observation, **SAN DOMENICO REAL ESTATE S.R.L.** (`06602310960`), application date 21 September 2026, section 9. It also moves four existing identities from `listed` to source-explicit `renewal_update_in_progress`: `02079720161` (R.G.F. S.R.L.), `02470450962` (LEGNANI DARIO), `10253070964` (NESCO SRL) and `13167930968` (REMSOL SRL). The current renewal/update rows do not publish listing or expiry dates.

Relative to the currently live registry, the source also retains the previously reviewed identifier correction `03998810612` → `KHLWDS89B03Z336P` for MM COSTRUZIONI DI KHALIFA WALID and still does not publish pending STONE S.R.L. (`14304140966`, application date 3 December 2025). No legal continuity or legal consequence is inferred beyond the displayed source rows.

## Reference-date semantics

The current mutable table contains a source-explicit application dated 21 September 2026 but exposes no separate reliable edition timestamp. The canonical `reference_date` is therefore advanced to **21 September 2026 strictly as the observation/capture boundary**. It is not interpreted as a publication date, decision date, registration date or other legal-effect date.

## Approval boundary

The approved candidate therefore pins raw SHA-256 `fe508b739494d6af29e494f90ac45646a3d24c6bd7bd5448ccaed4d779096b6d`, 4,205 sector rows, 2,611 observations and the 944/520/1,147 status distribution. Structural table/header/identifier validation remains fail-closed. The registered-only publication is retained as independent corroborating evidence, not merged as a second population.
