# National pipeline: operational states and remaining work

Checkpoint: 15 November 2026. Runtime evidence belongs in issue #225 and the
existing private operational reports. The table maps actual stored/runtime states;
it does not introduce a second scheduler or a fictitious global status column.

| Boundary | Current evidence/state | Prerequisite for progression | Retry/recovery |
|---|---|---|---|
| discovery → acquisition | Existing `Prefecture robots`, trusted `robot-state` index; roles `source`/`candidate` and reviewed population mapping | Official locator, qualified SourceSeries/population or explicit unbound candidate | Existing per-authority request/time bounds and persisted pending queue; unrelated authorities continue |
| acquisition → durable original | SHA-256 ContentObject, immutable CaptureCatalogue manifest/receipt, full size/hash readback | Exact original and authentic provenance; object storage success is distinct from PostgreSQL materialisation | Conditional writes and exact readback; unchanged bytes reuse object while retaining separate capture checks |
| durable original → relational capture | `source.source_capture`/ContentObject linkage; independent committed readback | Genuine series/resource/origin/type metadata and existing registered scope | Idempotent existing writer; metadata/locator conflicts quarantine rather than relabel historical checks |
| capture → private interpretation | `parsed_private_review_required` / `reused_private_interpretation`, complete labelled ParseRun inputs and ParseSnapshot | Parser/configuration/code lineage and complete input set; TLS and full snapshot rehash | Bounded typed transient-I/O retries; equivalent interpretation-code objects permit reuse without changing original revision |
| source exception | Per-source `quarantined`, stage, error class and private first-observed receipt; `blocked` for unavailable global prerequisites | Changed relevant parser, binding, configuration or source evidence; an exception is not approval | Other sources continue. Terminal-quarantine attempt suppression remains unfinished; first-observation ageing alone does not suppress identical work |
| missing-history/backfill | Existing bounded worker: `existing_verified`, `materialised`, `deferred`, `quarantined`, missing capture bindings | Exact reviewed original/configuration, registered series and complete private readback | Existing shard/batch bounds; cursor/checkpoint history remains separate from latest-source processing |
| interpretation → source review | `archived-release-readiness`: independent authority/population outcomes, `review_metadata_ready` or explicit exception | Both populations, authentic original/provenance, explicit date, family/contract checks; exhaustive physical census still required | Existing protected worker prepares bounded cohort; no automatic approval or public row artifacts |
| source review → immutable public candidate | Reviewed source/profile PR + `Public registry candidate` build and preserved five-file release | Required CI, exact raw/semantic approval, privacy contract, incremental row/report audit, browser and link checks | Reuse individually approved unrelated public derivatives; missing/corrupt selected evidence fails the candidate. Previous live selection survives |
| candidate → selected release | Separate reviewed `public_snapshot.json` + monitoring synchronised from the actual SHA-verified registry | All five immutable asset hashes/sizes; exact candidate acceptance | Expected-head serial merge; no overwritten release or mutable latest fallback |
| selection → live verified publication | Sole `Public retro portal`; five-file live SHA/size readback | Successful build/deployment and actual origin bytes equal selected manifest | Existing bounded CDN retries; prior immutable selector remains rollback. A candidate tag or successful deploy start is not completion |

The current incremental composition reuses **public derivatives**, not original
national-source replay. It preserves old rows, parser versions, source/check dates
and reports exactly. The new source must independently verify its original. Full
national original-byte replay and genuinely independent original recovery remain
separate acceptance criteria. Issue #16's closed label is not evidence of the
independent-provider control: its latest substantive comments retain that limit.

## Persistent observation and metric definitions

- `production_checkpoint` retains transaction-consistent private PostgreSQL
  counts with source tables, timestamps and explicit structural/integrity limits.
- Transformer reports distinguish newly persisted interpretations, verified
  reuse, QA flags, quarantines, blocked/deferred work, TLS and committed readback.
- Readiness reports retain source-specific explicit dates, original identities,
  population denominators and source-review outcomes without public source rows.
