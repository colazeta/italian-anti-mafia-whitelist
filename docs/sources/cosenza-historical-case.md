# Cosenza historical ingestion pilot

Cosenza is the first end-to-end historical ingestion pilot because the official Prefettura publication model exposes explicit dated White List editions and, for recent editions, a recurring bundle of one combined list plus section-specific files.

## Verified edition baseline

`data/source_registry/cosenza_historical_editions.csv` contains the first 11 independently verified reference dates spanning 2024–2026. The dates are source-reference dates explicitly stated by the official publication; they are not crawler timestamps.

The baseline includes:

- 24 June 2024;
- 9 September 2024 (official historical portal);
- 1 July 2025;
- 1 September 2025;
- 19 January 2026;
- 16 February 2026;
- 16 March 2026;
- 20 April 2026;
- 25 May 2026;
- 28 June 2026;
- 3 August 2026.

This is a lower bound, not a claim that these are all editions ever published.

## Resource model

For a modern dated edition page the acquisition pipeline treats the page itself as the logical edition locator and discovers its linked resources. The parser currently distinguishes:

- `combined_list`: the file covering listed companies and applicants;
- `sector_list`: a section-specific file with notation I–X.

The page reference date becomes `SourceEdition.reference_date`. Each linked file becomes a `SourceResource`; every retrieval becomes a `SourceCapture`; byte-identical resources converge on one immutable `ContentObject` via SHA-256. Parsing then occurs in a versioned `ParseRun`.

## Historical-origin distinction

The 9 September 2024 observation is retained from the Ministry's historical Prefetture portal and is marked `official_historical`. Current-site dated pages are marked `official_current`. This distinction belongs to source provenance and must not alter the substantive White List meaning of the edition.

## Automation

The CLI:

```bash
white-list-cosenza-snapshot <official-page-url>
```

extracts the explicit reference date and recognised edition resources. The manual GitHub Actions workflow `Cosenza snapshot discovery` runs the same parser and uploads a CSV discovery artifact.

## Next ingestion step

The next implementation increment should retrieve the verified resource URLs, persist content hashes and capture metadata, fingerprint the combined-list schema, and parse at least two successive editions. That will allow the first observed `FIRST_OBSERVED`, `DISAPPEARED_FROM_SOURCE` and sector-change candidates to be generated without conflating observational changes with administrative removals.
