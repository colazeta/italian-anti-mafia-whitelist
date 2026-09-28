"""Recover a historical acquisition from a contemporaneous evidence package.

This migration path is narrower than ordinary acquisition. It accepts only an exact
repository legacy capture manifest plus an exact bounded package whose contemporaneous
manifest agrees with that repository evidence. The recovered bytes then cross the
normal archive-first ContentObject + CaptureCatalogue boundary.

The capture UUID is deterministic from the historical acquisition provenance. It is a
compatibility identity for an acquisition actually recorded at the time; it is never
derived from a hash alone and never uses the current processing clock.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5
from zipfile import BadZipFile, ZipFile

from white_list_archive.acquisition.archive_first import ArchivedCapture, archive_payload
from white_list_archive.storage.evidence import EvidenceStore

_NAMESPACE = uuid5(
    NAMESPACE_URL,
    "https://github.com/colazeta/italian-anti-mafia-whitelist#legacy-capture-recovery-v1",
)
_SHA_FIELDS = ("sha256", "text_sha256", "schema_fingerprint")
_MATCH_FIELDS = (
    "reference_date",
    "page_url",
    "resource_url",
    "final_url",
    "http_status",
    "captured_at",
    "etag",
    "last_modified",
    "sha256",
    "byte_size",
    "content_type",
    "page_count",
    "text_sha256",
    "schema_fingerprint",
)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read legacy repository manifest: {path}") from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _aware_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Legacy capture timestamp is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Legacy capture timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Legacy capture timestamp requires an explicit timezone")
    return parsed


def _validate_repository_manifest(payload: Any, *, source_key: str, package_sha256: str) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Legacy repository manifest must be a JSON object")
    required = {
        "authority_key",
        "source_series_key",
        "reference_date",
        "resource_url",
        "final_url",
        "http_status",
        "captured_at",
        "sha256",
        "byte_size",
        "content_type",
        "workflow_run_id",
        "workflow_artifact_id",
        "workflow_artifact_sha256",
    }
    if required - payload.keys():
        raise ValueError("Legacy repository manifest lacks required capture provenance")
    if payload["source_series_key"] != source_key:
        raise ValueError("Legacy repository manifest belongs to another SourceSeries")
    if payload["workflow_artifact_sha256"] != package_sha256:
        raise ValueError("Legacy repository manifest points to another evidence package")
    if not isinstance(payload["sha256"], str) or len(payload["sha256"]) != 64:
        raise ValueError("Legacy repository manifest has invalid SHA-256")
    if type(payload["byte_size"]) is not int or payload["byte_size"] <= 0:
        raise ValueError("Legacy repository manifest has invalid byte size")
    for field in _SHA_FIELDS:
        value = payload.get(field)
        if value is not None and (not isinstance(value, str) or len(value) != 64):
            raise ValueError(f"Legacy repository manifest has invalid {field}")
    _aware_timestamp(payload["captured_at"])
    return payload


def _package_entry(zf: ZipFile, *, manifest_member: str, digest: str) -> dict:
    try:
        raw = zf.read(manifest_member)
    except KeyError as exc:
        raise ValueError("Recovery package lacks its contemporaneous capture manifest") from exc
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Recovery package capture manifest is invalid JSON") from exc
    if not isinstance(payload, list):
        raise ValueError("Recovery package capture manifest must be a list")
    matches = [row for row in payload if isinstance(row, dict) and row.get("sha256") == digest]
    if len(matches) != 1:
        raise ValueError("Recovery package must contain exactly one matching capture manifest row")
    return matches[0]


def legacy_capture_id(*, source_key: str, manifest: dict) -> str:
    """Return the stable compatibility UUID for one evidenced historical acquisition."""
    if not isinstance(source_key, str) or not source_key.strip():
        raise ValueError("Legacy capture SourceSeries is required")
    captured_at = manifest.get("captured_at")
    _aware_timestamp(captured_at)
    identity = {
        "source_key": source_key,
        "captured_at": captured_at,
        "sha256": manifest.get("sha256"),
        "resource_url": manifest.get("resource_url"),
        "resolved_url": manifest.get("final_url"),
        "reference_date": manifest.get("reference_date"),
    }
    required_values = (
        identity["source_key"],
        identity["captured_at"],
        identity["sha256"],
        identity["resource_url"],
        identity["resolved_url"],
    )
    if any(not isinstance(value, str) or not value for value in required_values):
        raise ValueError("Legacy capture provenance is incomplete for deterministic identity")
    seed = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(uuid5(_NAMESPACE, seed))


def recover_legacy_capture_from_package(
    *,
    package_path: Path,
    package_sha256: str,
    package_manifest_member: str,
    content_member: str,
    repository_manifest_path: Path,
    source_key: str,
    store: EvidenceStore,
    work_dir: Path,
) -> ArchivedCapture:
    """Verify one historical package member and persist it as the same acquisition."""
    if not isinstance(package_sha256, str) or len(package_sha256) != 64:
        raise ValueError("Recovery package SHA-256 must be a 64-character digest")
    if _sha256_file(package_path) != package_sha256:
        raise ValueError("Recovery package SHA-256 does not match reviewed evidence")

    repository_manifest = _validate_repository_manifest(
        _load_json(repository_manifest_path),
        source_key=source_key,
        package_sha256=package_sha256,
    )

    try:
        with ZipFile(package_path) as zf:
            package_manifest = _package_entry(
                zf,
                manifest_member=package_manifest_member,
                digest=repository_manifest["sha256"],
            )
            for field in _MATCH_FIELDS:
                if package_manifest.get(field) != repository_manifest.get(field):
                    raise ValueError(
                        f"Recovery package provenance disagrees with repository manifest: {field}"
                    )
            try:
                data = zf.read(content_member)
            except KeyError as exc:
                raise ValueError("Recovery package lacks the reviewed original member") from exc
    except BadZipFile as exc:
        raise ValueError("Recovery package is not a valid ZIP archive") from exc

    if len(data) != repository_manifest["byte_size"]:
        raise ValueError("Recovery package member byte size differs from reviewed evidence")
    if hashlib.sha256(data).hexdigest() != repository_manifest["sha256"]:
        raise ValueError("Recovery package member SHA-256 differs from reviewed evidence")

    return archive_payload(
        data=data,
        source_key=source_key,
        resource_url=repository_manifest["resource_url"],
        reference_date=repository_manifest.get("reference_date"),
        content_type=repository_manifest["content_type"],
        store=store,
        work_dir=work_dir,
        captured_at=_aware_timestamp(repository_manifest["captured_at"]),
        capture_id=legacy_capture_id(source_key=source_key, manifest=repository_manifest),
        resolved_url=repository_manifest.get("final_url") or repository_manifest["resource_url"],
        http_status=repository_manifest.get("http_status"),
        etag=repository_manifest.get("etag"),
        last_modified=repository_manifest.get("last_modified"),
        origin_type=repository_manifest.get("origin_type"),
    )
