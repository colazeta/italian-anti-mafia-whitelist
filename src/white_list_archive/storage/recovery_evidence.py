"""Reconcile repository evidence into conservative recovery-denominator inputs.

This module does not inspect the governed object store and therefore never assigns a
recovery outcome. It only builds the repository-supported denominator candidates that
can later be checked against durable storage, recovery packages and other catalogues.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

_SHA256_RE = re.compile(r"[a-f0-9]{64}")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _known_version(*, authority_key: str, source_key: str | None,
                   evidence_version_key: str, sha256: str, byte_size: int | None,
                   evidence_refs: list[str]) -> dict[str, Any]:
    return {
        "authority_key": authority_key,
        "source_key": source_key,
        "evidence_version_key": evidence_version_key,
        "sha256": sha256,
        "byte_size": byte_size,
        "evidence_refs": list(dict.fromkeys(evidence_refs)),
        "recovery_paths": [],
        "durable_absence_confirmed": False,
    }


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.fullmatch(value))


def _legacy_manifest_candidate(path: Path, captures_root: Path) -> dict[str, Any] | None:
    """Return a known version only for a source-capture-like legacy manifest.

    Diff/profile JSON files in the capture tree are analytical products, not source
    originals, and therefore do not enter the source-version denominator.
    """
    try:
        payload = _load_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    required = ("authority_key", "sha256", "byte_size", "captured_at", "resource_url")
    if any(key not in payload for key in required):
        return None
    authority = payload["authority_key"]
    digest = payload["sha256"]
    byte_size = payload["byte_size"]
    captured_at = payload["captured_at"]
    if (not isinstance(authority, str) or not authority.strip() or not _valid_sha(digest) or
            type(byte_size) is not int or byte_size <= 0 or
            not isinstance(captured_at, str) or not captured_at.strip()):
        return None
    source_key = payload.get("source_series_key")
    if source_key is not None and (not isinstance(source_key, str) or not source_key.strip()):
        source_key = None
    relative = path.relative_to(captures_root.parent).as_posix()
    return _known_version(
        authority_key=authority,
        source_key=source_key,
        evidence_version_key=f"legacy-manifest:{relative}",
        sha256=digest,
        byte_size=byte_size,
        evidence_refs=[relative],
    )


def build_repository_recovery_expectations(*, monitoring_path: Path, captures_root: Path,
                                           generated_at: str) -> dict[str, Any]:
    """Build repository-supported recovery expectations without inventing provenance.

    Hashed monitoring checks are retained as separate observations even when they share
    bytes. Authority-level ``known_content_sha256`` entries are lower-specificity
    evidence and are added only when that authority/hash pair is not already represented
    by a timestamped monitoring check or a legacy source manifest. Legacy manifests keep
    their observed capture timestamp in their evidence key but remain ``known_version``
    items because they predate stable archive-first capture identity.
    """
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise ValueError("generated_at is required")
    monitoring = _load_json(monitoring_path)
    if not isinstance(monitoring, dict):
        raise ValueError("Monitoring ledger must be a mapping")

    known_versions: list[dict[str, Any]] = []
    represented_authority_hashes: set[tuple[str, str]] = set()

    checks = monitoring.get("checks", [])
    if not isinstance(checks, list):
        raise ValueError("Monitoring checks must be a list")
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            raise ValueError("Monitoring check must be a mapping")
        digest = check.get("content_sha256")
        if digest is None:
            continue
        if not _valid_sha(digest):
            raise ValueError("Monitoring check contains invalid content SHA-256")
        authority = check.get("authority_key")
        observed_at = check.get("at")
        if (not isinstance(authority, str) or not authority.strip() or
                not isinstance(observed_at, str) or not observed_at.strip()):
            raise ValueError("Hashed monitoring check requires authority and timestamp")
        evidence = check.get("evidence")
        refs = [f"{monitoring_path.as_posix()}#check-{index}"]
        if isinstance(evidence, str) and evidence.strip():
            refs.insert(0, evidence)
        known_versions.append(
            _known_version(
                authority_key=authority,
                source_key=None,
                evidence_version_key=f"monitoring-check:{observed_at}:{digest}",
                sha256=digest,
                byte_size=None,
                evidence_refs=refs,
            )
        )
        represented_authority_hashes.add((authority, digest))

    if captures_root.exists():
        for path in sorted(captures_root.rglob("*.json")):
            candidate = _legacy_manifest_candidate(path, captures_root)
            if candidate is None:
                continue
            known_versions.append(candidate)
            represented_authority_hashes.add((candidate["authority_key"], candidate["sha256"]))

    prefectures = monitoring.get("prefectures", [])
    if not isinstance(prefectures, list):
        raise ValueError("Monitoring prefectures must be a list")
    for index, row in enumerate(prefectures):
        if not isinstance(row, dict):
            raise ValueError("Monitoring prefecture must be a mapping")
        authority = row.get("authority_key")
        hashes = row.get("known_content_sha256", [])
        if not isinstance(authority, str) or not authority.strip():
            raise ValueError("Monitoring prefecture requires authority_key")
        if hashes is None:
            hashes = []
        if not isinstance(hashes, list):
            raise ValueError("known_content_sha256 must be a list")
        evidence = row.get("evidence", [])
        if not isinstance(evidence, list) or any(not isinstance(ref, str) for ref in evidence):
            raise ValueError("Monitoring prefecture evidence must be a list of strings")
        for digest in hashes:
            if not _valid_sha(digest):
                raise ValueError("Monitoring prefecture contains invalid known SHA-256")
            if (authority, digest) in represented_authority_hashes:
                continue
            known_versions.append(
                _known_version(
                    authority_key=authority,
                    source_key=None,
                    evidence_version_key=f"coverage-known:{digest}",
                    sha256=digest,
                    byte_size=None,
                    evidence_refs=[*evidence, f"{monitoring_path.as_posix()}#prefecture-{index}"],
                )
            )
            represented_authority_hashes.add((authority, digest))

    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "recovery_search_complete": False,
        "captures": [],
        "known_versions": known_versions,
    }
