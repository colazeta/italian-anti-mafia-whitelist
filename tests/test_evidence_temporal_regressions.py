"""Temporal evidence regression tests using synthetic bytes and a protocol double.

These exercise the real EvidenceStore adapter, not provider retention, national
capture wiring, parser lineage, database persistence or release reconstruction.
Passing them must never be reported as national archival readiness.
"""
from copy import deepcopy
import hashlib
from io import BytesIO

import pytest

from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, object_key


class ConditionalExists(Exception):
    response = {"Error": {"Code": "PreconditionFailed"}}


class ObjectTransport:
    """Small conditional-write object transport; not an S3/R2 durability test."""

    def __init__(self):
        self.objects = {}
        self.puts = []
        self.gets = []

    def put_object(self, **kwargs):
        assert kwargs["IfNoneMatch"] == "*", "Unconditional overwrite is forbidden"
        key = (kwargs["Bucket"], kwargs["Key"])
        self.puts.append(key)
        if key in self.objects:
            raise ConditionalExists()
        self.objects[key] = bytes(kwargs["Body"])
        return {}

    def get_object(self, **kwargs):
        key = (kwargs["Bucket"], kwargs["Key"])
        self.gets.append(key)
        if key not in self.objects:
            raise FileNotFoundError("Synthetic archived object missing")
        return {"Body": BytesIO(self.objects[key])}


@pytest.fixture
def backend():
    client = ObjectTransport()
    store = EvidenceStore(client, StoreConfig(
        bucket="synthetic-archive", endpoint="https://archive.example.test",
        region="test", policy_evidence="synthetic-policy-not-provider-verification",
    ))
    return store, client


def capture(data, at="2026-09-22T09:00:00+00:00", reference=None):
    return {
        "sha256": hashlib.sha256(data).hexdigest(), "byte_size": len(data),
        "content_type": "text/html", "resource_url": "https://source.example.test/list",
        "captured_at": at, "reference_date": reference,
    }


def archive(tmp_path, store, data, manifest, name="input.html"):
    path = tmp_path / name
    path.write_bytes(data)
    return store.archive(path, manifest)


@pytest.mark.parametrize("at", [
    "2026-09-22T09:00:00+00:00",  # Equal timestamps must not collapse distinct bytes.
    "2026-09-22T15:00:00+00:00",  # Two revisions within the same calendar day.
    "2026-09-23T09:00:00+00:00",
])
def test_changed_url_payload_keeps_both_content_objects(tmp_path, backend, at):
    store, client = backend
    old, new = b"<p>pending</p>", b"<p>listed!</p>"  # Same byte length.
    before, after = capture(old), capture(new, at)
    frozen_before = deepcopy(before)
    first = archive(tmp_path, store, old, before)
    second = archive(tmp_path, store, new, after)
    assert first["storage_uri"] != second["storage_uri"]
    assert len(client.objects) == 2
    assert before == frozen_before
    assert store.read_verified(before) == old
    assert store.read_verified(after) == new


def test_same_content_later_check_reuses_bytes_keeps_capture_context(tmp_path, backend):
    store, client = backend
    data = b"<p>unchanged</p>"
    before = capture(data)
    after = capture(data, "2026-09-22T16:00:00+00:00")
    first = archive(tmp_path, store, data, before)
    second = archive(tmp_path, store, data, after)
    assert len(client.objects) == 1
    assert first["created"] is True and second["created"] is False
    assert first["storage_uri"] == second["storage_uri"]
    assert first["manifest_sha256"] != second["manifest_sha256"]
    assert first["captured_at"] == before["captured_at"]
    assert second["captured_at"] == after["captured_at"]
    # Check receipts remain separate; this adapter does not persist capture rows.
    assert len(client.gets) == 2


def test_cosmetic_byte_change_is_preserved_even_without_semantic_change(tmp_path, backend):
    store, client = backend
    versions = (b"<p>listed</p>", b"<p>listed</p>\n")
    manifests = [capture(data) for data in versions]
    for data, manifest in zip(versions, manifests):
        archive(tmp_path, store, data, manifest)
    assert len(client.objects) == 2
    assert [store.read_verified(m) for m in manifests] == list(versions)


def test_restoring_older_capture_never_consults_mutable_url(tmp_path, backend, monkeypatch):
    store, _ = backend
    old = b"old source version"
    manifest = capture(old)
    archive(tmp_path, store, old, manifest)

    def reject_source_fetch(*args, **kwargs):
        raise AssertionError("Historical replay must not retrieve the source URL")

    monkeypatch.setattr("urllib.request.urlopen", reject_source_fetch)
    (tmp_path / "input.html").unlink()
    assert store.read_verified(manifest) == old


def test_unknown_reference_date_is_not_replaced_by_capture_date(tmp_path, backend):
    store, _ = backend
    manifest = capture(b"no declared publication date")
    receipt = archive(tmp_path, store, b"no declared publication date", manifest)
    assert manifest["reference_date"] is None
    assert receipt["reference_date"] is None
    assert receipt["captured_at"] == manifest["captured_at"]
    assert receipt["database_promoted"] is False


