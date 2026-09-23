"""Materialise the national recovery denominator against governed private evidence.

Repository evidence defines the historical denominator; an operator-reviewed private
plan supplies only operational facts that cannot safely be inferred from Git: exact
archive-first capture receipts, recovery-package paths, reviewed byte sizes and
positive durable-absence decisions. The plan cannot create additional historical
``known_version`` identities or relabel reviewed SourceSeries ownership.
"""
from __future__ import annotations

import argparse
import csv
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
from white_list_archive.storage.recovery_denominator import build_recovery_denominator
from white_list_archive.storage.recovery_evidence import build_repository_recovery_expectations

_PLAN_FIELDS = {
    "schema_version",
    "generated_at",
    "recovery_search_complete",
    "captures",
    "known_version_recovery",
}
_KNOWN_RECOVERY_FIELDS = {
    "authority_key",
    "evidence_version_key",
    "sha256",
    "byte_size",
    "recovery_paths",
    "durable_absence_confirmed",
    "operator_evidence_refs",
}
_CAPTURE_FIELDS = {
    "authority_key",
    "capture",
    "catalogue",
    "recovery_paths",
    "durable_absence_confirmed",
}
_CAPTURE_FIELDS_WITH_EVIDENCE = _CAPTURE_FIELDS | {"operator_evidence_refs"}
_REQUIRED_SERIES_REGISTRY_FIELDS = {"source_series_key", "authority_key"}


def _aware_timestamp(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} requires an explicit timezone")
    return value


def _load_reviewed_source_authorities(path: Path) -> dict[str, str]:
    """Return the reviewed stable SourceSeries → authority binding.

    Recovery plans are private operational overlays. They may say where bytes were found
    or record provider readback receipts, but they are not allowed to redefine which
    authority owns a stable SourceSeries identity already governed by the repository.
    """
    try:
        handle = path.open("r", encoding="utf-8", newline="")
    except OSError as exc:
        raise ValueError(f"Unable to read reviewed SourceSeries registry: {path}") from exc
    with handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        if not _REQUIRED_SERIES_REGISTRY_FIELDS.issubset(fields):
            raise ValueError("Reviewed SourceSeries registry lacks source_series_key/authority_key")
        result: dict[str, str] = {}
        for line_number, row in enumerate(reader, start=2):
            source_key = (row.get("source_series_key") or "").strip()
            authority_key = (row.get("authority_key") or "").strip()
            if not source_key or not authority_key:
                raise ValueError(
                    f"Reviewed SourceSeries registry has blank identity at line {line_number}"
                )
            prior = result.get(source_key)
            if prior is not None and prior != authority_key:
                raise ValueError(
                    f"Reviewed SourceSeries registry assigns {source_key!r} to conflicting authorities"
                )
            result[source_key] = authority_key
    if not result:
        raise ValueError("Reviewed SourceSeries registry is empty")
    return result


