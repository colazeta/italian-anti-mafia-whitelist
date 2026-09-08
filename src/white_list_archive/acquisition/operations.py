"""Internal national work queue. This module never publishes company data."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re

COVERAGE = {"NOT_STARTED", "SOURCE_IDENTIFIED", "CAPTURED", "PARSER_IMPLEMENTED", "VALIDATED", "PUBLISHED", "BLOCKED", "NOT_APPLICABLE"}
MONITORING = {"NEVER_CHECKED", "CURRENT", "CHECK_DUE", "CHECK_FAILED", "SOURCE_CHANGED", "PROCESSING_UPDATE"}
STAGES = {"NOT_STARTED": 0, "SOURCE_IDENTIFIED": 1, "CAPTURED": 2, "PARSER_IMPLEMENTED": 3, "VALIDATED": 4, "PUBLISHED": 5}
GATES = ("source_verified", "current_edition_identified", "capture_implemented", "parser_implemented", "parser_validated", "company_observations_loaded", "canonical_integration_validated", "public_export_enabled", "durable_evidence_verified", "population_scopes_complete")


def timestamp(value: str | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Source checks require timezone-aware timestamps")
    return result.astimezone(timezone.utc)


def terminal(row: dict) -> bool:
    if row["coverage_status"] == "PUBLISHED":
        return all(row.get(key) is True for key in GATES) and bool(row.get("completion_evidence"))
    return row["coverage_status"] == "NOT_APPLICABLE" and bool(row.get("terminal_reason")) and bool(row.get("completion_evidence"))


def mode_for(rows: list[dict]) -> str:
    return "MAINTENANCE_MODE" if rows and all(terminal(row) for row in rows) else "EXPANSION_MODE"


def validate(ledger: dict, authority_keys: set[str]) -> None:
    rows = ledger["prefectures"]
    keys = [r["authority_key"] for r in rows]
    if len(keys) != len(set(keys)) or set(keys) != authority_keys:
        raise ValueError("Ledger must contain every canonical territorial authority exactly once")
    for row in rows:
        if row["coverage_status"] not in COVERAGE or row["monitoring_status"] not in MONITORING:
            raise ValueError("Unknown coverage or monitoring state")
        if row["coverage_status"] in {"PUBLISHED", "NOT_APPLICABLE"} and not terminal(row):
            raise ValueError("Unjustified terminal coverage")
        if row["coverage_status"] == "BLOCKED" and not row.get("unresolved_issue"):
            raise ValueError("Blocked coverage needs a recorded issue")
        for field in ("last_successful_source_check_at", "last_attempted_source_check_at", "last_content_change_at"):
            timestamp(row[field])
        if timestamp(row["last_successful_source_check_at"]) > timestamp(row["last_attempted_source_check_at"]):
            raise ValueError("Successful source check cannot follow the latest attempt")
        if row["monitoring_status"] == "CURRENT" and not row["last_successful_source_check_at"]:
            raise ValueError("Current monitoring requires successful evidence")
        if row["monitoring_status"] == "NEVER_CHECKED" and row["last_attempted_source_check_at"]:
            raise ValueError("Attempted source cannot be never checked")
        for digest in row["known_content_sha256"]:
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Invalid content identity")
    if ledger["mode"] != mode_for(rows):
        raise ValueError("Operational mode does not match national completion")


def transition(ledger: dict, at: str) -> dict:
    """Record a mode transition; incomplete coverage automatically restores expansion."""
    timestamp(at)
    result = deepcopy(ledger)
    mode = mode_for(result["prefectures"])
    if mode != result["mode"]:
        result["mode_transitions"].append({"at": at, "from": result["mode"], "to": mode})
        result["mode"] = mode
    return result


def priority_queue(ledger: dict) -> list[dict]:
    """Recompute on every selection. Null checks come before dated checks."""
    rows = ledger["prefectures"]
    if ledger["mode"] != mode_for(rows):
        raise ValueError("Apply the explicit mode transition before selecting")
    if ledger["mode"] == "MAINTENANCE_MODE":
        return sorted(rows, key=lambda r: (
            timestamp(r["last_successful_source_check_at"]),
            r["monitoring_status"] != "CHECK_FAILED",
            r.get("latest_source_reference_date") or "",
            timestamp(r["last_content_change_at"]), r["authority_key"]))
    represented = {r["region"] for r in rows if r["public_export_enabled"]}
    candidates = [r for r in rows if not terminal(r) and r["coverage_status"] != "BLOCKED"]
    return sorted(candidates, key=lambda r: (
        not r["source_verified"],
        -STAGES.get(r["coverage_status"], 0),
        not r.get("canonical_integration_validated", False),
        not bool(r.get("actionable_issue")),
        r["region"] in represented,
        r.get("last_successful_investigation_on") or "",
        timestamp(r["last_successful_source_check_at"]), r["authority_key"]))


def work_decision(ledger: dict) -> dict:
    """Operational preflight, separate from territorial priority and coverage."""
    prerequisites = ledger.get("operational_prerequisites", {})
    storage = prerequisites.get("durable_evidence_storage", {})
    ready = (storage.get("status") == "VERIFIED" and
             bool(storage.get("verification_evidence")) and
             bool(storage.get("verified_at")))
    if ready:
        timestamp(storage["verified_at"])
    if not ready:
        return {"mode": ledger["mode"], "action": "RESOLVE_GLOBAL_PREREQUISITE",
                "current_prefecture": None, "publication_allowed": False,
                "blocker": "DURABLE_EVIDENCE_STORAGE",
                "issue": storage.get("issue", 16),
                "next_action": "Provision designated private storage and verify writes, retrieval integrity and retention on existing Cosenza evidence."}
    queue = priority_queue(ledger)
    if not queue:
        return {"mode": ledger["mode"], "action": "RESOLVE_SOURCE_ACCESS",
                "current_prefecture": None, "publication_allowed": False,
                "blocked_prefectures": [r["authority_key"] for r in ledger["prefectures"]
                                        if r["coverage_status"] == "BLOCKED"]}
    return {"mode": ledger["mode"], "action": "CHECK_PREFECTURE",
            "current_prefecture": queue[0]["authority_key"],
            "publication_allowed": False,
            "next_action": "Investigate source; publication requires all separate per-Prefecture gates."}


def record_check(ledger: dict, authority_key: str, *, at: str, evidence: str,
                 content_sha256: list[str] | None = None, error: str | None = None,
                 assessment: dict | None = None) -> dict:
    """Call only after a complete landing-page/resource investigation, never just HTTP 200.

    Missing or failed resources are a failed check. Successful no-change checks
    advance recency without creating a capture or claiming an edition-date change.
    """
    if not evidence or (error is None and not content_sha256):
        raise ValueError("Check needs evidence and either complete content identities or an error")
    if error is not None and content_sha256 is not None:
        raise ValueError("Partial/failed checks must not replace known content identities")
    if error is None and not all((assessment or {}).get(key) is True for key in (
            "official_publication_surface_verified", "listed_and_applicant_accounted_for",
            "all_current_resources_verified")):
        raise ValueError("Successful check requires explicit complete source assessment; HTTP availability is insufficient")
    hashes = sorted(set(content_sha256 or []))
    if any(not re.fullmatch(r"[0-9a-f]{64}", h) for h in hashes):
        raise ValueError("Invalid content identity")
    result = deepcopy(ledger)
    row = next(r for r in result["prefectures"] if r["authority_key"] == authority_key)
    if timestamp(at) <= timestamp(row["last_attempted_source_check_at"]):
        raise ValueError("Check timestamps must advance")
    row["last_attempted_source_check_at"] = at
    changed = None
    if error is not None:
        row["monitoring_status"] = "CHECK_FAILED"
    else:
        changed = hashes != sorted(set(row["known_content_sha256"]))
        row["last_successful_source_check_at"] = at
        pending = row.get("source_update_pending", False) or row["monitoring_status"] in {"SOURCE_CHANGED", "PROCESSING_UPDATE"}
        if changed:
            row["monitoring_status"] = "SOURCE_CHANGED"
            row["source_update_pending"] = True
        elif pending and row["monitoring_status"] == "CHECK_FAILED":
            row["monitoring_status"] = "SOURCE_CHANGED"
        elif not pending:
            row["monitoring_status"] = "CURRENT"
        if changed:
            row["last_content_change_at"] = at
            row["known_content_sha256"] = hashes
    result["checks"].append({"authority_key": authority_key, "at": at,
        "evidence": evidence, "error": error, "content_changed": changed,
        "content_sha256": hashes if error is None else None,
        "assessment": deepcopy(assessment)})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--authorities", type=Path, default=Path("data/source_registry/territorial_authorities.csv"))
    args = parser.parse_args()
    import csv
    ledger = json.loads(args.ledger.read_text())
    with args.authorities.open() as handle:
        keys = {row["authority_key"] for row in csv.DictReader(handle)}
    validate(ledger, keys)
    queue = priority_queue(ledger)
    print(json.dumps({"decision": work_decision(ledger), "mode": ledger["mode"],
        "next_prefecture": work_decision(ledger)["current_prefecture"],
        "first_ranked_prefecture": queue[0]["authority_key"] if queue else None,
        "queue": [r["authority_key"] for r in queue]}, indent=2))


if __name__ == "__main__":
    main()
