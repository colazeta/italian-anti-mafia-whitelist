# Recovery decision provenance

The national recovery report distinguishes provider facts from operator decisions. Exact archive-first bytes and immutable capture/check provenance are verified against the governed private backend; claims about an external recovery package or a positively confirmed durable absence are different facts and require their own review trail.

For archive-first capture rows, `operator_evidence_refs` is therefore required whenever `recovery_paths` is non-empty or `durable_absence_confirmed` is true. The references remain private materialisation metadata and are copied into the corresponding private recovery-report item after provider verification. They are not source-edition metadata, do not alter capture identity and do not expose recovery-package paths publicly.

Compatibility is explicit: a schema-version-1 capture row that asserts neither a recovery package nor durable absence may omit `operator_evidence_refs`. Existing capture identities and lower-level archive-inventory input fields are unchanged. A previously prepared private plan that asserts either operational fact without evidence references must be amended before it can be materialised; the command now fails closed instead of accepting an unaudited recovery decision.

This rule mirrors the existing requirement for historical `known_version` overlays: operational recovery facts must be supported by operator evidence, while repository evidence remains authoritative for historical identity and the reviewed SourceSeries registry remains authoritative for archive-first authority ownership.
