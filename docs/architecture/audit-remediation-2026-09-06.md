# Audit remediation — 2026-09-06

This note records the database-hardening changes made after the independent review of the initial implementation baseline.

## Closed blockers

- Replaced explicit `timestamptz 'infinity'` range bounds with genuinely unbounded PostgreSQL ranges (`NULL` upper bound), so `upper_inf()` correctly identifies current system versions.
- Replaced current-only temporal checks with tri-temporal GiST exclusion constraints over effective, observation and system time. Unknown effective time is treated as a wildcard for integrity checking without changing its semantic value (`NULL`).
- Added `parse_run` versioning so the same immutable content can be re-parsed without overwriting previous interpretations.
- Added full system-time exclusion for accepted entity and procedure resolutions.

## Referential-integrity hardening

- A `source_field_value` must use a field definition from the same `source_schema_version` as its `parsed_record`.
- A relationship-sector state may only use a scheme membership for the same sector concept and the same White List regime as the relationship register.
- Sector-scheme versions for the same regime may not overlap.
- Sector memberships must be temporally contained within their scheme version.
- Edition sector scope cannot use a scheme membership from a regime different from the edition's linked register.
- A `procedure_mention` may only refer to an `entity_mention` extracted from the same parsed record.

## Provenance and immutability

- Canonical historical versions now retain the `processing_activity` that generated them.
- Derived events can retain explicit canonical state/version inputs.
- `source_field_value` is append-only. A corrected parse must be represented by a new parse run.
- The byte identity (`sha256`, size) of a `content_object` is immutable after creation.

## Source and publication model

- Source resources now support a generic canonical locator plus an optional web URL, so non-web archival/FOIA material is representable.
- Edition population and sector scope completeness are separate dimensions.
- Source-series type no longer conflates population and sector scope.
- Dissemination policy is profile-specific rather than globally attached to a field.

## Validation status

Static repository/design checks pass locally. The repository CI is configured to bootstrap PostgreSQL 18 and execute `db/tests/001_constraints.sql`. A live PostgreSQL 18 server is not available in the local execution runtime used for this remediation, so the DDL must still pass the configured integration job before the database schema is tagged `v0.1.0`.
