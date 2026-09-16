# Prefecture history and delta view

The public portal exposes a single **Storico** tab. Its purpose is deliberately narrow: select a Prefecture and inspect how each archived source series changed between its latest two comparable editions. The registry and current statistics retain their existing behaviour.

The historical model remains observational. It describes differences between published source editions; it does not reconstruct administrative decisions and it does not rank Prefectures.

## Public interface

The page follows the portal's existing compact, table-first visual language rather than introducing a separate dashboard.

- One Prefecture selector is the primary control.
- For every source series of that Prefecture, a plain table shows the previous comparable edition, the latest edition, days between them, observations in A and B, and the net delta.
- Opening a series shows an A/B table for the total and each reported status.
- Where an approved row-level comparison exists, a second table reports newly observed presences, presences no longer observed, modified common rows and the subset involving a status change.
- A final table lists all archived editions for the selected Prefecture and links back to the official documents.

There is no separate public **Aggiornamenti** tab, timeline chart, stacked-status chart, KPI-card layout, as-of mode, cadence ranking or advanced filter panel. These additions obscured the narrower analytical question the page is intended to answer. The underlying edition, comparison and check evidence is still retained for audit and future analysis.

Series with different registers, population scopes or source keys are never added together. If only one comparable edition exists, the interface reports that the delta is unavailable rather than substituting zero. Parser revisions and ambiguous same-date versions are not silently treated as Prefecture updates.

Count units are **source observations / presences**, not distinct legal entities. A newly observed presence is not automatically a new administrative registration; a presence no longer observed is not automatically a cancellation. Status changes are a subset of modified common rows and must not be added to them.

## Available starting evidence

The seed ledger contains the frozen Cosenza editions of 28 June and 3 August 2026. It references the original capture manifests and parser-v2 aggregate comparison: 1,327 to 1,334 observations; 21 newly observed, 14 no longer observed, 1,313 common, 66 modified common mentions, including 55 status transitions. The interval between the dates is 36 days.

Other approved source editions are added by the ordinary public build. The existence of one edition does not imply a complete historical series: only actually acquired, extracted and approved editions enter the delta view.

## Data path and durability

`public_national_build` runs the ordinary approved registry build first. It then merges `data/history/public_history.json`, current approved edition aggregates and, when available, the previous public release from the project's own Pages site. The output is `public-site/data/history.json`, validated against the current registry by the public artifact gate.

After a successful **main** Public retro portal run, **Persist public edition history** downloads that run's reviewed artifact and merges only its aggregate history JSON back into the durable ledger. It checks out trusted current main, never executes artifact code, validates the closed data contract and uses normal fast-forward pushes with bounded reconciliation retries. Reruns are idempotent and a failed safe append fails visibly rather than force-pushing.

The ledger persists no company names, identifiers, per-company hashes or internal review annotations. Edition identity includes scope, raw reference date, original SHA-256 and parser signature. Counts and approved comparison evidence are immutable; parser revisions remain separate.

## Guardrails and known limits

Repeated successful checks of the same document do not create editions. Different bytes with unchanged extracted values are distinguishable from data changes, and parser revisions are not presented as Prefecture actions. Unknown dates remain unknown; conflicting same-date versions are not arbitrarily ordered.

Automatic granular comparisons require compatible consecutive approved row-level releases and sufficiently unambiguous identifiers. Missing or duplicate identifiers, changed overlapping identifier bundles and name conflicts remain unresolved. Where granular comparison evidence is unavailable, the public page shows only the defensible aggregate A/B balances.

Source absence is not administrative removal. Nominal expiry is not automatic loss of legal effect. Different registers and populations are never compared as if they were one source. Geography and private canonical tables are not involved.

## Verification

`tests/test_public_history.py` covers reconciliation, immutable merge, idempotence, parser revisions, uncertain identities, unknown dates, preservation of old scopes, optional-network failure and the publication contract. It also runs the Node invariants in `tests/public_history.test.cjs`.

`tests/test_public_history_browser.py` renders the simplified Prefecture-delta interface at desktop and mobile widths. It verifies the Prefecture selector, latest comparable A/B pair, observational delta table, absence of the discarded dashboard elements and root-level mobile overflow. The ordinary public acceptance test continues to cover the complete national registry, all visible portal sections and official-source links.