def _validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict) or set(plan) != _PLAN_FIELDS or plan.get("schema_version") != 1:
        raise ValueError("Unsupported recovery materialisation plan")
    _aware_timestamp(plan["generated_at"], label="Plan generated_at")
    if type(plan["recovery_search_complete"]) is not bool:
        raise ValueError("recovery_search_complete must be boolean")
    if not isinstance(plan["captures"], list) or not isinstance(plan["known_version_recovery"], list):
        raise ValueError("captures and known_version_recovery must be lists")

    capture_ids: set[tuple[str, str]] = set()
    for row in plan["captures"]:
        if not isinstance(row, dict) or set(row) not in {_CAPTURE_FIELDS, _CAPTURE_FIELDS_WITH_EVIDENCE}:
            raise ValueError("Unapproved capture recovery-plan row")
        authority = row["authority_key"]
        capture = row["capture"]
        if not isinstance(authority, str) or not authority.strip() or not isinstance(capture, dict):
            raise ValueError("Capture recovery-plan row requires authority and capture")
        source_key = capture.get("source_key")
        capture_id = capture.get("capture_id")
        if not isinstance(source_key, str) or not source_key.strip() or not isinstance(capture_id, str) or not capture_id.strip():
            raise ValueError("Capture recovery-plan row requires source_key and capture_id")
        identity = (source_key, capture_id)
        if identity in capture_ids:
            raise ValueError("Duplicate capture in recovery materialisation plan")
        capture_ids.add(identity)
        if not isinstance(row["recovery_paths"], list) or any(not isinstance(path, str) for path in row["recovery_paths"]):
            raise ValueError("Capture recovery_paths must be a list of paths")
        if type(row["durable_absence_confirmed"]) is not bool:
            raise ValueError("Capture durable_absence_confirmed must be boolean")
        if row["catalogue"] is not None and not isinstance(row["catalogue"], dict):
            raise ValueError("Capture catalogue must be a mapping or null")
        refs = row.get("operator_evidence_refs", [])
        if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
            raise ValueError("Capture operator_evidence_refs must be a list of non-empty references")
        if (row["recovery_paths"] or row["durable_absence_confirmed"]) and not refs:
            raise ValueError("Capture operational recovery facts require operator_evidence_refs")

    overlays: set[tuple[str, str, str]] = set()
    for row in plan["known_version_recovery"]:
        if not isinstance(row, dict) or set(row) != _KNOWN_RECOVERY_FIELDS:
            raise ValueError("Unapproved known-version recovery-plan row")
        authority = row["authority_key"]
        version_key = row["evidence_version_key"]
        digest = row["sha256"]
        if any(not isinstance(value, str) or not value.strip() for value in (authority, version_key, digest)):
            raise ValueError("Known-version recovery row requires authority, evidence key and SHA-256")
        identity = (authority, version_key, digest)
        if identity in overlays:
            raise ValueError("Duplicate known-version recovery-plan row")
        overlays.add(identity)
        byte_size = row["byte_size"]
        if byte_size is not None and (type(byte_size) is not int or byte_size <= 0):
            raise ValueError("Known-version reviewed byte_size must be a positive integer or null")
        if not isinstance(row["recovery_paths"], list) or any(not isinstance(path, str) for path in row["recovery_paths"]):
            raise ValueError("Known-version recovery_paths must be a list of paths")
        if type(row["durable_absence_confirmed"]) is not bool:
            raise ValueError("Known-version durable_absence_confirmed must be boolean")
        refs = row["operator_evidence_refs"]
        if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
            raise ValueError("operator_evidence_refs must be a list of non-empty references")
        if (byte_size is not None or row["recovery_paths"] or row["durable_absence_confirmed"]) and not refs:
            raise ValueError("Operational recovery facts require operator_evidence_refs")
    return plan


def _capture_operator_evidence(plan: dict[str, Any]) -> dict[tuple[str, str], list[str]]:
    """Return decision provenance keyed by stable archive-first capture identity."""
    result: dict[tuple[str, str], list[str]] = {}
    for row in plan["captures"]:
        capture = row["capture"]
        result[(capture["source_key"], capture["capture_id"])] = list(
            row.get("operator_evidence_refs", [])
        )
    return result


