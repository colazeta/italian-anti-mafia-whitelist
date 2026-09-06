from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

OBJECTS = [
    ("authority", "Autorità territoriali", "core.public_authority", "reference", "Authorities maintaining White List registers."),
    ("regime", "Regimi White List", "whitelist.white_list_regime", "reference", "Versioned legal/administrative White List regimes."),
    ("register", "Registri White List", "whitelist.white_list_register", "reference", "Concrete registers maintained by authorities."),
    ("sector_concept", "Tassonomia settori", "whitelist.sector_concept", "reference", "Stable canonical White List sector concepts."),
    ("source_series", "Source series", "source.source_series", "source", "Recurring logical publications."),
    ("source_edition", "Edizioni fonte", "source.source_edition", "source", "Logical dated/periodic editions."),
    ("source_capture", "Capture", "source.source_capture", "source", "Timestamped acquisitions of source resources."),
    ("content_object", "Content object", "source.content_object", "source", "Immutable byte identities."),
    ("parse_run", "Parse run", "source.parse_run", "source", "Versioned parser executions."),
    ("parsed_record", "Parsed record", "source.parsed_record", "source", "Immutable source rows emitted by parsers."),
    ("source_field_value", "Valori sorgente", "source.source_field_value", "source", "Raw and parsed source-field values."),
    ("entity_mention", "Entity mention", "source.entity_mention", "source", "Source-level mentions before identity resolution."),
    ("procedure_mention", "Procedure mention", "source.procedure_mention", "source", "Source-level administrative-procedure mentions."),
    ("projection_run", "Semantic projection run", "semantic.projection_run", "semantic", "Record-contract to ontology projection executions."),
    ("entity_observation", "Osservazioni entità", "semantic.entity_observation", "semantic", "Typed source-supported entity observations."),
    ("identifier_observation", "Osservazioni identificativi", "semantic.identifier_observation", "semantic", "Typed identifier observations including ambiguous/malformed values."),
    ("establishment_observation", "Osservazioni sedi", "semantic.establishment_observation", "semantic", "Typed registered/secondary-office observations."),
    ("relationship_observation", "Osservazioni relazione White List", "semantic.relationship_observation", "semantic", "Source-supported relationship/status observations."),
    ("procedure_observation", "Osservazioni procedure", "semantic.procedure_observation", "semantic", "Typed application/procedure observations."),
    ("procedure_sector_observation", "Osservazioni settori richiesti", "semantic.procedure_sector_observation", "semantic", "Requested activities mapped to versioned sector concepts."),
    ("projection_issue", "Questioni di proiezione", "semantic.projection_issue", "semantic_issue", "Unmapped/ambiguous semantic items requiring review."),
    ("entity_projection_resolution", "Decisioni identità semantiche", "semantic.entity_projection_resolution", "resolution", "Accepted or unresolved semantic identity decisions."),
    ("legal_entity", "Legal entity canoniche", "core.legal_entity", "canonical", "Canonical subjects created only after guarded resolution."),
    ("entity_name", "Nomi canonici osservati", "core.entity_name", "canonical", "Source-supported names with temporal provenance."),
    ("entity_identifier", "Identificativi canonici osservati", "core.entity_identifier", "canonical", "Source-supported identifiers attached to resolved entities."),
    ("address", "Indirizzi canonici osservati", "core.address", "canonical", "Source-supported address objects."),
    ("establishment", "Sedi canoniche osservate", "core.establishment", "canonical", "Resolved entity establishments."),
    ("entity_resolution", "Entity resolution", "provenance.entity_resolution", "resolution", "Auditable mention-to-entity decisions."),
    ("white_list_relationship", "Relazioni White List", "whitelist.white_list_relationship", "canonical", "Canonical entity × register relationships."),
    ("relationship_state_version", "Stati White List", "whitelist.relationship_state_version", "canonical", "Temporal source-supported relationship state versions."),
    ("relationship_sector", "Settori della relazione", "whitelist.relationship_sector", "relationship_sector", "Sectors actually represented/listed on a White List relationship."),
    ("white_list_procedure", "Procedure canoniche", "whitelist.white_list_procedure", "canonical", "Resolved administrative procedures."),
    ("procedure_version", "Stati procedure", "whitelist.procedure_version", "canonical", "Temporal procedure versions."),
    ("procedure_sector", "Settori richiesti per procedura", "whitelist.procedure_sector", "canonical", "Canonical requested sectors attached to procedures."),
    ("procedure_resolution", "Procedure resolution", "provenance.procedure_resolution", "resolution", "Auditable procedure-mention resolutions."),
    ("field_mapping", "Field mapping", "mapping.field_mapping", "mapping", "Versioned source-field to canonical-field mappings."),
    ("derived_event", "Eventi derivati", "derived.derived_event", "derived", "Reproducible historical/observational events derived after canonical history exists."),
]


