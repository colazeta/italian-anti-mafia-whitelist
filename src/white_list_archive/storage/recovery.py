"""Provider-neutral backup and clean-restore verification for private evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re

from white_list_archive.storage.evidence import EvidenceStore, StoreConfig


def store_fingerprint(config: StoreConfig) -> str:
    """Return a non-secret fingerprint for one exact object-store namespace."""
    material = f"{config.endpoint.rstrip('/')}\0{config.bucket}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def validate_recovery_target(
    primary_store_fingerprint: str,
    recovery_config: StoreConfig,
    independence_evidence: str,
) -> str:
    """Refuse the primary namespace and require explicit independence evidence.

    The fingerprint check proves only that the exact endpoint+bucket namespace differs.
    The evidence locator is an operator-reviewed statement about the stronger
    organisational/provider independence requirement; code must not infer that merely
    from a different bucket name.
    """
    if not re.fullmatch(r"[0-9a-f]{64}", primary_store_fingerprint):
        raise ValueError("Invalid primary evidence-store fingerprint")
    if not independence_evidence.strip():
        raise ValueError("Reviewed recovery-independence evidence is required")
    recovery_fingerprint = store_fingerprint(recovery_config)
    if recovery_fingerprint == primary_store_fingerprint:
        raise ValueError("Recovery target must not be the primary evidence namespace")
    return recovery_fingerprint


def backup_and_restore_test(
    *,
    source_path: Path,
    manifest: dict,
    recovery_store: EvidenceStore,
    restore_path: Path,
    primary_store_fingerprint: str,
    independence_evidence: str,
) -> dict:
    """Create/verify a recovery copy and restore exact bytes into a clean path.

    `source_path` is expected to be a short-lived verified export from the primary
    store. `EvidenceStore.archive` re-verifies those local bytes against the frozen
    manifest before writing, then performs a full destination GET/SHA-256 check.
    The clean restore is read back and hashed again. Existing restore paths are never
    overwritten, and are rejected before any destination write is attempted.
    """
    recovery_fingerprint = validate_recovery_target(
        primary_store_fingerprint,
        recovery_store.config,
        independence_evidence,
    )
    if restore_path.exists():
        raise FileExistsError(f"Clean restore path already exists: {restore_path}")

    backup_receipt = recovery_store.archive(source_path, manifest)
    recovered = recovery_store.read_verified(manifest)

    restore_path.parent.mkdir(parents=True, exist_ok=True)
    with restore_path.open("xb") as handle:
        handle.write(recovered)
    with restore_path.open("rb") as handle:
        restored = handle.read(manifest["byte_size"] + 1)
    if (
        len(restored) != manifest["byte_size"]
        or hashlib.sha256(restored).hexdigest() != manifest["sha256"]
    ):
        raise ValueError("Clean restore failed independent size/SHA-256 verification")

    return {
        "schema_version": 1,
        "sha256": manifest["sha256"],
        "byte_size": manifest["byte_size"],
        "primary_store_fingerprint": primary_store_fingerprint,
        "recovery_store_fingerprint": recovery_fingerprint,
        "independence_evidence": independence_evidence,
        "backup_created": bool(backup_receipt["created"]),
        "backup_storage_uri": backup_receipt["storage_uri"],
        "backup_policy_evidence": backup_receipt["policy_evidence"],
        "restore_file_name": restore_path.name,
        "restore_verified_at": datetime.now(timezone.utc).isoformat(),
    }
