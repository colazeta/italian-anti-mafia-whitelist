"""Conservative denominator for national temporal-archive recovery.

This layer reconciles different evidence classes without conflating them:

* archive-first captures with stable capture identity and immutable provenance;
* historical byte versions known from transition notes, manifests or other reviewed
  evidence but lacking a durable capture/check identity; and
* approved public-history editions, retained only as aggregate publication scopes.

Historical byte evidence is part of the recovery problem but can never be promoted to
``verified`` merely because matching bytes exist. Public-history document digests are
not treated as raw ``ContentObject`` identities because the aggregate ledger does not
preserve whether a digest originated from one source object or a source bundle.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
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
_RELEASE_SCOPE_FIELDS = {
    "history_edition_id",
    "authority_key",
    "source_key",
    "document_digest",
    "digest_semantics",
    "raw_content_object_identity_established",
    "parser_signature",
    "reference_date",
    "reference_date_raw",
    "successful_checks",
    "evidence_refs",
}
_RELEASE_CHECK_FIELDS = {"checked_at", "kind", "evidence_ref"}
_RELEASE_CHECK_KINDS = {"approved_document_verification", "historical_capture"}


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
    if not isinstance(authority_key, str) or not authority_key.strip():
        raise ValueError("Known version requires authority_key")
    if source_key is not None and (not isinstance(source_key, str) or not source_key.strip()):
        raise ValueError("Known-version source_key must be non-empty or null when not established")
    if not isinstance(version_key, str) or not version_key.strip():
        raise ValueError("Known version requires evidence_version_key")

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


def _validate_release_scope(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != _RELEASE_SCOPE_FIELDS:
        raise ValueError("Unapproved published-release scope")
    if not _SHA256_RE.fullmatch(raw["history_edition_id"]):
        raise ValueError("Published-release history edition ID must be SHA-256")
    for key in ("authority_key", "source_key", "parser_signature", "reference_date_raw"):
        if not isinstance(raw[key], str):
            raise ValueError(f"Published-release {key} must be text")
    if not raw["authority_key"].strip() or not raw["source_key"].strip() or not raw["parser_signature"].strip():
        raise ValueError("Published-release authority, source and parser signature are required")
    if raw["reference_date"] is not None and not isinstance(raw["reference_date"], str):
        raise ValueError("Published-release reference_date must be text or null")
    if not _SHA256_RE.fullmatch(raw["document_digest"]):
        raise ValueError("Published-release document digest must be SHA-256")
    if raw["digest_semantics"] != "public_history_document_digest":
        raise ValueError("Unsupported published-release digest semantics")
    if raw["raw_content_object_identity_established"] is not False:
        raise ValueError("Public history cannot establish raw ContentObject identity")

    evidence_refs = raw["evidence_refs"]
    if (not isinstance(evidence_refs, list) or not evidence_refs or
            any(not isinstance(ref, str) or not ref.strip() for ref in evidence_refs)):
        raise ValueError("Published-release scope needs evidence references")

    checks = raw["successful_checks"]
    if not isinstance(checks, list):
        raise ValueError("Published-release successful_checks must be a list")
    seen_checks: set[tuple[str, str, str]] = set()
    for check in checks:
        if not isinstance(check, dict) or set(check) != _RELEASE_CHECK_FIELDS:
            raise ValueError("Invalid published-release check")
        if check["kind"] not in _RELEASE_CHECK_KINDS:
            raise ValueError("Unsupported published-release check kind")
        if any(not isinstance(check[key], str) or not check[key].strip() for key in _RELEASE_CHECK_FIELDS):
            raise ValueError("Published-release check fields must be non-empty text")
        parsed = datetime.fromisoformat(check["checked_at"].replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Published-release check timestamp needs a timezone")
        key = (check["checked_at"], check["kind"], check["evidence_ref"])
        if key in seen_checks:
            raise ValueError("Duplicate published-release check")
        seen_checks.add(key)
    return raw


def build_recovery_denominator(expectations: dict[str, Any], store: EvidenceStore) -> dict[str, Any]:
    """Build a denominator without fabricating capture or source-series identity.

    ``known_versions`` admits byte identities supported by reviewed historical evidence
    even when no stable capture UUID/catalogue record survives. Such an item may be
    ``recoverable_pending`` when exact bytes are available outside the governed store,
    or ``missing`` only under the same positive-absence and completed-search contract as
    captures. It cannot be ``verified`` until real immutable capture provenance exists.

    A known SHA-256 can be checked directly against content-addressed governed storage
    even when historical evidence did not preserve byte size. Successful byte readback
    proves only that the exact bytes are durable; it does not mint a capture identity or
    upgrade the historical version to ``verified``.

    ``published_release_scopes`` is an optional compatibility extension to schema
    version 1. It records what the aggregate public-history ledger says was published
    without adding those digests to raw-source recovery metrics.
    """
    if not isinstance(expectations, dict) or expectations.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported recovery denominator expectations")
    allowed = {
        "schema_version",
        "generated_at",
        "recovery_search_complete",
        "captures",
        "known_versions",
        "published_release_scopes",
    }
    required = allowed - {"published_release_scopes"}
    if set(expectations) - allowed or not required <= set(expectations):
        raise ValueError("Unapproved recovery denominator expectations envelope")
    if not isinstance(expectations["generated_at"], str) or not expectations["generated_at"].strip():
        raise ValueError("Denominator generation timestamp is required")
    if type(expectations["recovery_search_complete"]) is not bool:
        raise ValueError("recovery_search_complete must be boolean")
    if not isinstance(expectations["captures"], list) or not isinstance(expectations["known_versions"], list):
        raise ValueError("captures and known_versions must be lists")
    release_scopes_raw = expectations.get("published_release_scopes", [])
    if not isinstance(release_scopes_raw, list):
        raise ValueError("published_release_scopes must be a list")

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
    known_identities: set[tuple[str, str | None, str]] = set()

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
                "verified_byte_size": row["byte_size"] if row["durable_original_verified"] else None,
            }
        )

    for raw in expectations["known_versions"]:
        expected = _validate_known_version(raw)
        identity = (
            expected["authority_key"],
            expected["source_key"],
            expected["evidence_version_key"],
        )
        if identity in known_identities:
            raise ValueError("Duplicate known-version recovery expectation")
        known_identities.add(identity)
        authorities.add(expected["authority_key"])

        digest = expected["sha256"]
        byte_size = expected["byte_size"]
        durable_original_verified = False
        verified_byte_size = None
        provider_error = None
        verification_blocker = None
        try:
            if byte_size is None:
                recovered = store.read_digest_verified(digest)
                verified_byte_size = len(recovered)
            else:
                store.read_verified({"sha256": digest, "byte_size": byte_size})
                verified_byte_size = byte_size
            durable_original_verified = True
            durable_content.add(digest)
            verification_blocker = "capture_identity_missing"
        except Exception as exc:  # provider failure is uncertainty, never absence
            provider_error = type(exc).__name__
            if byte_size is None:
                verification_blocker = "byte_size_unknown"

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
                "verified_byte_size": verified_byte_size,
                "status": status,
                "durable_original_verified": durable_original_verified,
                "capture_provenance_verified": False,
                "provider_check_error_class": provider_error,
                "verification_blocker": verification_blocker,
            }
        )

    release_scopes: list[dict[str, Any]] = []
    release_ids: set[str] = set()
    release_authorities: set[str] = set()
    for raw in release_scopes_raw:
        scope = _validate_release_scope(raw)
        edition_id = scope["history_edition_id"]
        if edition_id in release_ids:
            raise ValueError("Duplicate published-release scope")
        release_ids.add(edition_id)
        release_authorities.add(scope["authority_key"])
        release_scopes.append(
            {
                **scope,
                "successful_checks": [dict(check) for check in scope["successful_checks"]],
                "evidence_refs": list(scope["evidence_refs"]),
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
            "published_release_scopes": len(release_scopes),
            "published_release_authorities": len(release_authorities),
            "verified": counts["verified"],
            "recoverable_pending": counts["recoverable_pending"],
            "missing": counts["missing"],
            "not_verified": counts["not_verified"],
        },
        "items": rows,
        "published_release_scopes": release_scopes,
    }
