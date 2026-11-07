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

Reviewed changes to this workflow or preflight module run a read-only acceptance
on main against the exact already committed June capture/snapshot pair. The run
UUID was independently read from production; it is not chosen by date, latest
revision or matching bytes at runtime. Explicit dispatch remains available for
other exact reviewed pairs. No source-edition attribution is created.

## Explicit capture-only source persistence

The workflow mode defaults to `preflight` for both manual dispatch and push
acceptance. `persist-source-only` is accepted only for an explicit
`workflow_dispatch` event; a push never writes source rows. The same exact reviewed
historical capture and existing aggregate snapshot UUIDs remain prerequisites.

This mode uses `persistence.capture_rich_cosenza`, not the legacy
`persist_records_v2`/`persist_manifest` path. It verifies original/catalogue bytes,
historical provenance and the prerequisite snapshot, runs the validated rich
parser, and appends a separate rich parse snapshot with exact parser version,
executing Git revision and configuration hash. It creates the immutable primary
`parse_run_input` and `capture_parse_run` links and materialises rich source records,
seven fields per row and one entity mention per row. It never creates or changes
captures, ContentObjects, source editions, edition links, semantic/canonical facts
or release approvals.

The schema fingerprint and physical field namespace come from the existing
validated parser-family registry. Existing matching database schema metadata are
reused without timestamp updates. When the schema must first be registered,
`first_observed_at` is the actual rich processing start, and `last_observed_at`
remains NULL. This is a schema registration observation; the independent historical
capture timestamp remains on the unchanged acquisition. The new path does not
backdate inferred schema observation or claim a latest observation range.

All writes occur in a caller-owned transaction after fixed privilege and record
contract checks. Complete readback compares the canonical snapshot hash and every
parsed locator/hash/raw block, schema fingerprint, field definition attribute,
raw/parsed field value and entity-mention cardinality. `ON CONFLICT` never clears a
mismatch. A new TLS connection then repeats full readback after commit. Exact
repeats reuse the interpretation and rows; another parser/code/configuration
revision creates another interpretation. Conflicting output for one identity
fails without overwriting it. Source QA, edition attribution and semantic approval
remain separate gates.

### Exact database permissions

Both modes require existing schema USAGE. The source-only implementation needs
SELECT on these fourteen tables:

- source.source_capture, source.content_object, source.source_series;
- source.source_schema, source.source_schema_version, source.source_field_definition;
- source.parse_run, source.parse_run_input, source.capture_parse_run, source.parse_snapshot;
- source.parsed_record, source.source_field_value, source.entity_mention;
- provenance.processing_activity.

INSERT is required on eleven of those tables: all except source.source_capture,
source.content_object and source.source_series. No UPDATE, DELETE, sequence,
edition, semantic, canonical, role-management or publication privilege is required.
The prerequisite read-only preflight also selects existing source.capture_edition
and source.source_edition links, without treating them as approval.

Read-only inspection of the existing `wl_ingest` role during preparation found
all required SELECT permissions and five existing INSERT permissions. The exact
missing privileges were:

| Table | Missing permission |
| --- | --- |
| source.source_schema | INSERT |
| source.source_schema_version | INSERT |
| source.source_field_definition | INSERT |
| source.parsed_record | INSERT |
| source.source_field_value | INSERT |
| source.entity_mention | INSERT |

`missing_privileges()` derives its fixed requirement set from this implementation.
Missing permissions stop the source-only path before its first INSERT and are
reported as table/privilege pairs without connection details. The workflow and
module execute no GRANT and cannot silently expand access. A separate owner
decision is required before changing the role's security-sensitive access.

The concrete proposal for that separate decision, to be executed only after
explicit approval, is limited to:

```sql
GRANT INSERT ON
    source.source_schema,
    source.source_schema_version,
    source.source_field_definition,
    source.parsed_record,
    source.source_field_value,
    source.entity_mention
TO wl_ingest;
```

This proposal grants no edition, semantic, canonical, UPDATE or DELETE access.
It has not been executed by preparing the implementation or documentation.
