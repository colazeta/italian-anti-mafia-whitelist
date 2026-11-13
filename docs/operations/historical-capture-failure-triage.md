# Closed diagnostics for failed historical capture reconciliation

The first protected run after source-only backfill PR #256 verified four of six eligible immutable historical capture checks in PostgreSQL; two attempts failed closed. The existence of original bytes and a verified capture manifest does not establish that every relational metadata constraint can be satisfied.

The existing protected transformer now performs a read-only, exact-identity SQL diagnostic for failures and prints fixed aggregate category counts only. Possible causes include conflicting immutable capture UUID/original, capture metadata, existing resource-locator classification, registered original metadata, missing reviewed SourceSeries, SQL integrity/permissions or a remaining writer/readback failure. A failed diagnostic is explicitly classified as unavailable. No raw exception, private URL, original, identifier, storage key or individual record is logged.

This change does not retry with inferred metadata, overwrite conflicts, modify quarantine conditions, add database privileges or mark any original as an approved edition. Previously committed source-only checks remain intact. A new run is required to verify the aggregate diagnostic and independent PostgreSQL state; success of CI alone does not establish recovery.
## Resource-locator mismatch triage (safe aggregate only)

A `resource_locator_type_conflict` previously combined two different
comparisons. The protected writer still requires exact equality of the archived
manifest's resource type and URL with the already registered SourceResource.
The read-only diagnostic now distinguishes **resource type only**, **web URL
only**, and **both**. These are distinct *metadata contradictions*, not proof
that either classification is wrong or permission to reclassify it.

A second closed counter, `resource_metadata_conflicts_by_series`, reports
only aggregate conflicts among the already reviewed series: `lodi-listed`,
`lodi-applicants`, `milano-combined`. It does not include locators,
per-capture identifiers, original hashes, rows, private storage keys or
exceptions. A failed metadata diagnostic remains `diagnostic_unavailable`.

No writer rule, immutable provenance, catalogue identity, database schema,
acquisition, permission or publication boundary changes. Any correction needs
explicit documentary comparison of the frozen capture manifest and registered
resource metadata in the protected environment, followed by a separate
reviewed, append-only resolution contract; do not overwrite either source.
