"""Conservative denominator for national temporal-archive recovery.

This layer reconciles two different kinds of evidence without conflating them:

* archive-first captures with stable capture identity and immutable provenance; and
* historical byte versions known from transition notes, manifests or other reviewed
  evidence but lacking a durable capture/check identity.

The latter are part of the recovery problem but can never be promoted to ``verified``
merely because matching bytes exist. A caller must supply an explicit evidence version
key; it is a reconciliation key, not a retroactively invented SourceEdition or capture
identifier.
"""
from __future__ import annotations

from collections import Counter
import hashlib
from pathlib import Path
import re
from typing import Any

from white_list_archive.storage.archive_inventory import (
    STATUSES,
    build_archive_inventory,
)
from white_list_archive.storage.evidence import EvidenceStore

SCHEMA_VERSION = 1
_SHA256_RE = re.compile(r"[a-f0-9]{64}")


def _verified_recovery_copy(paths: list[str], *, sha256: str, byte_size: int) -> bool:
    for raw_path in paths:
        path = Path(raw_path)
        try:
            with path.open("rb") as handle:
                data = handle.read(byte_size + 1)
        except (FileNotFoundError, IsADirectoryError, PermissionError, OSError):
            continue
        if len(data) == byte_size and hashlib.sha256(data).hexdigest() == sha256:
            return True
    return False


def _validate_known_version(expected: dict[str, Any]) -> dict[str, Any]:
    required = {
        "authority_key",
        "source_key",
        "evidence_version_key",
        "sha256",
        "byte_size",
        "evidence_refs",
        "recovery_paths",
        "durable_absence_confirmed",
    }
    if not isinstance(expected, dict) or set(expected) != required:
        raise ValueError("Unapproved known-version recovery expectation")

    authority_key = expected["authority_key"]
    source_key = expected["source_key"]
    version_key = expected["evidence_version_key"]
    if any(not isinstance(value, str) or not value.strip()
           for value in (authority_key, source_key, version_key)):
        raise ValueError("Known version requires authority, source and evidence version keys")

    digest = expected["sha256"]
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        raise ValueError("Known version requires a lowercase SHA-256")

    byte_size = expected["byte_size"]
    if byte_size is not None and (type(byte_size) is not int or byte_size <= 0):
        raise ValueError("Known-version byte_size must be a positive integer or null")

    evidence_refs = expected["evidence_refs"]
    if (not isinstance(evidence_refs, list) or not evidence_refs or
            any(not isinstance(ref, str) or not ref.strip() for ref in evidence_refs)):
        raise ValueError("Known version requires at least one evidence reference")

    recovery_paths = expected["recovery_paths"]
    if not isinstance(recovery_paths, list) or any(not isinstance(path, str) for path in recovery_paths):
        raise ValueError("recovery_paths must be a list of paths")
    if type(expected["durable_absence_confirmed"]) is not bool:
        raise ValueError("durable_absence_confirmed must be boolean")
    return expected


