from __future__ import annotations

from datetime import datetime, timezone
import io
from pathlib import Path

from white_list_archive.acquisition.archive_first import archive_payload
from white_list_archive.storage.archive_inventory import build_archive_inventory
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, object_key


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


def expectation(result, *, recovery_paths=None, durable_absence_confirmed=False):
    return {
        "authority_key": "mutable",
        "capture": result.manifest,
        "catalogue": result.catalogue_receipt,
        "recovery_paths": recovery_paths or [],
        "durable_absence_confirmed": durable_absence_confirmed,
    }


def envelope(captures, *, recovery_search_complete=False):
    return {
        "schema_version": 1,
        "generated_at": "2026-09-22T19:15:00+00:00",
        "recovery_search_complete": recovery_search_complete,
        "captures": captures,
    }


def test_inventory_counts_captures_separately_from_content_objects(tmp_path):
    evidence = store()
    first = archived(
        tmp_path / "one",
        evidence,
        capture_id="10101010-1010-4010-8010-101010101010",
        data=b"unchanged official bytes",
    )
    second = archived(
        tmp_path / "two",
        evidence,
        capture_id="20202020-2020-4020-8020-202020202020",
        data=b"unchanged official bytes",
    )

    inventory = build_archive_inventory(envelope([expectation(first), expectation(second)]), evidence)
    assert inventory["metrics"] == {
        "source_authorities_covered": 1,
        "captures_expected": 2,
        "distinct_content_objects_expected": 1,
        "durably_retrievable_content_objects": 1,
        "captures_with_verified_provenance": 2,
        "verified": 2,
        "recoverable_pending": 0,
        "missing": 0,
        "not_verified": 0,
    }


def test_durable_bytes_without_catalogue_are_not_archive_verified(tmp_path):
    evidence = store()
    result = archived(
        tmp_path / "source",
        evidence,
        capture_id="21212121-2121-4121-8121-212121212121",
        data=b"durable bytes need temporal provenance",
    )
    expected = expectation(result)
    expected["catalogue"] = None

    inventory = build_archive_inventory(envelope([expected]), evidence)
    row = inventory["captures"][0]
    assert row["status"] == "not_verified"
    assert row["durable_original_verified"] is True
    assert row["capture_provenance_verified"] is False
    assert inventory["metrics"]["durably_retrievable_content_objects"] == 1
    assert inventory["metrics"]["captures_with_verified_provenance"] == 0
    assert inventory["metrics"]["verified"] == 0
    assert inventory["metrics"]["not_verified"] == 1


def test_corrupt_catalogue_prevents_verified_capture_even_when_bytes_are_durable(tmp_path):
    client = MemoryClient()
    evidence = store(client)
    result = archived(
        tmp_path / "source",
        evidence,
        capture_id="22222222-2222-4222-8222-222222222222",
        data=b"durable bytes with corrupt temporal provenance",
    )
    client.objects[result.catalogue_receipt["catalogue_key"]] = b"corrupt"

    inventory = build_archive_inventory(envelope([expectation(result)]), evidence)
    row = inventory["captures"][0]
    assert row["status"] == "not_verified"
    assert row["durable_original_verified"] is True
    assert row["capture_provenance_verified"] is False
    assert inventory["metrics"]["durably_retrievable_content_objects"] == 1
    assert inventory["metrics"]["captures_with_verified_provenance"] == 0
    assert inventory["metrics"]["verified"] == 0
    assert inventory["metrics"]["not_verified"] == 1


