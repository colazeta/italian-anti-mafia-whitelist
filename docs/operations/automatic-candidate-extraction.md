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