def build_recovery_denominator(expectations: dict[str, Any], store: EvidenceStore) -> dict[str, Any]:
    """Build a denominator without fabricating capture identity for legacy evidence.

    ``known_versions`` admits byte identities supported by reviewed historical evidence
    even when no stable capture UUID/catalogue record survives. Such an item may be
    ``recoverable_pending`` when exact bytes are available outside the governed store,
    or ``missing`` only under the same positive-absence and completed-search contract as
    captures. It cannot be ``verified`` until real immutable capture provenance exists.
    """
    if not isinstance(expectations, dict) or expectations.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported recovery denominator expectations")
    allowed = {
        "schema_version",
        "generated_at",
        "recovery_search_complete",
        "captures",
        "known_versions",
    }
    if set(expectations) != allowed:
        raise ValueError("Unapproved recovery denominator expectations envelope")
    if not isinstance(expectations["generated_at"], str) or not expectations["generated_at"].strip():
        raise ValueError("Denominator generation timestamp is required")
    if type(expectations["recovery_search_complete"]) is not bool:
        raise ValueError("recovery_search_complete must be boolean")
    if not isinstance(expectations["captures"], list) or not isinstance(expectations["known_versions"], list):
        raise ValueError("captures and known_versions must be lists")

    capture_inventory = build_archive_inventory(
        {
            "schema_version": 1,
            "generated_at": expectations["generated_at"],
            "recovery_search_complete": expectations["recovery_search_complete"],
            "captures": expectations["captures"],
        },
        store,
    )

    rows: list[dict[str, Any]] = []
    authorities: set[str] = set()
    durable_content: set[str] = set()
    known_identities: set[tuple[str, str]] = set()

    for row in capture_inventory["captures"]:
        authorities.add(row["authority_key"])
        if row["durable_original_verified"]:
            durable_content.add(row["sha256"])
        rows.append(
            {
                **row,
                "identity_kind": "capture",
                "evidence_version_key": None,
                "evidence_refs": [],
                "byte_size_known": True,
            }
        )

    for raw in expectations["known_versions"]:
        expected = _validate_known_version(raw)
        identity = (expected["source_key"], expected["evidence_version_key"])
        if identity in known_identities:
            raise ValueError("Duplicate known-version recovery expectation")
        known_identities.add(identity)
        authorities.add(expected["authority_key"])

        digest = expected["sha256"]
        byte_size = expected["byte_size"]
        durable_original_verified = False
        provider_error = None
        verification_blocker = None
        if byte_size is None:
            verification_blocker = "byte_size_unknown"
        else:
            try:
                store.read_verified({"sha256": digest, "byte_size": byte_size})
                durable_original_verified = True
                durable_content.add(digest)
            except Exception as exc:  # provider failure is uncertainty, never absence
                provider_error = type(exc).__name__

        recoverable = False
        if not durable_original_verified and byte_size is not None:
            recoverable = _verified_recovery_copy(
                expected["recovery_paths"],
                sha256=digest,
                byte_size=byte_size,
            )

        if recoverable:
            status = "recoverable_pending"
        elif (byte_size is not None and expected["durable_absence_confirmed"] and
              expectations["recovery_search_complete"]):
            status = "missing"
        else:
            # Even verified durable bytes are insufficient without immutable capture/check
            # provenance. Do not retroactively mint a capture ID from a hash or note.
            status = "not_verified"

        rows.append(
            {
                "identity_kind": "known_version",
                "authority_key": expected["authority_key"],
                "source_key": expected["source_key"],
                "capture_id": None,
                "evidence_version_key": expected["evidence_version_key"],
                "evidence_refs": list(expected["evidence_refs"]),
                "sha256": digest,
                "byte_size": byte_size,
                "byte_size_known": byte_size is not None,
                "status": status,
                "durable_original_verified": durable_original_verified,
                "capture_provenance_verified": False,
                "provider_check_error_class": provider_error,
                "verification_blocker": verification_blocker,
            }
        )

    counts = Counter(row["status"] for row in rows)
    if set(counts) - STATUSES:
        raise AssertionError("Unexpected denominator status")

    all_hashes = {row["sha256"] for row in rows}
    capture_metrics = capture_inventory["metrics"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": expectations["generated_at"],
        "recovery_search_complete": expectations["recovery_search_complete"],
        "metrics": {
            "source_authorities_covered": len(authorities),
            "denominator_items": len(rows),
            "captures_expected": capture_metrics["captures_expected"],
            "known_versions_without_capture_identity": len(expectations["known_versions"]),
            "distinct_content_objects_known": len(all_hashes),
            "durably_retrievable_content_objects": len(durable_content),
            "captures_with_verified_provenance": capture_metrics["captures_with_verified_provenance"],
            "verified": counts["verified"],
            "recoverable_pending": counts["recoverable_pending"],
            "missing": counts["missing"],
            "not_verified": counts["not_verified"],
        },
        "items": rows,
    }
