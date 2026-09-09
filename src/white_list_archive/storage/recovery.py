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


def public_recovery_receipt(receipt: dict) -> dict:
    """Return the deliberately redacted receipt safe for a public repository artifact.

    GitHub Actions artifacts attached to a public repository must be treated as public
    evidence. Provider coordinates, namespace fingerprints, policy locators and the
    reviewed independence statement therefore remain out of the uploaded receipt. A
    digest binds the run to the reviewed independence record without publishing it.
    """
    required = (
        "schema_version",
        "sha256",
        "byte_size",
        "primary_store_fingerprint",
        "recovery_store_fingerprint",
        "independence_evidence",
        "backup_created",
        "restore_verified_at",
    )
    missing = [name for name in required if name not in receipt]
    if missing:
        raise ValueError("Incomplete recovery receipt: " + ", ".join(missing))
    if receipt["primary_store_fingerprint"] == receipt["recovery_store_fingerprint"]:
        raise ValueError("Cannot publish a receipt for a non-distinct recovery target")
    independence_evidence = receipt["independence_evidence"]
    if not isinstance(independence_evidence, str) or not independence_evidence.strip():
        raise ValueError("Recovery receipt lacks reviewed independence evidence")
    return {
        "schema_version": receipt["schema_version"],
        "sha256": receipt["sha256"],
        "byte_size": receipt["byte_size"],
        "backup_created": bool(receipt["backup_created"]),
        "recovery_target_distinct_from_primary": True,
        "independence_record_sha256": hashlib.sha256(
            independence_evidence.encode("utf-8")
        ).hexdigest(),
        "clean_restore_verified": True,
        "restore_verified_at": receipt["restore_verified_at"],
    }


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
