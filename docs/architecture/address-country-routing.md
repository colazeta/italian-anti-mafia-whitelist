# Address country semantics and provider routing

## Contract

Country is not inferred from the authority that publishes a White List. An Italian Prefettura can publish an address outside Italy, so the fact that the source authority is Italian is **not** evidence that `core.address.country_code = IT`.

The address model now separates three things:

1. `core.address.full_address` — immutable source-supported address text;
2. `core.address.country_code` — country only when the source itself explicitly supports it through a dedicated/source-explicit representation;
3. `geo.address_country_assessment` — versioned derived classification and provider-routing decision, with provenance and an explicit derivation reason.

A derived country therefore never rewrites source truth.

## Routing policy

The current policy is deliberately conservative:

```text
source-explicit country
  ├─ IT       -> italian_anncsu
  └─ non-IT   -> foreign_fallback

no source-explicit country
  ├─ exact, unambiguous Istat municipality prefix -> derived IT -> italian_anncsu
  ├─ validated foreign marker                     -> source-explicit foreign -> foreign_fallback
  └─ otherwise                                    -> unresolved_fallback
```

An ambiguous municipality prefix or a province-marker mismatch is not sufficient to derive Italy.

### Foreign marker guard

A parenthetical two-letter token is not treated mechanically as an ISO country code because Italian province plates can collide with ISO alpha-2 codes. `FR`, for example, is both the ISO code for France and the plate for Frosinone.

Therefore exact Italian municipality recognition is evaluated first. `FROSINONE (FR) Via ...` remains Italian. A non-Italian place marker is admitted as explicit foreign evidence only under a reviewed country-specific source-language cue. In the current Cosenza corpus this positively resolves:

```text
PARIGI (FR)Rue du Cardinal Demoine 62
```

as France (`FR`), because the source itself contains `(FR)` and the following French street-type cue `Rue`. This rule is intentionally narrow and versioned; unsupported markers remain unresolved.

## Cosenza expected routing

For the frozen 28 June / 3 August 2026 Cosenza population of 1,298 canonical address strings, the corrected routing gate is expected to produce:

- `italian_anncsu`: **1,260**;
- `foreign_fallback`: **1**;
- `unresolved_fallback`: **37**.

The 37 unresolved cases are mostly abbreviated or otherwise non-exact municipality forms. They are **not** silently labelled Italian merely because the White List is published by the Prefettura di Cosenza.

Under this routing, ANNCSU is evaluated only on the 1,260 defensibly Italian addresses. The previously validated 624 candidates remain unchanged; operational ANNCSU `not_found` becomes 636 and 38 addresses are `unprocessed` by ANNCSU because they belong to foreign/unresolved fallback routes.

## Validation semantics

`address_results.csv` and the validation summary expose separately:

- `source_country_code`;
- `derived_country_code`;
- country classification status;
- provider route;
- derivation reason;
- provider-normalised country, where a provider candidate exists.

Source/provider country conflict metrics compare only actual source-explicit country evidence against provider output. Derived country is reported separately.

The frozen 7 September 2026 Cosenza review remains a historical gold standard. Its candidate coverage (48.07%), weighted candidate precision (82.49%) and estimated validated yield (39.65%) are not rewritten merely because provider routing is now semantically cleaner. The operational distinction is that foreign/unresolved cases are no longer mislabelled as ANNCSU `not_found`.

## Downstream implications

- ANNCSU remains the official-first route only for defensibly Italian addresses.
- `foreign_fallback` and `unresolved_fallback` are explicit inputs to the configurable fallback-provider workstream (#33).
- National ANNCSU orchestration (#31) must derive required regional inputs from the `italian_anncsu` population, not from all addresses blindly.
- Any future stronger/fuzzy country or municipality inference requires separate versioned validation evidence; it must not mutate the literal source address.