def test_exact_local_copy_is_recoverable_pending_not_durable(tmp_path):
    source_store = store()
    result = archived(
        tmp_path / "source",
        source_store,
        capture_id="30303030-3030-4030-8030-303030303030",
        data=b"at-risk exact recovery bytes",
    )
    recovery_path = tmp_path / "package" / "original.bin"
    recovery_path.parent.mkdir()
    recovery_path.write_bytes(b"at-risk exact recovery bytes")
    expected = expectation(result, recovery_paths=[str(recovery_path)])
    # A recovery package is not the governed durable store.
    expected["catalogue"] = None

    inventory = build_archive_inventory(envelope([expected]), store())
    row = inventory["captures"][0]
    assert row["status"] == "recoverable_pending"
    assert row["durable_original_verified"] is False
    assert inventory["metrics"]["durably_retrievable_content_objects"] == 0


def test_failed_get_or_incomplete_search_never_implies_missing(tmp_path):
    source_store = store()
    result = archived(
        tmp_path / "source",
        source_store,
        capture_id="40404040-4040-4040-8040-404040404040",
        data=b"expected bytes",
    )
    expected = expectation(result, durable_absence_confirmed=True)
    expected["catalogue"] = None

    incomplete = build_archive_inventory(envelope([expected], recovery_search_complete=False), store())
    assert incomplete["captures"][0]["status"] == "not_verified"

    exhaustive = build_archive_inventory(envelope([expected], recovery_search_complete=True), store())
    assert exhaustive["captures"][0]["status"] == "missing"


def test_corrupt_governed_object_is_not_misreported_as_missing(tmp_path):
    source_store = store()
    result = archived(
        tmp_path / "source",
        source_store,
        capture_id="50505050-5050-4050-8050-505050505050",
        data=b"expected bytes",
    )
    client = MemoryClient()
    client.objects[object_key(result.manifest)] = b"corrupt"
    expected = expectation(result, durable_absence_confirmed=False)
    expected["catalogue"] = None

    inventory = build_archive_inventory(envelope([expected], recovery_search_complete=True), store(client))
    row = inventory["captures"][0]
    assert row["status"] == "not_verified"
    assert row["provider_check_error_class"] == "ValueError"


def test_only_original_bytes_are_cached_within_one_inventory(tmp_path, monkeypatch):
    evidence = store()
    captures = [archived(tmp_path / str(i), evidence,
        capture_id=f'{i:08d}-1111-4111-8111-111111111111',
        data=b'shared bytes' if i < 3 else b'different bytes') for i in range(1, 4)]
    original_get = evidence.client.get_object
    calls = []
    def tracked(**kwargs):
        calls.append(kwargs['Key'])
        return original_get(**kwargs)
    monkeypatch.setattr(evidence.client, 'get_object', tracked)
    expectations = envelope([expectation(c) for c in captures])
    inventory = build_archive_inventory(expectations, evidence)
    assert inventory['metrics']['verified'] == 3
    assert len([k for k in calls if k.startswith('sha256/')]) == 2
    for capture in captures:
        assert calls.count(capture.catalogue_receipt['catalogue_key']) == 1
    # Next invocation must independently verify originals again.
    calls.clear()
    evidence.client.objects[object_key(captures[0].manifest)] = b'corrupted'
    inventory = build_archive_inventory(expectations, evidence)
    assert inventory['metrics']['verified'] == 1
    assert calls.count(object_key(captures[0].manifest)) == 2  # failures never cached
    assert len([k for k in calls if k.startswith('sha256/')]) == 3


def test_cached_bytes_never_bypass_capture_catalogue_or_conflicting_size(tmp_path, monkeypatch):
    from copy import deepcopy
    evidence = store()
    first = archived(tmp_path / 'first', evidence,
        capture_id='51515151-5151-4151-8151-515151515151', data=b'shared')
    second = archived(tmp_path / 'second', evidence,
        capture_id='61616161-6161-4161-8161-616161616161', data=b'shared')
    broken = expectation(second)
    evidence.client.objects[second.catalogue_receipt['catalogue_key']] = b'corrupt'
    inventory = build_archive_inventory(envelope([expectation(first), broken]), evidence)
    assert [r['status'] for r in inventory['captures']] == ['verified', 'not_verified']
    assert inventory['captures'][1]['durable_original_verified'] is True
    # Same digest and wrong size must not hit the positive identity cache.
    broken = deepcopy(broken)
    broken['capture']['byte_size'] += 1
    inventory = build_archive_inventory(envelope([expectation(first), broken]), evidence)
    assert inventory['captures'][1]['durable_original_verified'] is False
    assert inventory['captures'][1]['status'] == 'not_verified'