- The selected-publication ledger is regenerated only from actual verified public
  registry bytes; prospective configuration never defines live freshness.
- The portal's documentary backlog is computed by `robotPublicationGap`. It counts
  acquired candidate documents with interpretable **filename dates** after their
  corresponding published scope; it excludes already selected hashes and keeps
  unknown/same-date/unbound cases separate. HTML page updates require the separate
  original-body date review. This counter is not an approved-edition count.
- Capture checks, distinct originals, records across parse revisions, public
  documentary presences, canonical businesses and administrative SourceEdition
  attributions are different denominators. Never add or substitute them.

Reconciliation on frozen `robot-state@5ae0fdc86988131c1dac59bceb0e3e252fa03299`
against selected `public-data-43524455108-1` gives **280** dated candidate documents
in **30/74** comparable published authorities, with **32** authorities lacking a
release baseline and **790** unclassified document candidates. The historical
278/30 checkpoint has therefore advanced by two documentary candidates under the
same portal algorithm. These are discovery-index results, not 280 independently
validated editions or a complete inventory of every historical ContentObject.

Direct Neon readback at **14:40:05 UTC** found **392/417** registered content objects
with interpretation inputs and **518/621** capture checks linked to an
interpretation. This covers registered source-layer inputs including discovery
material; it is not a publication-eligibility rate. At 14:32:35 UTC there were
745 snapshots / 233,123 record occurrences and zero administrative editions. The
Biella original's earliest authentic exact capture is **12:00:37.675 UTC**; elapsed
time to a verified live release must use the eventual actual verification time,
not infer an availability timestamp from the page's date alone.

The approved Biella source-config transition then materialised **two** exact
private snapshots (132 + 111 = **243** observations) with reviewed reference date
12 November. Independent SQL at 14:49:10 UTC found exactly one such snapshot per
physical parser for that original/configuration. Historical undated snapshots and
original capture dates were retained; this is not an administrative-edition or
canonical-entity attribution. Worker #43725882675, shard 2, separately verified
the two committed backfills. The full approved backfill becomes **124/142**
verified scopes: 122 reused + 2 new, 3 deferred, 8 quarantines, 7 missing index
bindings; those outcome counts reconcile to 142.

## Priority order after the Biella release

1. **Como 10 November, then Taranto 6 November:** original/provenance/date/parser
   metadata already verified by the bounded cohort. Add exhaustive physical-row
   census and finite full-source review, then follow the same two-population
   incremental candidate/selector/live checks. Their HTML dates do not reduce the
   filename-based backlog counter automatically.
2. **Expected terminal quarantines:** introduce attempt identity/checkpoint reuse
   tied to relevant parser/configuration/input evidence, retaining first-observed
   ageing and explicit exceptions. Do not treat the entire deployed commit as a
   reason to repeat physical extraction or re-review unchanged evidence.
3. **Approved backfill and bindings:** resolve the eight source-specific QA
   exceptions and nine missing index bindings recorded before the Biella update;
   read fresh denominators after new config processing. The exact Ascoli adapter
   is already materialised; do not repeat that old task or relabel its capture.
   Source resource-type conflicts are software/metadata compatibility defects,
   distinct from unknown official editions requiring source review.
4. **Catania / Lodi / Milano:** classify actual source rows/layout/status evidence.
   Catania's ten trailing rows and missing exact catalogue provenance remain real
   gates; no name-only deduplication or inferred status/date repairs. Retain the
   existing approved derivatives meanwhile.
5. **National history and recovery:** continue the existing bounded historical
   campaign from verified checkpoints, qualify the remaining 32 authorities and
   complete semantic/canonical attribution separately. Original-byte recovery to
   an independent target needs a genuinely authorised transfer/target; do not retry
   previously declined authentication or introduce paid infrastructure.

Further engineering: narrow the conservative interpretation-code footprint to
validated family dependencies; avoid a full robot sweep when only one reviewed
catalogue scope changes; replace opaque backfill error classes with closed
stage/reason codes; consolidate review metadata into an indexed private operational
view. None is permission to weaken source, privacy or publication gates.
