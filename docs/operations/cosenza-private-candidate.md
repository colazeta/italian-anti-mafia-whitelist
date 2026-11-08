# Cosenza private source candidate

The deterministic planner is a review preparation step. It cannot execute semantic projection, canonicalisation, edition attribution or publication. Its private row payload contains personal/source values and must stay in the private dossier store. Only `safe_summary` may reach workflow logs.

Integration API:

```python
from white_list_archive.normalisation.cosenza_candidate import plan_records
result = plan_records(records, capture_id=capture_id, parse_run_id=rich_run_id,
    source_sha256=original_sha, snapshot_sha256=snapshot_sha,
    source_revision=original_parser_git_sha, planner_revision=dossier_git_sha)
```

The dossier caller first verifies the R2 original and full relational rich readback, then passes those exact snapshot records and pins. The pure planner revalidates record hashes/contract and snapshot SHA, requires exact parser/planner revisions, and returns `private_payload`, its deterministic `candidate_sha256`, and an aggregate `safe_summary`. The payload has no processing timestamp; repeating identical inputs/code produces identical bytes. `build_candidate(conn, ...)` provides a convenience wrapper for direct callers and starts with the existing read-only QA assessment; do not use that wrapper for a dossier already holding verified rows.

Every row retains capture/run/physical locator/record hash. Identifier candidates, ambiguous schemes and raw source fields remain intact. Application, observed listing and observed expiry dates become calendar-valid candidate values, or null while their raw value remains available. Invalid populated observed date counts stay visible; these calendar candidates are never legal effective dates. Requested activity mappings are proposed concepts for requested activities, never proof of represented relationship sectors. Source outcome text remains a source classification. Canonical entity, legal status and edition approval are always null. Expiry, cancellation text or disappearance never generates a canonical legal event.

## Remaining execution controls

The current projector `semantic.combined_whitelist_v1.project_series` requires exact rich parse/capture selection and a unique same-series edition/date. It also interprets relationship/procedure states. It does not authenticate a reviewer or materially enforce edition identity/attribution approval statuses. Consequently it cannot be called as a shortcut for safely typed source facts before attribution review. The current canonicaliser v2 additionally needs explicit selected projection IDs, reviewed identifier ambiguity/resolution and date/procedure rules. Planning performs neither operation.

Before any execution, independently authenticate edition identity/date basis and capture attribution, population/sector scope, parser/source exceptions and the versioned semantic/canonical rules. A JSON envelope or successful source readback does not authorise those decisions. Publication remains separate and requires the authorised publisher.

## Read-only privilege audit, 8 November 2026

`wl_ingest` already has every privilege needed by this source-only planner/QA. The following are missing for the *existing full semantic/canonical writers*, based on their concrete INSERT statements and independent Neon privilege queries. This is an audit, not a GRANT request or permission to run them:

- `USAGE` on schema `semantic`;
- `SELECT` and `INSERT` on `semantic.projection_run`, `entity_observation`, `identifier_observation`, `establishment_observation`, `projection_issue`, `relationship_observation`, `procedure_observation`, `procedure_sector_observation`, `canonicalisation_run`, `entity_projection_resolution`;
- `INSERT` on `source.procedure_mention` for projection;
- `INSERT` on `core.legal_entity`, `entity_name`, `entity_identifier`, `address`, `establishment`, `establishment_address`;
- `INSERT` on `whitelist.white_list_relationship`, `relationship_state_version`, `white_list_procedure`, `procedure_version`, `procedure_sector`;
- `INSERT` on `provenance.evidence_item`, `entity_resolution`, `procedure_resolution`, `entity_name_evidence`, `entity_identifier_evidence`, `establishment_evidence`, `address_evidence`, `relationship_state_evidence`, `procedure_version_evidence`.

`provenance.processing_activity` SELECT/INSERT already exist. Edition append would separately lack INSERT on `source.source_edition` and `source.capture_edition`; do not grant or invoke the legacy manifest path merely to bypass absent attribution. Any complete edition materialiser must receive its own reviewed contract/privilege audit. No UPDATE/DELETE privilege is proposed. No privilege change was executed by this work.

Tests verify deterministic hashes, immutable source ambiguity, impossible dates, revision/snapshot mismatch rejection, privacy of aggregate summaries and absence of inferred canonical states. PostgreSQL/source-store integration is exercised by the dossier caller using the same verified rich snapshot; this pure planner introduces no new SQL.
