# Archived input readiness for incremental publication

The existing protected transformer prepares a bounded first cohort of release
review metadata for Biella, Como and Taranto. These use existing HTML families
with already registered population scopes. It performs no live requests, database
writes, edition attribution, selection or public release.

The cohort requires a complete latest reviewed `listed` and `applicant` capture
pair, genuine immutable CaptureCatalogue manifests and full original SHA/size
readback. Both latest population inputs are selected even when one or both match
the approved bytes: byte change is not a completeness prerequisite. This opt-in
selection leaves the ordinary changed-source worker and approved-only backfill
unchanged; source/provenance checks still run on each selected input.

Source dates must be explicitly labelled `Ultimo aggiornamento` in the
original HTML, using the reviewed Italian day/month-name/four-digit-year format.
Every visible declaration must be interpretable and agree, including repetitions;
an unsupported second declaration cannot disappear from the date census. Partial
year tokens, ambiguous, absent, invalid and future dates fail closed. The
date is an official **page update**, not an administrative event, capture date or
assertion that every company entry was decided that day.

Parsing reuses the existing versioned family and public-contract validator. For
Biella an independent exhaustive census additionally classifies every nonempty
physical table row; widths silently skipped by the legacy parser are quarantined.
Grouped sector repetitions and applicant observations remain different units.
Old-edition count drift is recorded for review, never automatically approved.

Como has its own independent census using the existing v2 family's exact table,
title/header and source-counter structures. It classifies every nonempty row,
rejects unknown widths or unnamed nonempty rows, and reconciles physical rows
with both parser source_rows and complete observations. The page's source counter
may disagree with physical rows: retain both values and their discrepancy for
finite review instead of silently changing either. Blank source identifiers and
malformed source dates are counted and preserved, not invented or discarded.

Each authority and each population has its own result. One failure cannot prevent
the next cohort authority from reaching review. `review_metadata_ready` means
metadata for a human/agent source review exists; it is not release eligibility or
approval. Taranto still needs a separate exhaustive physical census. Como's
source-specific finite profile and publication intent still require review. The
private report is persisted/read back in the existing operations namespace. Console
output is a closed set of counts, dates and content identities; raw rows, names,
locators, exception messages and provider coordinates cannot expand its surface.

After source review the existing sequence remains: reviewed source config PR,
CI/source/contract/incremental/browser/link gates, immutable candidate release,
separate selector PR with regenerated monitoring, the sole **Public retro portal**
publisher, then all five live SHA/size checks. Previous selected public derivatives
are preserved for unrelated scopes and rollback. Candidate triage does not
replace any of these gates or imply completion of the canonical database.
