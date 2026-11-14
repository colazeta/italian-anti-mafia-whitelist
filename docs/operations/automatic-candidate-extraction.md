# Automatic private extraction of newly discovered White List documents

## Scope

The Prefecture robots already monitor the 106 territorial authorities and archive
verified source bytes in the protected evidence store. The existing
`auto_transform` pipeline parses changed **previously associated resource URLs**
into the private PostgreSQL `source.parse_snapshot` table, preserving the
source data, provenance and independent database readback.

For Catania XLSX, the provisional workflow uses the separate
`catania_candidate` family: it requires the expected column headers but
accepts a changing number of data rows, preserves raw malformed sector/date
cells and flags formula, identifier and outcome anomalies. It **does not**
relax or modify the exact-SHA official November 6 release parser. Newer
Perugia PDFs and several other prefectural formats still need additional
schema-family adapters: a parser that is intrinsically pinned to one edition
cannot be safely repurposed by replacing its input hash.

A newly discovered PDF/XLSX/DOC/CSV at **another URL** has previously remained
an unbound `<authority>-robot-discovery` capture. It must **not** be relabelled
as a confirmed listed/applicant SourceSeries merely because its filename
looks promising.

## Additional automatic stage

The existing `transform-reviewed-captures.yml` workflow now also invokes
`white_list_archive.acquisition.candidate_extract` against the same frozen
trusted main revision and frozen robot-state revision. This is done after the
reviewed-source processing step, even when a different approved source fails
or requires quarantine.

The candidate extractor:

1. Inspects source-check metadata for resources with the explicit
   `candidate` role, excluding already associated URLs and landing pages.
2. Restricts candidates to the Prefecture's configured HTTPS host(s),
   relevant document filenames and supported input extensions.
3. Selects a **single parser hypothesis** from the same reviewed Prefecture
   using compatible format and, where the filename has an unambiguous signal,
   listed versus applicant population. Unclear or multiple matches are
   deferred; these heuristics never assign an official source series.
4. Requires a real immutable `<authority>-robot-discovery` capture with a
   valid digest, positive size and timezone-aware capture timestamp.
5. Reads the original source bytes from the protected archive and verifies
   the complete private capture catalogue/manifest, size and SHA-256.
   **No public or live download occurs in the extraction worker.**
6. Runs a compatible parser or, for Catania XLSX, a separate unpinned candidate parser with
   `reference_date=""`. Rejects empty outputs or parser lineage failure.
   Flags source row count, sector count, date and status drift.
7. Re-keys extracted provisional rows to the verified
   `<authority>-robot-discovery` capture, including the **new document URL**,
   true document SHA-256 and source row ordinal. The older approved URL and
   registered series key are retained only as parser-selection hypotheses,
   never as evidential attribution for the new document.
8. Writes the **complete parser output and diagnostics** to an immutable,
   content-addressed private `operations/v1/candidate-extract/` receipt,
   then independently reads back the exact result. A repeat input/parser/code
   identity reuses the stored extraction instead of rerunning the parser.

A parser mismatch after verified archive readback is stored instead as a
`quarantined_candidate_extraction` receipt containing **only the error class**,
the unbound source identity and zero rows. Subsequent runs reuse this immutable
quarantine until the source/parser/code identity changes; failures cannot
indefinitely consume the six-new-attempts-per-shard budget. Provider/archive
readback failures are not cached as parser mismatches.

Each successful extraction carries `review_status=unapproved_candidate_extraction`,
`publication_approved=false` and a **null** source reference date.
The original unbound discovery capture remains unbound. No source
administrative date, canonical entity decision or publication event is inferred.

One shard attempts no more than six *new* candidate parser runs per execution.
Existing privately staged results can be reused without consuming that limit.
Backlog, ambiguous candidates, parser failures and access problems remain
visible as aggregate counts for later evaluation.

## Where outputs go

| Output | Destination | Contents |
| --- | --- | --- |
| Unmodified source evidence | Protected private archive | Original bytes and immutable capture catalogue |
| Successful candidate extraction | Protected private archive `operations/v1/candidate-extract/` | Full unapproved extracted source rows, parser diagnostics and SHA provenance |
| Detailed operating report | Protected private archive `operations/v1/transform/` | Source-level status, QA flags and error classes; no exception text |
| Public Actions report | GitHub Actions artifact, 14-day retention | Aggregate counts only; no names, tax identifiers, source URLs or storage keys |
| Previously reviewed source snapshot | Protected PostgreSQL via `auto_transform` | Independently read-back parse snapshot, still unapproved for public release |

This separate candidate store is deliberately **not** a new `source.parse_snapshot`
table, since the identity of an unbound source is not yet a reviewed source series.
Promoting a candidate to a registered series and later to the public release
still requires source-context/edition review, stricter schema-specific QA and
an explicitly selected versioned publication manifest.

