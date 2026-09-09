"""Copy verified evidence to an independent S3-compatible recovery store and restore it."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .evidence import EvidenceStore, StoreConfig, object_key


@dataclass(frozen=True)
class RecoveryConfig:
    primary: StoreConfig
    backup: StoreConfig
    primary_access_key_id: str
    primary_secret_access_key: str
    backup_access_key_id: str
    backup_secret_access_key: str
    primary_session_token: str | None = None
    backup_session_token: str | None = None

    def __post_init__(self) -> None:
        if (self.primary.endpoint.rstrip('/'), self.primary.bucket) == (
            self.backup.endpoint.rstrip('/'), self.backup.bucket
        ):
            raise ValueError("Recovery store must be outside the primary evidence namespace")
        required = (
            self.primary_access_key_id,
            self.primary_secret_access_key,
            self.backup_access_key_id,
            self.backup_secret_access_key,
        )
        if any(not value.strip() for value in required):
            raise ValueError("Primary read and backup read/write credentials are required")

    @classmethod
    def from_env(cls) -> "RecoveryConfig":
        def store(prefix: str) -> StoreConfig:
            names = (
                f"{prefix}_BUCKET",
                f"{prefix}_ENDPOINT",
                f"{prefix}_REGION",
                f"{prefix}_POLICY_EVIDENCE",
            )
            if any(not os.environ.get(name) for name in names):
                raise ValueError(f"Configure {', '.join(names)}")
            return StoreConfig(*(os.environ[name] for name in names))

        names = (
            "PRIMARY_EVIDENCE_ACCESS_KEY_ID",
            "PRIMARY_EVIDENCE_SECRET_ACCESS_KEY",
            "BACKUP_EVIDENCE_ACCESS_KEY_ID",
            "BACKUP_EVIDENCE_SECRET_ACCESS_KEY",
        )
        if any(not os.environ.get(name) for name in names):
            raise ValueError("Configure separate primary-read and backup read/write credentials")
        return cls(
            primary=store("PRIMARY_EVIDENCE"),
            backup=store("BACKUP_EVIDENCE"),
            primary_access_key_id=os.environ[names[0]],
            primary_secret_access_key=os.environ[names[1]],
            backup_access_key_id=os.environ[names[2]],
            backup_secret_access_key=os.environ[names[3]],
            primary_session_token=os.environ.get("PRIMARY_EVIDENCE_SESSION_TOKEN"),
            backup_session_token=os.environ.get("BACKUP_EVIDENCE_SESSION_TOKEN"),
        )


def client_for(config: StoreConfig, *, access_key_id: str, secret_access_key: str, session_token: str | None = None):
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint,
        region_name=config.region,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        aws_session_token=session_token,
        config=Config(
            signature_version="s3v4",
            connect_timeout=10,
            read_timeout=60,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def _put_backup(store: EvidenceStore, manifest: dict[str, Any], data: bytes) -> bool:
    key = object_key(manifest)
    created = True
    try:
        store.client.put_object(
            Bucket=store.config.bucket,
            Key=key,
            Body=data,
            ContentType=manifest["content_type"],
            IfNoneMatch="*",
            Metadata={"sha256": manifest["sha256"]},
        )
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        code = str(code) if code is not None else None
        if code not in ("PreconditionFailed", "412", "ObjectLockedByBucketPolicy", "10069"):
            raise
        created = False
    store.read_verified(manifest)
    return created


def backup_and_restore(
    *,
    manifest: dict[str, Any],
    restore_file: Path,
    primary_store: EvidenceStore,
    backup_store: EvidenceStore,
) -> dict[str, Any]:
    """Verify primary, copy idempotently, verify backup, then restore into a clean path."""
    if restore_file.exists():
        raise FileExistsError(f"Restore target already exists: {restore_file}")
    data = primary_store.read_verified(manifest)
    created = _put_backup(backup_store, manifest, data)
    recovered = backup_store.read_verified(manifest)
    restore_file.parent.mkdir(parents=True, exist_ok=True)
    with restore_file.open("xb") as handle:
        handle.write(recovered)
    restored = restore_file.read_bytes()
    restored_sha = hashlib.sha256(restored).hexdigest()
    if len(restored) != manifest["byte_size"] or restored_sha != manifest["sha256"]:
        raise ValueError("Clean restore failed independent size/SHA-256 verification")
    key = object_key(manifest)
    return {
        "schema_version": 1,
        "sha256": manifest["sha256"],
        "byte_size": manifest["byte_size"],
        "primary_uri": f"{primary_store.config.endpoint.rstrip('/')}/{primary_store.config.bucket}/{key}",
        "backup_uri": f"{backup_store.config.endpoint.rstrip('/')}/{backup_store.config.bucket}/{key}",
        "backup_created": created,
        "primary_policy_evidence": primary_store.config.policy_evidence,
        "backup_policy_evidence": backup_store.config.policy_evidence,
        "restore_file": str(restore_file),
        "restore_sha256": restored_sha,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "restore_verified": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--restore-file", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists():
        parser.error("Recovery receipt must be a new path")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    object_key(manifest)
    config = RecoveryConfig.from_env()
    primary = EvidenceStore(
        client_for(
            config.primary,
            access_key_id=config.primary_access_key_id,
            secret_access_key=config.primary_secret_access_key,
            session_token=config.primary_session_token,
        ),
        config.primary,
    )
    backup = EvidenceStore(
        client_for(
            config.backup,
            access_key_id=config.backup_access_key_id,
            secret_access_key=config.backup_secret_access_key,
            session_token=config.backup_session_token,
        ),
        config.backup,
    )
    receipt = backup_and_restore(
        manifest=manifest,
        restore_file=args.restore_file,
        primary_store=primary,
        backup_store=backup,
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2)
        handle.write("\n")
    print("Independent backup and clean restore verified; receipt remains private.")


if __name__ == "__main__":
    main()
