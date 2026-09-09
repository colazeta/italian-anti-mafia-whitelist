from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from white_list_archive.acquisition.source_population_coverage import _read_csv, build_coverage

ISSUE_SOURCE_POPULATION = 20
ISSUE_DURABLE_STORAGE = 16
DEFAULT_ACTIVATION_RECORD = "docs/architecture/evidence-store-activation-2026-09-09.md"


def _is_issue_reference(value: Any, issue_number: int) -> bool:
    if value == issue_number:
        return True
    if isinstance(value, str):
        return value.rstrip("/").endswith(f"/issues/{issue_number}")
    return False


def _dedupe(values: list[Any]) -> list[Any]:
    out: list[Any] = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


def _authority_population_state(report: dict[str, Any]) -> dict[str, bool]:
    scopes: dict[str, list[bool]] = defaultdict(list)
    for row in report["scopes"]:
        scopes[row["authority_key"]].append(bool(row["source_population_complete"]))
    return {authority: all(values) for authority, values in scopes.items()}


def reconcile_monitoring_state(
    state: dict[str, Any],
    population_report: dict[str, Any],
    *,
    durable_storage_run_url: str,
    durable_storage_verified_at: str,
    activation_record: str = DEFAULT_ACTIVATION_RECORD,
) -> dict[str, Any]:
    """Reconcile derived monitoring fields with evidence already accepted elsewhere.

    This function does not create source facts. It synchronises the operational ledger
    with the deterministic listed/applicant coverage report and with a separately
    completed live durable-storage verification gate.
    """

    population_state = _authority_population_state(population_report)

    for row in state["prefectures"]:
        authority = row["authority_key"]
        if authority in population_state:
            complete = population_state[authority]
            row["population_scopes_complete"] = complete
            if complete:
                row["unresolved_issue"] = [
                    value
                    for value in row.get("unresolved_issue", [])
                    if not _is_issue_reference(value, ISSUE_SOURCE_POPULATION)
                ]

        # Issue #16 was previously injected into Bari only because the global durable
        # storage prerequisite was unresolved. The live R2 gate now satisfies that
        # prerequisite; Bari itself has no captured source object awaiting promotion.
        if authority == "bari" and population_state.get(authority):
            row["unresolved_issue"] = [
                value
                for value in row.get("unresolved_issue", [])
                if not _is_issue_reference(value, ISSUE_DURABLE_STORAGE)
            ]
            if row.get("coverage_status") == "BLOCKED":
                row["coverage_status"] = row.get("last_completed_coverage_status") or "SOURCE_IDENTIFIED"
            row["actionable_issue"] = bool(row.get("unresolved_issue"))
            evidence = row.setdefault("evidence", [])
            evidence.append("docs/sources/source-population-resolution-2026-09-09.md")
            row["evidence"] = _dedupe(evidence)

        if authority == "udine" and population_state.get(authority):
            row["actionable_issue"] = bool(row.get("unresolved_issue"))
            evidence = row.setdefault("evidence", [])
            evidence.append("docs/sources/source-population-resolution-2026-09-09.md")
            row["evidence"] = _dedupe(evidence)

        # The live workflow verified the exact frozen Cosenza bytes in R2, including
        # repeated writes under Bucket Lock, full retrieval and SHA-256 recomputation.
        if authority == "cosenza":
            row["durable_evidence_verified"] = True
            row["archived_evidence_storage_status"] = "durable_r2_verified"
            row["unresolved_issue"] = [
                value
                for value in row.get("unresolved_issue", [])
                if not _is_issue_reference(value, ISSUE_DURABLE_STORAGE)
            ]
            if row.get("coverage_status") == "BLOCKED":
                row["coverage_status"] = (
                    row.get("last_completed_coverage_stage")
                    or row.get("last_completed_coverage_status")
                    or "VALIDATED"
                )
            row["actionable_issue"] = bool(row.get("unresolved_issue"))
            evidence = row.setdefault("evidence", [])
            evidence.extend([activation_record, durable_storage_run_url])
            row["evidence"] = _dedupe(evidence)

    storage = state.setdefault("operational_prerequisites", {}).setdefault(
        "durable_evidence_storage", {}
    )
    storage.update(
        {
            "status": "VERIFIED",
            "issue": ISSUE_DURABLE_STORAGE,
            "verification_evidence": _dedupe(
                [
                    *storage.get("verification_evidence", []),
                    durable_storage_run_url,
                    activation_record,
                ]
            ),
            "verified_at": durable_storage_verified_at,
            "required_action": (
                "Use the live-verified private R2 evidence backend for production captures. "
                "Independent backup/restore and database promotion remain tracked separately "
                "under issue #16 and do not reopen this expansion prerequisite."
            ),
        }
    )
    return state


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconcile the national operational monitoring ledger with validated evidence."
    )
    parser.add_argument(
        "--state", type=Path, default=Path("data/monitoring/national_coverage.json")
    )
    parser.add_argument(
        "--verified-pages",
        type=Path,
        default=Path("data/source_registry/verified_primary_pages.csv"),
    )
    parser.add_argument(
        "--source-series",
        type=Path,
        default=Path("data/source_registry/source_series_inventory.csv"),
    )
    parser.add_argument("--durable-storage-run-url", required=True)
    parser.add_argument("--durable-storage-verified-at", required=True)
    parser.add_argument("--activation-record", default=DEFAULT_ACTIVATION_RECORD)
    args = parser.parse_args()

    state = json.loads(args.state.read_text(encoding="utf-8"))
    report = build_coverage(_read_csv(args.verified_pages), _read_csv(args.source_series))
    reconciled = reconcile_monitoring_state(
        state,
        report,
        durable_storage_run_url=args.durable_storage_run_url,
        durable_storage_verified_at=args.durable_storage_verified_at,
        activation_record=args.activation_record,
    )
    args.state.write_text(
        json.dumps(reconciled, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "complete_register_scopes": report["complete_register_scope_count"],
                "incomplete_register_scopes": report["incomplete_register_scope_count"],
                "durable_evidence_storage": reconciled["operational_prerequisites"][
                    "durable_evidence_storage"
                ]["status"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