## Current limitations

- Candidate parser selection is deliberately conservative and only works
  where exactly one plausible reviewed *scalar* parser matches the file
  extension and population hint. Bundles, unfamiliar layouts, ambiguous
  candidates and unreviewed authorities remain unresolved.
- Exact extraction of newer content is not evidence that a previous parser
  is semantically compatible. QA flags and any parser outputs must be
  reviewed before promotion.
- Scanned PDFs cannot be reliably extracted by the existing text parsers.
- The protected private archive is mandatory; the workflow does not
  silently produce a public-only substitute when it is unavailable.
- Candidate parsing is bounded per shard. A backlog is explicit, rather
  than silently counted as completed.
- The public UI is not a source of truth for private candidate staging.

## Operational check

Inspect the `Transform reviewed captures into private observations`
GitHub Actions run and the four `white-list-candidate-extract-status-*`
artifacts. Confirm separately how many inputs were examined, extracted,
reused, quarantined, blocked and deferred. Check the protected review
receipts before approving a new source series or public edition.

The transform never deploys Pages or modifies
`data/publication/public_snapshot.json`.

## Catania 13 November candidate-source QA

An additional **read-only step in the existing protected transform workflow** (shard 0
only) checks the two original 13 November Catania XLSX SHA-256 pins already
documented in issue #267, using the primary content-addressed archive. It
does not fetch a live URL, change the source registry, issue a new capture,
dispatch another workflow or write to PostgreSQL.

For each original, the step verifies the complete bytes against the frozen
digest and runs the separate provisional Catania candidate parser *without*
an administrative reference date. It emits aggregate source-observation and
status counts and a closed set of quality counters only. The extracted rows
remain ephemeral, and exception messages, raw names, identifiers, private
storage keys and original URLs are never logged.

The reported states are distinct:

- `unknown`: the exact original could not be positively read back; this
  **does not** establish loss or absence;
- `layout_or_parser_review_required`: the original bytes were positively
  verified, but its unapproved sheet/row contract failed;
- `provisional_extraction_for_review`: the exact bytes passed the provisional
  parser, yielding only *candidate* source-row statistics.

Positive primary-byte verification **does not** verify immutable capture
catalogue provenance, associate a robot-discovery capture with a reviewed
SourceSeries, establish the official 13 November edition date, approve the
physical parser, create a `SourceEdition`, create a semantic/canonical
observation or authorise new public records. The independent capture/catalogue
receipt, full layout/row/date/sector/status review and a separately versioned,
fail-closed production parser are still required before an incremental public
candidate and selector change.

The listed parser separately counts expiry cells containing Excel formulas as
`source_expiry_formulas`. This is an informational source-layout count, **not**
itself an error or a date inferred from a formula. `formula_without_cached_date`
is a distinct quality flag that must be retained. The private QA aggregate keeps
both counters distinct, accepts only its documented closed diagnostic keys, and
quarantines unknown counters or parser mismatches. No value, formula or person-
level row is published by this read-only check.

For a verified original that fails the provisional parser, the report now
records only a **closed diagnostic category** (for example, header identity,
worksheet bounds, incomplete data-like row or unclassified source row).
Unknown errors are assigned `other_review_required`. Neither workbook values
nor exception messages enter the public report. This classification is for
triage, not a new parser approval or a reason to drop source rows.

A failure of this read-only diagnostic is isolated from the other transform,
backfill and quarantine lanes. The existing private source reports remain the
authoritative location for detailed review. The latest selected public release
must be preserved until the newer inputs pass their own complete controls.

### Catania 13 November — aggregate-only ambiguous-row triage

When the exact verified listed workbook produces the known
`unclassified_data_like_row` rejection, the protected read-only probe also
counts source-row **shapes** over that same workbook and validated header.
The separate summary distinguishes full anchor rows, incomplete anchors,
ambiguous rows before/between/after anchored rows and two non-exclusive
categories of populated cells (name with office; other non-anchor cells).
It never emits a cell value, source row number, identifier, address, hash of
a row, original URL or private object coordinate. The triage is `null`
when its independent workbook inspection fails or when another parser error
occurs; unknown remains unknown. Its counts are not records accepted by a
production parser and cannot be added to publication totals.

This helps determine privately whether the new XLSX layout contains an
interleaved continuation, extra administrative annotation or another
source-specific structure requiring review. **No ambiguous row is skipped,
reinterpreted or published.** The same exact source hash, Catania-specific
parser approval, capture/catalogue binding, documented edition date,
listed/applicant QA and unchanged non-Catania release comparison remain
mandatory. Synthetic XLSX regressions verify aggregate counts and redaction.