def test_parallel_inventory_deduplicates_inflight_bytes_but_checks_every_catalogue(tmp_path, monkeypatch):
    import threading
    import time
    from white_list_archive.storage.capture_catalogue import CaptureCatalogue
    evidence = store()
    captures = [archived(tmp_path / str(i), evidence,
        capture_id=f'{i:08d}-2222-4222-8222-222222222222', data=b'same original')
        for i in range(1, 9)]
    expected = envelope([expectation(c) for c in captures])
    original_read = evidence.read_verified
    catalogue_read = CaptureCatalogue.verify_receipt
    lock = threading.Lock()
    counts = {'original': 0, 'catalogue': 0, 'active': 0, 'peak': 0}

    def slow_original(capture):
        with lock:
            counts['original'] += 1
        time.sleep(0.03)  # All workers contend for the same original identity.
        return original_read(capture)

    def slow_catalogue(catalogue, capture, receipt):
        with lock:
            counts['catalogue'] += 1
            counts['active'] += 1
            counts['peak'] = max(counts['peak'], counts['active'])
        time.sleep(0.01 * (4 - int(capture['capture_id'][:8]) % 4))
        try:
            return catalogue_read(catalogue, capture, receipt)
        finally:
            with lock:
                counts['active'] -= 1

    monkeypatch.setattr(evidence, 'read_verified', slow_original)
    monkeypatch.setattr(CaptureCatalogue, 'verify_receipt', slow_catalogue)
    result = build_archive_inventory(expected, evidence)
    assert counts['original'] == 1
    assert counts['catalogue'] == 8
    assert 1 < counts['peak'] <= 4
    assert [r['capture_id'] for r in result['captures']] == [c.manifest['capture_id'] for c in captures]
    # Serial and concurrent output are identical; verification state never leaks.
    serial = build_archive_inventory(expected, evidence, max_workers=1)
    assert serial == result
    assert counts['original'] == 2
    assert counts['catalogue'] == 16
    # One corrupt catalogue is never masked by another capture's valid bytes.
    evidence.client.objects[captures[3].catalogue_receipt['catalogue_key']] = b'corrupt'
    changed = build_archive_inventory(expected, evidence)
    assert changed['metrics']['verified'] == 7
    assert changed['captures'][3]['status'] == 'not_verified'
    assert counts['catalogue'] == 24


def test_parallel_inventory_bounds_outstanding_work_on_unexpected_failure(tmp_path, monkeypatch):
    import pytest
    import white_list_archive.storage.archive_inventory as module
    evidence = store()
    captures = [archived(tmp_path / str(i), evidence,
        capture_id=f'{i:08d}-3333-4333-8333-333333333333', data=b'same original')
        for i in range(1, 13)]
    rows = [expectation(c) for c in captures]
    for row in rows:
        row['catalogue'] = None
    reads = []
    def unavailable(capture):
        reads.append(capture['capture_id'])
        raise RuntimeError('unavailable')
    def unexpected(*args, **kwargs):
        raise RuntimeError('unexpected recovery failure')
    monkeypatch.setattr(evidence, 'read_verified', unavailable)
    monkeypatch.setattr(module, '_verified_recovery_copy', unexpected)
    with pytest.raises(RuntimeError, match='unexpected recovery failure'):
        build_archive_inventory(envelope(rows), evidence)
    assert 1 <= len(reads) <= 4
    with pytest.raises(ValueError, match='between one and four'):
        build_archive_inventory(envelope(rows), evidence, max_workers=5)
