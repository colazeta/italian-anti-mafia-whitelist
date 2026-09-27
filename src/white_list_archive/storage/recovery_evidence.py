"""Reconcile repository evidence into conservative recovery-denominator inputs.

This module does not inspect the governed object store and therefore never assigns a
recovery outcome. It only builds repository-supported recovery candidates and preserves
public-release evidence as a separate aggregate layer.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

_SHA256_RE = re.compile(r"[a-f0-9]{64}")
_PUBLIC_HISTORY_FIELDS = {"version", "editions", "checks", "comparisons"}
_PUBLIC_EDITION_REQUIRED = {
    "id",
    "source_key",
    "authority_key",
    "reference_date",
    "reference_date_raw",
    "document_sha256",
    "parser_signature",
    "evidence",
}
_PUBLIC_CHECK_FIELDS = {"edition_id", "checked_at", "kind"}
_PUBLIC_CHECK_KINDS = {"approved_document_verification", "historical_capture"}


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


def _repo_ref(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("Recovery evidence path must be inside repository_root") from exc


def _canonical_time(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Public-history check timestamp is required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Public-history check timestamp needs a timezone")
    return value


def _legacy_manifest_candidate(path: Path, *, repository_root: Path) -> dict[str, Any] | None:
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
    relative = _repo_ref(path, repository_root)
    return _known_version(
        authority_key=authority,
        source_key=source_key,
        evidence_version_key=f"legacy-manifest:{relative}",
        sha256=digest,
        byte_size=byte_size,
        evidence_refs=[relative],
    )


def _public_history_release_scopes(path: Path, *, repository_root: Path) -> list[dict[str, Any]]:
    """Return aggregate publication scopes without promoting them to raw source versions.

    ``public_history.json`` deliberately loses the distinction between a scalar source
    capture identity and a bundle-derived digest. Its document digest is therefore useful
    publication evidence, but it cannot by itself prove possession of one raw
    ``ContentObject`` or mint a historical ``SourceCapture``.
    """
    payload = _load_json(path)
    if not isinstance(payload, dict) or set(payload) != _PUBLIC_HISTORY_FIELDS or payload.get("version") != 1:
        raise ValueError("Unsupported public-history envelope")
    editions = payload["editions"]
    checks = payload["checks"]
    if not isinstance(editions, list) or not isinstance(checks, list):
        raise ValueError("Public-history editions and checks must be lists")

    history_ref = _repo_ref(path, repository_root)
    edition_ids: set[str] = set()
    for edition in editions:
        if not isinstance(edition, dict) or not _PUBLIC_EDITION_REQUIRED <= set(edition):
            raise ValueError("Public-history edition is missing required fields")
        edition_id = edition["id"]
        if not _valid_sha(edition_id) or edition_id in edition_ids:
            raise ValueError("Public-history edition identity must be unique SHA-256")
        edition_ids.add(edition_id)
        for key in ("authority_key", "source_key", "parser_signature", "reference_date_raw"):
            if not isinstance(edition[key], str):
                raise ValueError(f"Public-history {key} must be text")
        if not edition["authority_key"].strip() or not edition["source_key"].strip() or not edition["parser_signature"].strip():
            raise ValueError("Public-history authority, source and parser signature are required")
        if edition["reference_date"] is not None and not isinstance(edition["reference_date"], str):
            raise ValueError("Public-history reference_date must be text or null")
        if not _valid_sha(edition["document_sha256"]):
            raise ValueError("Public-history document digest must be SHA-256")
        evidence = edition["evidence"]
        if not isinstance(evidence, list) or any(not isinstance(ref, str) for ref in evidence):
            raise ValueError("Public-history edition evidence must be a list of strings")

    checks_by_edition: dict[str, list[dict[str, str]]] = {edition_id: [] for edition_id in edition_ids}
    for index, check in enumerate(checks):
        if not isinstance(check, dict) or set(check) != _PUBLIC_CHECK_FIELDS:
            raise ValueError("Invalid public-history check")
        edition_id = check["edition_id"]
        if edition_id not in edition_ids:
            raise ValueError("Public-history check references an unknown edition")
        if check["kind"] not in _PUBLIC_CHECK_KINDS:
            raise ValueError("Unsupported public-history check kind")
        checked_at = _canonical_time(check["checked_at"])
        checks_by_edition[edition_id].append(
            {
                "checked_at": checked_at,
                "kind": check["kind"],
                "evidence_ref": f"{history_ref}#check-{index}",
            }
        )

    scopes: list[dict[str, Any]] = []
    for edition in editions:
        edition_id = edition["id"]
        scopes.append(
            {
                "history_edition_id": edition_id,
                "authority_key": edition["authority_key"],
                "source_key": edition["source_key"],
                "document_digest": edition["document_sha256"],
                "digest_semantics": "public_history_document_digest",
                "raw_content_object_identity_established": False,
                "parser_signature": edition["parser_signature"],
                "reference_date": edition["reference_date"],
                "reference_date_raw": edition["reference_date_raw"],
                "successful_checks": checks_by_edition[edition_id],
                "evidence_refs": list(
                    dict.fromkeys(
                        [*edition["evidence"], f"{history_ref}#edition-{edition_id}"]
                    )
                ),
            }
        )
    return scopes


def build_repository_recovery_expectations(*, repository_root: Path, monitoring_path: Path,
                                           captures_root: Path, generated_at: str,
                                           public_history_path: Path | None = None) -> dict[str, Any]:
    """Build repository-supported recovery expectations without inventing provenance.

    Hashed monitoring checks are retained as separate observations even when they share
    bytes or the same timestamp. Authority-level ``known_content_sha256`` entries are
    lower-specificity evidence and are added only when that authority/hash pair is not
    already represented by a timestamped monitoring check or a legacy source manifest.
    Legacy manifests remain ``known_version`` items because they predate stable
    archive-first capture identity.

    Public history is optional and remains a separate aggregate publication layer. Its
    edition digests never become ``known_version`` rows or raw ``ContentObject``
    identities. Evidence references are always repository-relative.
    """
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise ValueError("generated_at is required")
    repository_root = repository_root.resolve()
    monitoring_path = monitoring_path.resolve()
    captures_root = captures_root.resolve()
    monitoring_ref = _repo_ref(monitoring_path, repository_root)
    _repo_ref(captures_root, repository_root)

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
        refs = [f"{monitoring_ref}#check-{index}"]
        if isinstance(evidence, str) and evidence.strip():
            refs.insert(0, evidence)
        known_versions.append(
            _known_version(
                authority_key=authority,
                source_key=None,
                evidence_version_key=f"monitoring-check:{index}:{observed_at}:{digest}",
                sha256=digest,
                byte_size=None,
                evidence_refs=refs,
            )
        )
        represented_authority_hashes.add((authority, digest))

    if captures_root.exists():
        for path in sorted(captures_root.rglob("*.json")):
            candidate = _legacy_manifest_candidate(path, repository_root=repository_root)
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
                    evidence_refs=[*evidence, f"{monitoring_ref}#prefecture-{index}"],
                )
            )
            represented_authority_hashes.add((authority, digest))

    published_release_scopes: list[dict[str, Any]] = []
    if public_history_path is not None:
        public_history_path = public_history_path.resolve()
        _repo_ref(public_history_path, repository_root)
        published_release_scopes = _public_history_release_scopes(
            public_history_path,
            repository_root=repository_root,
        )

    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "recovery_search_complete": False,
        "captures": [],
        "known_versions": known_versions,
        "published_release_scopes": published_release_scopes,
    }