def _attach_capture_operator_evidence(report: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Retain private decision evidence in the private recovery report.

    The lower-level archive inventory deliberately has no knowledge of operator-plan
    provenance. Materialisation therefore reattaches those references after provider
    verification, without exposing private paths or changing capture identity.
    """
    refs_by_identity = _capture_operator_evidence(plan)
    for item in report.get("items", []):
        if item.get("identity_kind") != "capture":
            continue
        identity = (item.get("source_key"), item.get("capture_id"))
        if identity not in refs_by_identity:
            raise AssertionError("Materialised capture missing operator-plan identity")
        item["evidence_refs"] = refs_by_identity[identity]
    return report


def apply_recovery_plan(
    repository_expectations: dict[str, Any],
    plan: dict[str, Any],
    *,
    source_authorities: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Apply reviewed operational recovery facts without expanding historical identity.

    The repository evidence remains authoritative for ``known_version`` identity. A plan
    may add a positively reviewed byte size, package paths or durable-absence result to an
    existing row, but cannot introduce a historical version that the repository has never
    evidenced. Archive-first captures are different: their stable capture UUID and private
    catalogue receipt are themselves the positive identity evidence and may enter via the
    operator plan, but every such capture requires a reviewed SourceSeries → authority
    binding and cannot be relabelled to another authority.
    """
    plan = _validate_plan(plan)
    expectations = deepcopy(repository_expectations)
    if expectations.get("schema_version") != 1:
        raise ValueError("Unsupported repository recovery expectations")
    if not isinstance(expectations.get("known_versions"), list):
        raise ValueError("Repository recovery expectations lack known_versions")
    if not isinstance(expectations.get("captures"), list) or expectations["captures"]:
        raise ValueError("Repository reconciler captures must be empty before private capture reconciliation")

    indexed: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in expectations["known_versions"]:
        key = (row.get("authority_key"), row.get("evidence_version_key"), row.get("sha256"))
        if key in indexed:
            raise ValueError("Repository recovery expectations contain duplicate known-version identity")
        indexed[key] = row

    used: set[tuple[str, str, str]] = set()
    for overlay in plan["known_version_recovery"]:
        key = (overlay["authority_key"], overlay["evidence_version_key"], overlay["sha256"])
        row = indexed.get(key)
        if row is None:
            raise ValueError("Recovery plan references a historical version absent from repository evidence")
        if key in used:
            raise ValueError("Recovery plan applies twice to one historical version")
        used.add(key)

        reviewed_size = overlay["byte_size"]
        current_size = row.get("byte_size")
        if reviewed_size is not None:
            if current_size is not None and current_size != reviewed_size:
                raise ValueError("Reviewed byte_size conflicts with repository evidence")
            row["byte_size"] = reviewed_size
        row["recovery_paths"] = list(overlay["recovery_paths"])
        row["durable_absence_confirmed"] = overlay["durable_absence_confirmed"]
        row["evidence_refs"] = list(dict.fromkeys([*row["evidence_refs"], *overlay["operator_evidence_refs"]]))

    captures = deepcopy(plan["captures"])
    if captures and source_authorities is None:
        raise ValueError(
            "Archive-first recovery captures require reviewed SourceSeries authority bindings"
        )
    if source_authorities is not None:
        for row in captures:
            source_key = row["capture"]["source_key"]
            reviewed_authority = source_authorities.get(source_key)
            if reviewed_authority is None:
                raise ValueError(
                    f"Recovery capture SourceSeries {source_key!r} is absent from reviewed SourceSeries registry"
                )
            if row["authority_key"] != reviewed_authority:
                raise ValueError(
                    f"Recovery capture authority for {source_key!r} does not match reviewed SourceSeries registry"
                )
    # The lower-level archive inventory schema remains stable. Decision-provenance
    # references belong to this private materialisation layer and are reattached to the
    # private report after provider verification.
    for row in captures:
        row.pop("operator_evidence_refs", None)

    expectations["generated_at"] = plan["generated_at"]
    expectations["recovery_search_complete"] = plan["recovery_search_complete"]
    expectations["captures"] = captures
    return expectations


def materialise_national_recovery(*, repository_root: Path, plan: dict[str, Any],
                                  store: EvidenceStore) -> dict[str, Any]:
    """Build the national denominator and verify it against governed evidence storage."""
    repository_root = repository_root.resolve()
    plan = _validate_plan(plan)
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
    expectations = apply_recovery_plan(
        repository_expectations,
        plan,
        source_authorities=source_authorities,
    )
    report = build_recovery_denominator(expectations, store)
    return _attach_capture_operator_evidence(report, plan)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--plan", type=Path, required=True,
                        help="Private reviewed recovery plan; never committed by this command")
    parser.add_argument("--report", type=Path, required=True,
                        help="New private recovery report path; existing files are never overwritten")
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Recovery report path already exists")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    store_config = StoreConfig.from_env()
    store = EvidenceStore(client_for(store_config), store_config)
    result = materialise_national_recovery(
        repository_root=args.repository_root,
        plan=plan,
        store=store,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    print("National recovery denominator materialised from reviewed evidence; report remains private.")


if __name__ == "__main__":
    main()
