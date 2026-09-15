# Prefecture history and document updates

The existing public portal's **Storico** and **Aggiornamenti** tabs share Prefecture,
register, source series, source-date interval and status filters. The registry and
existing statistics retain their original behaviour. This is an observational
read model, not a reconstruction of administrative decisions or a ranking of
Prefectures.

## What the interface exposes

- A source-date timeline, one row per source series and one point per available
  edition. Selecting a point opens its edition comparison.
- Status distributions and counts by edition, in absolute or percentage scale.
  A status percentage always uses the full edition as its denominator.
- A/B comparison within the same Prefecture, register, population and source
  series: net change, new and no-longer-observed presences, modified common rows,
  status transitions, document links and the available public rows for edition B.
- An as-of-source-date view: the last usable edition of each selected series not
  later than the requested date. Missing bases and ambiguous same-date versions
  are excluded and counted explicitly. This does not reconstruct what the project
  knew at the time or certify an entity's legal position on that day.
- Update intervals, a type-of-change filter, minimum absolute net change and
  minimum interval. One edition yields no frequency; two give only one interval.
  The median is exposed only from two observed intervals, with its denominator.
- CSV/JSON exports of the selected history or event rows. JSON also retains the
  source-edition evidence and missing/ambiguous snapshot scopes.

Count units are **source observations / presences**, not distinct legal entities.
The entry/absence and modified-row cards cover the whole compared source, even
when a status filter selects only the net balance; the labels state this scope.
Status changes are a subset of modified common rows, not an additional category
to sum. A row table for edition B is not mislabelled as a list of changed rows.
No historical company names are manufactured from aggregate counts.

## Available starting evidence

The seed ledger contains the frozen Cosenza editions of 28 June and 3 August 2026.
It references the original capture manifests and parser-v2 aggregate comparison:
1,327 to 1,334 observations; 21 newly observed, 14 no longer observed, 1,313 common,
66 modified common mentions, including 55 status transitions. The interval between
the dates is 36 days. These are observational mention matches, not canonical
entity resolutions. The historical aggregate does not report a resolved-identity
quality measure, so its unresolved-identity fields remain null.

Other current approved source editions are added by the ordinary public build.
The existence of one edition does not imply a complete historical series. The
older Cosenza discovery links remain accessible but do not enter counts or cadence
until an edition has actually been acquired, extracted and approved.

## Data path and durability

`public_national_build` runs the ordinary approved registry build first. It then
merges `data/history/public_history.json`, the current approved edition aggregates,
and optionally the previous public release from the project's own Pages site.
The output is `public-site/data/history.json`, validated against the current
registry by the public artifact gate. The public allow-list includes only the new
history JSON and its JavaScript module; the row-level publication contract is not
widened.

After a successful **main** Public retro portal run, **Persist public edition
history** downloads that run's reviewed artifact and merges only its aggregate
history JSON back into the durable ledger. It checks out trusted current main,
never executes artifact code, validates the closed data contract and uses normal
fast-forward pushes with bounded reconciliation retries. Reruns are idempotent.
The collector does not change the publication dataset or create an extra source
polling schedule. A failed safe append fails visibly rather than force-pushing.
The already-published history is also read on the next build as a recovery layer.

The ledger persists no company names, identifiers, per-company hashes or internal
review annotations. Edition identity includes scope, raw reference date, original
SHA-256 and parser signature. Counts and comparison evidence are immutable; parser
revisions remain separate. Only a whole-edition data fingerprint is stored, after
whitespace/list-order normalisation and exclusion of physical row positions.
Changing this fingerprint algorithm requires an explicit history migration.

## Guardrails and known limits

Repeated successful checks of the same document do not create editions or inflate
update counts. Different bytes with unchanged extracted values are distinguished
from data changes, and parser revisions are not presented as Prefecture actions.
Unknown dates remain unknown; conflicting same-date versions are never selected
by arbitrary hash order for a historical snapshot.

Checks currently concern **approved, pinned resource URLs**, not an exhaustive
watcher of the newest publications on each institutional site. The retained
success-only check ledger does not contain every failed attempt. Consequently it
cannot measure website uptime, monitoring completeness, or prove there were no
updates during unobserved periods. UI labels and exports do not claim otherwise.

Automatic granular comparisons require both consecutive approved row-level
releases, compatible parsers and unambiguous exact identifier observations.
Missing/duplicate identifiers, changed overlapping identifier bundles and name
conflicts remain unresolved. Incomplete identity coverage suppresses complete
entry/absence counts rather than turning uncertain matches into flows. Without
previous rows, counts and status balances remain available but granular deltas
stay null. No fuzzy name matching or administrative interpretation is applied.

Source absence is not administrative removal. Nominal expiry is not automatic
loss of legal effect. Different registers and populations are never compared as
if they were one source. Requested sectors are not converted into authorised
relationship sectors. Geography and private canonical tables are not involved.

## Verification

`tests/test_public_history.py` checks reconciliation, immutable merge, idempotence,
parser revisions, uncertain identities, unknown dates, preservation of old scopes,
optional-network failure and the recursive publication contract. It also runs the
Node invariants in `tests/public_history.test.cjs`.

`tests/test_public_history_browser.py` renders the existing portal with consistent
synthetic fixtures at desktop/mobile widths and exercises shared filters, A/B
metrics, as-of selection, exports, drill-down navigation and missing-history
fallback. It is run by **Prefecture history checks** with the same Playwright
version as the existing public acceptance workflow. The ordinary public workflow
continues to run its full national registry and rendered acceptance gates.
