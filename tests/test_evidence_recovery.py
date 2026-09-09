import hashlib
import io

import pytest

from white_list_archive.storage.evidence import EvidenceStore, StoreConfig
from white_list_archive.storage.recovery import (
    backup_and_restore_test,
    store_fingerprint,
    validate_recovery_target,
)

DATA = b"%PDF-synthetic-recovery-test"
MANIFEST = {
    "sha256": hashlib.sha256(DATA).hexdigest(),
    "byte_size": len(DATA),
    "content_type": "application/pdf",
    "resource_url": "https://official.example.invalid/source.pdf",
    "captured_at": "2026-09-06T12:00:00Z",
    "reference_date": "2026-08-03",
}
PRIMARY = StoreConfig(
    "primary-evidence",
    "https://primary.example.invalid",
    "eu-west-1",
    "primary-policy",
)
RECOVERY = StoreConfig(
    "recovery-evidence",
    "https://recovery.example.invalid",
    "eu-west-1",
    "recovery-policy",
)


class Conflict(Exception):
    response = {"Error": {"Code": "PreconditionFailed"}}


class MemoryS3:
    """Protocol double only; never evidence of real backup independence."""

    def __init__(self):
        self.objects = {}
        self.writes = 0
        self.corrupt_read = False

    def put_object(self, **kwargs):
        assert kwargs["IfNoneMatch"] == "*"
        key = kwargs["Key"]
        if key in self.objects:
            raise Conflict()
        self.objects[key] = kwargs["Body"]
        self.writes += 1

    def get_object(self, **kwargs):
        value = self.objects[kwargs["Key"]]
        return {"Body": io.BytesIO(b"corrupt" if self.corrupt_read else value)}


def _source(tmp_path):
    path = tmp_path / "primary-export.bin"
    path.write_bytes(DATA)
    return path


def test_recovery_target_requires_distinct_namespace_and_evidence():
    primary_fingerprint = store_fingerprint(PRIMARY)
    assert primary_fingerprint != store_fingerprint(RECOVERY)
    with pytest.raises(ValueError, match="independence"):
        validate_recovery_target(primary_fingerprint, RECOVERY, "")
    with pytest.raises(ValueError, match="must not be the primary"):
        validate_recovery_target(primary_fingerprint, PRIMARY, "reviewed-independence-record")
    with pytest.raises(ValueError, match="fingerprint"):
        validate_recovery_target("not-a-digest", RECOVERY, "reviewed-independence-record")


def test_backup_is_idempotent_and_clean_restore_is_reverified(tmp_path):
    client = MemoryS3()
    store = EvidenceStore(client, RECOVERY)
    primary_fingerprint = store_fingerprint(PRIMARY)
    source = _source(tmp_path)

    first_restore = tmp_path / "restore-1" / "evidence.bin"
    first = backup_and_restore_test(
        source_path=source,
        manifest=MANIFEST,
        recovery_store=store,
        restore_path=first_restore,
        primary_store_fingerprint=primary_fingerprint,
        independence_evidence="reviewed-independence-record",
    )
    assert first["backup_created"] is True
    assert first_restore.read_bytes() == DATA
    assert first["primary_store_fingerprint"] == primary_fingerprint
    assert first["recovery_store_fingerprint"] == store_fingerprint(RECOVERY)

    second_restore = tmp_path / "restore-2" / "evidence.bin"
    second = backup_and_restore_test(
        source_path=source,
        manifest=MANIFEST,
        recovery_store=store,
        restore_path=second_restore,
        primary_store_fingerprint=primary_fingerprint,
        independence_evidence="reviewed-independence-record",
    )
    assert second["backup_created"] is False
    assert client.writes == 1
    assert second_restore.read_bytes() == DATA


def test_corrupt_recovery_copy_fails_before_clean_restore(tmp_path):
    client = MemoryS3()
    store = EvidenceStore(client, RECOVERY)
    source = _source(tmp_path)
    store.archive(source, MANIFEST)
    client.corrupt_read = True
    restore = tmp_path / "restore" / "evidence.bin"
    with pytest.raises(ValueError, match="Stored evidence"):
        backup_and_restore_test(
            source_path=source,
            manifest=MANIFEST,
            recovery_store=store,
            restore_path=restore,
            primary_store_fingerprint=store_fingerprint(PRIMARY),
            independence_evidence="reviewed-independence-record",
        )
    assert not restore.exists()


def test_existing_restore_path_fails_before_any_recovery_write(tmp_path):
    client = MemoryS3()
    store = EvidenceStore(client, RECOVERY)
    source = _source(tmp_path)
    restore = tmp_path / "restore.bin"
    restore.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        backup_and_restore_test(
            source_path=source,
            manifest=MANIFEST,
            recovery_store=store,
            restore_path=restore,
            primary_store_fingerprint=store_fingerprint(PRIMARY),
            independence_evidence="reviewed-independence-record",
        )
    assert restore.read_bytes() == b"existing"
    assert client.writes == 0