def _count(cur, table: str) -> int:
    cur.execute(f"SELECT count(*) FROM {table}")
    return int(cur.fetchone()[0])


def _status(kind: str, count: int, *, unresolved: int, projection_issues: int) -> tuple[str, str]:
    if kind == "relationship_sector" and count == 0:
        return (
            "NOT_APPLICABLE_FROM_CURRENT_SOURCE",
            "The current Cosenza combined source publishes requested activities; those belong to procedures, not relationship sectors.",
        )
    if kind == "derived" and count == 0:
        return (
            "NOT_YET_PROCESSED",
            "Derived longitudinal events are intentionally generated only after canonical history is established.",
        )
    if kind == "semantic_issue":
        if count:
            return ("REQUIRES_REVIEW", f"{count} semantic projection issue(s) remain reviewable.")
        return ("POPULATED_NO_OPEN_ISSUES", "Semantic projection ran and produced no issues for the current source scope.")
    if kind == "resolution" and count == 0 and unresolved:
        return ("REQUIRES_RESOLUTION", f"{unresolved} semantic observations still require identity/procedure resolution.")
    if count > 0:
        if kind == "canonical" and unresolved:
            return (
                "POPULATED_WITH_UNRESOLVED_EDGE_CASES",
                f"Canonical layer is populated; {unresolved} entity observation(s) remain deliberately unresolved.",
            )
        if kind == "semantic" and projection_issues:
            return (
                "POPULATED_WITH_REVIEW_ITEMS",
                f"Semantic layer is populated; {projection_issues} projection issue(s) are retained for review.",
            )
        return ("POPULATED", "Rows exist in the current reconstructed database.")
    if kind in {"source", "semantic", "mapping", "canonical", "resolution"}:
        return ("NOT_YET_POPULATED", "No rows currently materialised for this object in the reconstructed database.")
    return ("EMPTY", "No rows currently materialised.")


def build_population(conn) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) FROM semantic.entity_projection_resolution
            WHERE decision_status_code IN ('requires_resolution','requires_review')
            """
        )
        unresolved = int(cur.fetchone()[0])
        projection_issues = _count(cur, "semantic.projection_issue")
        rows = []
        for code, label, table, kind, meaning in OBJECTS:
            count = _count(cur, table)
            status, reason = _status(
                kind,
                count,
                unresolved=unresolved,
                projection_issues=projection_issues,
            )
            rows.append(
                {
                    "object_code": code,
                    "label": label,
                    "table": table,
                    "layer": kind,
                    "count": count,
                    "status": status,
                    "reason": reason,
                    "meaning": meaning,
                }
            )
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "unresolved_entity_observations": unresolved,
        "projection_issue_count": projection_issues,
        "objects": rows,
    }


def build_from_dsn(dsn: str) -> dict[str, Any]:
    if psycopg is None:
        raise RuntimeError("psycopg is required; install the 'database' extra") from _IMPORT_ERROR
    with psycopg.connect(dsn) as conn:
        return build_population(conn)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export actual PostgreSQL population counts/status for the Dataset Explorer."
    )
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_from_dsn(args.dsn)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "objects": len(payload["objects"])}, indent=2))


if __name__ == "__main__":
    main()
