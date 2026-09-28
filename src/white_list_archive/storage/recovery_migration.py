"""Schema-v2 recovery materialisation with explicit legacy capture migrations.

The v1 recovery materialiser remains stable for existing callers. This module adds one
narrow compatibility operation: replace an exact repository-supported historical
known_version with an immutable recovered capture when contemporaneous acquisition
provenance and original bytes have survived.

A migration is one-for-one. It may not create a new historical denominator item, infer
a SourceSeries, change byte identity, or use current processing time as acquisition time.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from white_list_archive.storage.evidence import EvidenceStore
from white_list_archive.storage.recovery_denominator import build_recovery_denominator
from white_list_archive.storage.recovery_evidence import build_repository_recovery_expectations
from white_list_archive.storage.recovery_materialize import (
    _load_reviewed_source_authorities,
    apply_recovery_plan,
)

_PLAN_FIELDS = {
    "schema_version",
    "generated_at",
    "recovery_search_complete",
    "captures",
    "known_version_recovery",
    "capture_migrations",
}
_MIGRATION_FIELDS = {
    "authority_key",
    "evidence_version_key",
    "sha256",
    "capture",
    "catalogue",
    "operator_evidence_refs",
}


def _validate_migration(row: Any) -> tuple[str, str, str]:
    if not isinstance(row, dict) or set(row) != _MIGRATION_FIELDS:
        raise ValueError("Unapproved capture migration")
    authority = row["authority_key"]
    version_key = row["evidence_version_key"]
    digest = row["sha256"]
    if any(not isinstance(value, str) or not value.strip() for value in (authority, version_key, digest)):
        raise ValueError("Capture migration requires authority, evidence key and SHA-256")
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError("Capture migration requires lowercase SHA-256")
    capture = row["capture"]
    if not isinstance(capture, dict):
        raise ValueError("Capture migration requires a frozen capture manifest")
    source_key = capture.get("source_key")
    capture_id = capture.get("capture_id")
    if not isinstance(source_key, str) or not source_key.strip():
        raise ValueError("Capture migration requires source_key")
    if not isinstance(capture_id, str) or not capture_id.strip():
        raise ValueError("Capture migration requires capture_id")
    if capture.get("sha256") != digest:
        raise ValueError("Capture migration digest disagrees with recovered capture")
    if type(capture.get("byte_size")) is not int or capture["byte_size"] <= 0:
        raise ValueError("Capture migration requires recovered byte size")
    if not isinstance(row["catalogue"], dict):
        raise ValueError("Capture migration requires immutable catalogue receipt")
    refs = row["operator_evidence_refs"]
    if not isinstance(refs, list) or not refs or any(
        not isinstance(ref, str) or not ref.strip() for ref in refs
    ):
        raise ValueError("Capture migration requires operator evidence references")
    return authority, version_key, digest


def _validate_plan(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict) or set(plan) != _PLAN_FIELDS or plan.get("schema_version") != 2:
        raise ValueError("Unsupported recovery migration plan")
    if not isinstance(plan["capture_migrations"], list):
        raise ValueError("capture_migrations must be a list")
    identities: set[tuple[str, str, str]] = set()
    capture_ids: set[tuple[str, str]] = set()
    for row in plan["captures"]:
        capture = row.get("capture") if isinstance(row, dict) else None
        if isinstance(capture, dict):
            identity = (capture.get("source_key"), capture.get("capture_id"))
            if all(isinstance(value, str) and value for value in identity):
                capture_ids.add(identity)
    for row in plan["capture_migrations"]:
        identity = _validate_migration(row)
        if identity in identities:
            raise ValueError("Duplicate capture migration")
        identities.add(identity)
        capture_identity = (row["capture"]["source_key"], row["capture"]["capture_id"])
        if capture_identity in capture_ids:
            raise ValueError("Recovered capture identity duplicates another plan capture")
        capture_ids.add(capture_identity)
    return plan


def apply_capture_migrations(
    expectations: dict[str, Any],
    migrations: list[dict[str, Any]],
    *,
    source_authorities: dict[str, str],
) -> tuple[dict[str, Any], dict[tuple[str, str], list[str]]]:
    """Replace exact known-version rows one-for-one with recovered capture identities."""
    result = deepcopy(expectations)
    indexed = {
        (row["authority_key"], row["evidence_version_key"], row["sha256"]): row
        for row in result["known_versions"]
    }
    migrated_keys: set[tuple[str, str, str]] = set()
    migrated_capture_rows: list[dict[str, Any]] = []
    migration_refs: dict[tuple[str, str], list[str]] = {}

    for migration in migrations:
        key = _validate_migration(migration)
        historical = indexed.get(key)
        if historical is None:
            raise ValueError("Capture migration references a historical version absent from repository evidence")
        if key in migrated_keys:
            raise ValueError("Capture migration consumes one historical version more than once")
        capture = migration["capture"]
        source_key = capture["source_key"]
        if historical.get("source_key") is not None and historical["source_key"] != source_key:
            raise ValueError("Capture migration SourceSeries disagrees with repository evidence")
        if historical.get("byte_size") is not None and historical["byte_size"] != capture["byte_size"]:
            raise ValueError("Capture migration byte size disagrees with repository evidence")
        reviewed_authority = source_authorities.get(source_key)
        if reviewed_authority is None:
            raise ValueError("Capture migration SourceSeries is absent from reviewed registry")
        if reviewed_authority != migration["authority_key"]:
            raise ValueError("Capture migration authority disagrees with reviewed SourceSeries")
        migrated_keys.add(key)
        migrated_capture_rows.append(
            {
                "authority_key": migration["authority_key"],
                "capture": deepcopy(capture),
                "catalogue": deepcopy(migration["catalogue"]),
                "recovery_paths": [],
                "durable_absence_confirmed": False,
            }
        )
        migration_refs[(source_key, capture["capture_id"])] = list(
            migration["operator_evidence_refs"]
        )

    before = len(result["known_versions"]) + len(result["captures"])
    result["known_versions"] = [
        row
        for row in result["known_versions"]
        if (row["authority_key"], row["evidence_version_key"], row["sha256"])
        not in migrated_keys
    ]
    result["captures"].extend(migrated_capture_rows)
    after = len(result["known_versions"]) + len(result["captures"])
    if before != after:
        raise AssertionError("Capture migration changed recovery denominator cardinality")
    return result, migration_refs


def materialise_migrating_recovery(
    *,
    repository_root: Path,
    plan: dict[str, Any],
    store: EvidenceStore,
) -> dict[str, Any]:
    """Materialise schema-v2 recovery without double-counting migrated acquisitions."""
    plan = _validate_plan(plan)
    repository_root = repository_root.resolve()
    repository_expectations = build_repository_recovery_expectations(
        repository_root=repository_root,
        monitoring_path=repository_root / "data" / "monitoring" / "national_coverage.json",
        captures_root=repository_root / "data" / "captures",
        public_history_path=repository_root / "data" / "history" / "public_history.json",
        generated_at=plan["generated_at"],
    )
    source_authorities = _load_reviewed_source_authorities(
        repository_root / "data" / "source_registry" / "source_series_inventory.csv"
    )

    base_plan = {
        "schema_version": 1,
        "generated_at": plan["generated_at"],
        "recovery_search_complete": plan["recovery_search_complete"],
        "captures": deepcopy(plan["captures"]),
        "known_version_recovery": deepcopy(plan["known_version_recovery"]),
    }
    expectations = apply_recovery_plan(
        repository_expectations,
        base_plan,
        source_authorities=source_authorities,
    )
    expectations, migration_refs = apply_capture_migrations(
        expectations,
        plan["capture_migrations"],
        source_authorities=source_authorities,
    )

    expected_items = len(repository_expectations["known_versions"]) + len(plan["captures"])
    actual_items = len(expectations["known_versions"]) + len(expectations["captures"])
    if actual_items != expected_items:
        raise AssertionError("Schema-v2 recovery changed denominator cardinality")

    report = build_recovery_denominator(expectations, store)
    refs_by_identity = {
        (row["capture"]["source_key"], row["capture"]["capture_id"]): list(
            row.get("operator_evidence_refs", [])
        )
        for row in plan["captures"]
    }
    refs_by_identity.update(migration_refs)
    for item in report["items"]:
        if item.get("identity_kind") != "capture":
            continue
        identity = (item.get("source_key"), item.get("capture_id"))
        if identity not in refs_by_identity:
            raise AssertionError("Materialised capture missing schema-v2 plan identity")
        item["evidence_refs"] = refs_by_identity[identity]
    return report
