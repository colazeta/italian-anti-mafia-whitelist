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

## Multiple application dates: mandatory review signal

Production aggregate QA counts `multiple_distinct_application_date_rows` and
`max_distinct_application_dates_per_row` from the *source-cell* candidate list.
Rows with two or more distinct application date candidates force the source-fact
review gate to `unknown`; the dates remain separate in the private candidate.
This is **not** evidence of multiple procedures, an edition date, an approval or
a legal event. A reviewer must inspect the exact original and establish any
procedure linkage explicitly before a separately authenticated semantic gate.
The diagnostic is per parse run; repeated runs and editions must not be summed
as distinct entities. The frozen historical code/campaign are not modified.

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

## Physical row position is not longitudinal identity (QA, 12 November 2026)

Independent aggregate SQL over the two persisted, immutable Cosenza originals
selected one verified rich parse run per original (1,327 and 1,334 document
occurrences). Their raw-block record hashes overlap for **1,247** occurrences.
Of those identical content blocks, only **62** retain the same physical
`row:NNNNNN` locator, while **1,185** occur at different row positions. There
are **80** content blocks in the 1,327-row input with no exact hash match in
the 1,334-row input and **87** in the reverse direction. Within each selected
source input, no record hash is repeated. A same-position comparison would
incorrectly suggest **1,265** changed blocks because physical row order is not
stable between files.

These are comparisons of **source document occurrences**, not identified
companies, administrative entries, legal events or approved editions. Even
identical source blocks do not themselves authorise canonical identity
resolution. The comparison order is explicitly selected input order; it is
not proof of chronology or of administrative reference dates. Unmatched text
cannot be labelled removal, entry, revocation, rejection or interdiction.
A synthetic regression test protects content-based comparison against row
reordering; reviewer attribution and semantic/canonical execution remain
separately blocked by the existing gates.
