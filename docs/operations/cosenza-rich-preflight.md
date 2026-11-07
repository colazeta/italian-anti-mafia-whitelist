# Private Cosenza rich preflight

The manually dispatched workflow requires exact historical capture and committed
snapshot parse-run UUIDs. It reads immutable R2 originals, checks reviewed
historical provenance, relational capture/input identity and snapshot rehash,
and requires rich v2 row denominators of 1,327 (28 June) or 1,334 (3 August).
A succeeded scalar parse run is required. Count agreement and ordinal uniqueness
are limited structural checks; full rich-record quality approval remains open.
No source rows or original bytes are uploaded as artifacts. SQL is read-only.

This is readiness evidence, not production normalisation. It never calls
persist_records_v2: that legacy entrypoint calls persist_manifest and can create
date-derived editions. Existing edition links are reported separately; explicit
identity/attribution is not publication approval. The historical manifests prove
exact bytes, capture time and stated reference date; administrative edition
identity and approval require independent review. No edition, grant, semantic
selection or publication is created by this workflow.

The minimal database privileges are schema USAGE and SELECT on
source.capture_parse_run, source.source_capture, source.content_object,
source.parse_run, source.parse_run_input, source.capture_edition, source.source_edition and
source.parse_snapshot. R2 needs read access to the original and catalogue.
No INSERT, UPDATE, DELETE, sequence or approval privilege is needed. Permission
failure blocks the preflight; it never broadens grants.

Subsequent rich persistence must reuse verified capture/ContentObject identities
and create versioned source parsing lineage. Append privileges must be enumerated
from its implementation separately from edition creation and attribution. The
semantic owner selects exact capture/run pairs. A passing preflight does not
certify canonical completeness, national coverage or eligibility for publication.
