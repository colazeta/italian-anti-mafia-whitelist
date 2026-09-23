from __future__ import annotations

from datetime import datetime, timezone
import io
from pathlib import Path

from white_list_archive.acquisition.archive_first import archive_payload
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig
from white_list_archive.storage.recovery_denominator import build_recovery_denominator


class ExistingObject(Exception):
    def __init__(self):
        self.response = {"Error": {"Code": "PreconditionFailed"}}


class MemoryClient:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        assert Bucket == "archive-bucket"
        if Key in self.objects:
            raise ExistingObject()
        self.objects[Key] = bytes(Body)
        return {}

    def get_object(self, *, Bucket, Key):
        assert Bucket == "archive-bucket"
        if Key not in self.objects:
            raise KeyError(Key)
        return {"Body": io.BytesIO(self.objects[Key])}


def store(client: MemoryClient | None = None) -> EvidenceStore:
    return EvidenceStore(
        client or MemoryClient(),
        StoreConfig(
            bucket="archive-bucket",
            endpoint="https://evidence.example",
            region="auto",
            policy_evidence="internal-policy-record",
        ),
    )


def archived(tmp_path: Path, evidence: EvidenceStore, *, capture_id: str, data: bytes):
    return archive_payload(
        data=data,
        source_key="mutable-listed",
        resource_url="https://prefettura.example/current.pdf",
        reference_date=None,
        content_type="application/pdf",
        store=evidence,
        work_dir=tmp_path,
        captured_at=datetime(2026, 9, 22, 19, 0, tzinfo=timezone.utc),
        capture_id=capture_id,
        http_status=200,
    )


def capture_expectation(result):
    return {
        "authority_key": "mutable",
        "capture": result.manifest,
        "catalogue": result.catalogue_receipt,
        "recovery_paths": [],
        "durable_absence_confirmed": False,
    }


def known_version(*, sha256: str, byte_size: int | None, recovery_paths=None,
                  durable_absence_confirmed=False, version_key="transition-note-1",
                  source_key="legacy-listed"):
    return {
        "authority_key": "legacy",
        "source_key": source_key,
        "evidence_version_key": version_key,
        "sha256": sha256,
        "byte_size": byte_size,
        "evidence_refs": ["docs/sources/legacy-transition-note.md#version-1"],
        "recovery_paths": recovery_paths or [],
        "durable_absence_confirmed": durable_absence_confirmed,
    }


def envelope(*, captures=None, known_versions=None, recovery_search_complete=False):
    return {
        "schema_version": 1,
        "generated_at": "2026-09-23T00:15:00+00:00",
        "recovery_search_complete": recovery_search_complete,
        "captures": captures or [],
        "known_versions": known_versions or [],
    }


def test_known_hash_without_capture_identity_enters_denominator_not_verified():
    item = known_version(sha256="a" * 64, byte_size=None)
    inventory = build_recovery_denominator(envelope(known_versions=[item]), store())

    row = inventory["items"][0]
    assert row["identity_kind"] == "known_version"
    assert row["capture_id"] is None
    assert row["status"] == "not_verified"
    assert row["verification_blocker"] == "byte_size_unknown"
    assert inventory["metrics"] == {
        "source_authorities_covered": 1,
        "denominator_items": 1,
        "captures_expected": 0,
        "known_versions_without_capture_identity": 1,
        "distinct_content_objects_known": 1,
        "durably_retrievable_content_objects": 0,
        "captures_with_verified_provenance": 0,
        "verified": 0,
        "recoverable_pending": 0,
        "missing": 0,
        "not_verified": 1,
    }


def test_authority_level_evidence_does_not_invent_source_series():
    item = known_version(
        sha256="1" * 64,
        byte_size=None,
        source_key=None,
        version_key="monitoring-check-2026-09-21T10:32:25Z",
    )
    inventory = build_recovery_denominator(envelope(known_versions=[item]), store())
    row = inventory["items"][0]
    assert row["source_key"] is None
    assert row["status"] == "not_verified"


def test_exact_recovery_package_for_legacy_version_is_recoverable_pending(tmp_path):
    data = b"known historical bytes"
    path = tmp_path / "recoverable.bin"
    path.write_bytes(data)
    import hashlib
    item = known_version(
        sha256=hashlib.sha256(data).hexdigest(),
        byte_size=len(data),
        recovery_paths=[str(path)],
    )

    inventory = build_recovery_denominator(envelope(known_versions=[item]), store())
    row = inventory["items"][0]
    assert row["status"] == "recoverable_pending"
    assert row["durable_original_verified"] is False
    assert row["capture_provenance_verified"] is False


def test_durable_legacy_bytes_stay_not_verified_without_capture_provenance(tmp_path):
    evidence = store()
    result = archived(
        tmp_path / "capture",
        evidence,
        capture_id="61616161-6161-4161-8161-616161616161",
        data=b"same durable bytes",
    )
    legacy = known_version(
        sha256=result.manifest["sha256"],
        byte_size=result.manifest["byte_size"],
        version_key="historical-note-without-capture-id",
    )

    inventory = build_recovery_denominator(
        envelope(captures=[capture_expectation(result)], known_versions=[legacy]),
        evidence,
    )
    capture_row, legacy_row = inventory["items"]
    assert capture_row["status"] == "verified"
    assert legacy_row["status"] == "not_verified"
    assert legacy_row["durable_original_verified"] is True
    assert legacy_row["capture_provenance_verified"] is False
    assert inventory["metrics"]["denominator_items"] == 2
    assert inventory["metrics"]["distinct_content_objects_known"] == 1
    assert inventory["metrics"]["durably_retrievable_content_objects"] == 1
    assert inventory["metrics"]["verified"] == 1
    assert inventory["metrics"]["not_verified"] == 1


def test_missing_requires_known_size_positive_absence_and_completed_search():
    sized = known_version(sha256="b" * 64, byte_size=123, durable_absence_confirmed=True)
    incomplete = build_recovery_denominator(
        envelope(known_versions=[sized], recovery_search_complete=False),
        store(),
    )
    assert incomplete["items"][0]["status"] == "not_verified"

    complete = build_recovery_denominator(
        envelope(known_versions=[sized], recovery_search_complete=True),
        store(),
    )
    assert complete["items"][0]["status"] == "missing"

    unknown_size = known_version(
        sha256="c" * 64,
        byte_size=None,
        durable_absence_confirmed=True,
        version_key="unknown-size",
    )
    conservative = build_recovery_denominator(
        envelope(known_versions=[unknown_size], recovery_search_complete=True),
        store(),
    )
    assert conservative["items"][0]["status"] == "not_verified"


def test_known_version_keys_are_explicit_and_do_not_silently_collapse():
    first = known_version(sha256="d" * 64, byte_size=None, version_key="note-a")
    second = known_version(sha256="d" * 64, byte_size=None, version_key="note-b")
    inventory = build_recovery_denominator(envelope(known_versions=[first, second]), store())
    assert inventory["metrics"]["denominator_items"] == 2
    assert inventory["metrics"]["distinct_content_objects_known"] == 1

    duplicate = known_version(sha256="e" * 64, byte_size=None, version_key="note-a")
    import pytest
    with pytest.raises(ValueError, match="Duplicate known-version"):
        build_recovery_denominator(envelope(known_versions=[first, duplicate]), store())
