# Historical capture/check writer-provenance preflight

The existing protected transformation workflow checks four previously reviewed September Lodi and Milano byte identities from the primary, immutable R2 archive. The bounded read-only probe now also distinguishes a complete verified capture/check from one whose original immutable manifest contains all three explicit metadata fields required by the existing append-only relational writer: origin_type, authority_rank_code and resource_type_code.

This gate never repairs or invents missing metadata. It cannot use a capture timestamp, hash, file label or mutable resource URL as administrative edition identity, source date or evidence of an approved legal status. At most 64 catalogue objects per one of the three existing SourceSeries prefixes are inspected. Truncated/provider-failed listings never establish absence.

The additional fixed-schema counters report the numbers of verified capture checks with complete writer metadata and checks whose metadata is missing, both by existing reviewed scope and overall. They contain no capture UUIDs, private locations, source values or object hashes. Synthetic regression tests cover both the negative and explicitly populated metadata cases. The probe performs no relational INSERT and does not establish SQL privileges, committed rows, independent PostgreSQL readback, parser compatibility, administrative edition approval, semantic/canonical facts, independent recovery or public publication.

A subsequent source-only backfill may use only the existing transactionally idempotent capture writer, but must separately verify each exact capture and its independent post-commit readback. No new grant, credential, service, schedule or publication right is created by this preflight.