def test_relabelled_file_does_not_create_another_content_object(tmp_path, backend):
    store, client = backend
    data = b"immutable source"
    original = capture(data)
    relabelled = {**original, "content_type": "application/octet-stream"}
    first = archive(tmp_path, store, data, original, "first.html")
    second = archive(tmp_path, store, data, relabelled, "second.bin")
    assert first["storage_uri"] == second["storage_uri"]
    assert len(client.objects) == 1


def test_hash_without_archived_bytes_is_not_recoverable(backend):
    store, client = backend
    with pytest.raises(FileNotFoundError):
        store.read_verified(capture(b"never stored"))
    assert not client.puts


@pytest.mark.parametrize("corrupt", [b"wrong", b"right plus extra", b""])
def test_corruption_never_becomes_verified_evidence(tmp_path, backend, corrupt):
    store, client = backend
    data = b"right"
    manifest = capture(data)
    archive(tmp_path, store, data, manifest)
    key = (store.config.bucket, object_key(manifest))
    client.objects[key] = corrupt  # Simulated external corruption, not adapter write.
    with pytest.raises(ValueError, match="independent size/SHA-256"):
        store.read_verified(manifest)
    with pytest.raises(ValueError, match="independent size/SHA-256"):
        archive(tmp_path, store, data, manifest)
    assert client.objects[key] == corrupt  # No destructive repair/overwrite fallback.


def test_unverified_local_bytes_are_rejected_before_remote_write(tmp_path, backend):
    store, client = backend
    with pytest.raises(ValueError, match="Local evidence does not match"):
        archive(tmp_path, store, b"wrong", capture(b"right"))
    assert not client.puts and not client.gets


def test_archive_copies_buffered_bytes_not_later_local_file(tmp_path, backend, monkeypatch):
    store, client = backend
    data = b"frozen input"
    manifest = capture(data)
    original_put = client.put_object

    def alter_input_then_put(**kwargs):
        (tmp_path / "input.html").write_bytes(b"changed after verification")
        return original_put(**kwargs)

    monkeypatch.setattr(client, "put_object", alter_input_then_put)
    archive(tmp_path, store, data, manifest)
    assert store.read_verified(manifest) == data


@pytest.mark.parametrize("field,value", [
    ("captured_at", None),
    ("captured_at", "2026-09-22"),
    ("captured_at", "2026-09-22T09:00:00"),
    ("reference_date", "2026-02-30"),
    ("reference_date", "2026-09"),
    ("resource_url", "not-an-absolute-url"),
    ("resource_url", "https://user:password@source.example.test/list"),
    ("content_type", "text/html\r\nInjected: value"),
])
def test_invalid_capture_context_is_rejected_before_upload(tmp_path, backend, field, value):
    store, client = backend
    data = b"valid bytes but invalid provenance"
    manifest = {**capture(data), field: value}
    with pytest.raises(ValueError):
        archive(tmp_path, store, data, manifest)
    assert not client.puts and not client.gets


def test_missing_capture_time_does_not_leave_an_orphan_upload(tmp_path, backend):
    store, client = backend
    data = b"valid bytes without capture timestamp"
    manifest = capture(data)
    del manifest["captured_at"]
    with pytest.raises(ValueError):
        archive(tmp_path, store, data, manifest)
    assert not client.puts and not client.gets


def test_non_json_metadata_is_rejected_before_upload(tmp_path, backend):
    store, client = backend
    data = b"valid bytes with non-JSON metadata"
    manifest = {**capture(data), "invalid_extra": object()}
    with pytest.raises(ValueError):
        archive(tmp_path, store, data, manifest)
    assert not client.puts and not client.gets


def test_capture_receipt_is_bound_to_preupload_metadata(tmp_path, backend, monkeypatch):
    import json
    store, client = backend
    data = b"snapshot before concurrent metadata mutation"
    manifest = {**capture(data), "notes": ["original context"]}
    original = deepcopy(manifest)
    original_put = client.put_object

    def change_caller_metadata(**kwargs):
        manifest["captured_at"] = "2026-09-23T09:00:00+00:00"
        manifest["notes"].append("later caller mutation")
        return original_put(**kwargs)

    monkeypatch.setattr(client, "put_object", change_caller_metadata)
    receipt = archive(tmp_path, store, data, manifest)
    expected_hash = hashlib.sha256(json.dumps(
        original, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    assert receipt["captured_at"] == original["captured_at"]
    assert receipt["manifest_sha256"] == expected_hash
    assert store.read_verified(original) == data


def test_promotion_preserves_minimal_content_object_contract(tmp_path, backend):
    from unittest.mock import Mock
    store, client = backend
    data = b"already linked content object"
    full_capture = capture(data)
    receipt = archive(tmp_path, store, data, full_capture)
    content = {key: full_capture[key] for key in ("sha256", "byte_size", "content_type")}
    cursor = Mock()
    connection = Mock()
    connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
    connection.cursor.return_value.__exit__ = Mock(return_value=False)
    cursor.fetchone.return_value = (
        "existing-id", len(data), "text/html", "artifact:old", "ephemeral",
    )
    # Promotion updates an existing ContentObject, not its capture provenance.
    # Do not invent capture dates or URLs to satisfy a different layer's schema.
    store.promote(connection, content)
    assert cursor.execute.call_args.args[1] == (receipt["storage_uri"], "existing-id")
    assert set(content) == {"sha256", "byte_size", "content_type"}
    assert len(client.objects) == 1
