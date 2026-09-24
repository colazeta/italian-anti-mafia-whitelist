from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path

import pytest

from white_list_archive.acquisition.archive_first import archive_payload
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig


class ExistingObject(Exception):
    def __init__(self):
        self.response = {"Error": {"Code": "PreconditionFailed"}}


class MemoryClient:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        assert Bucket == "archive-bucket"
        assert kwargs["IfNoneMatch"] == "*"
        if Key in self.objects:
            raise ExistingObject()
        self.objects[Key] = bytes(Body)
        return {}

    def get_object(self, *, Bucket, Key):
        assert Bucket == "archive-bucket"
        if Key not in self.objects:
            raise KeyError(Key)
        return {"Body": io.BytesIO(self.objects[Key])}


def store(client: MemoryClient) -> EvidenceStore:
    return EvidenceStore(
        client,
        StoreConfig(
            bucket="archive-bucket",
            endpoint="https://evidence.example",
            region="auto",
            policy_evidence="internal-policy-record",
        ),
    )


def capture(
    tmp_path: Path,
    evidence: EvidenceStore,
    *,
    capture_id: str,
    origin_type: str = "official_primary",
    authority_rank_code: str = "prefecture",
    resource_type_code: str = "white_list",
):
    return archive_payload(
        data=b"official source bytes",
        source_key="alpha-listed",
        resource_url="https://prefettura.example/white-list.pdf",
        reference_date="2026-09-22",
        content_type="application/pdf",
        store=evidence,
        work_dir=tmp_path,
        captured_at=datetime(2026, 9, 22, 18, 0, tzinfo=timezone.utc),
        capture_id=capture_id,
        resolved_url="https://cdn.prefettura.example/white-list.pdf",
        http_status=200,
        etag='"example-etag"',
        last_modified="Tue, 22 Sep 2026 17:45:00 GMT",
        origin_type=origin_type,
        authority_rank_code=authority_rank_code,
        resource_type_code=resource_type_code,
    )


def canonical_json(value: dict) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def test_catalogue_persists_complete_frozen_capture_manifest(tmp_path):
    client = MemoryClient()
    result = capture(
        tmp_path,
        store(client),
        capture_id="11111111-1111-4111-8111-111111111111",
    )

    key = result.catalogue_receipt["catalogue_key"]
    record = json.loads(client.objects[key])
    assert record["capture_manifest"] == result.manifest
    assert record["capture_manifest"]["origin_type"] == "official_primary"
    assert record["capture_manifest"]["authority_rank_code"] == "prefecture"
    assert record["capture_manifest"]["resource_type_code"] == "white_list"
    assert hashlib.sha256(canonical_json(result.manifest)).hexdigest() == record["capture_manifest_sha256"]


def test_exact_capture_retry_is_idempotent_despite_new_content_readback_time(tmp_path):
    client = MemoryClient()
    evidence = store(client)
    capture_id = "22222222-2222-4222-8222-222222222222"
    first = capture(tmp_path / "first", evidence, capture_id=capture_id)
    key = first.catalogue_receipt["catalogue_key"]
    original = client.objects[key]

    second = capture(tmp_path / "second", evidence, capture_id=capture_id)

    assert second.catalogue_receipt["created"] is False
    assert client.objects[key] == original
    assert second.catalogue_receipt["catalogue_record_sha256"] == hashlib.sha256(original).hexdigest()
    assert second.content_receipt["verified_at"] != json.loads(original)["content_verified_at"]


def test_pre_upgrade_catalogue_record_remains_readable_without_in_place_upgrade(tmp_path):
    client = MemoryClient()
    evidence = store(client)
    capture_id = "33333333-3333-4333-8333-333333333333"
    first = capture(tmp_path / "first", evidence, capture_id=capture_id)
    key = first.catalogue_receipt["catalogue_key"]

    legacy = json.loads(client.objects[key])
    legacy.pop("capture_manifest")
    legacy_bytes = canonical_json(legacy)
    client.objects[key] = legacy_bytes

    retried = capture(tmp_path / "retry", evidence, capture_id=capture_id)

    assert retried.catalogue_receipt["created"] is False
    assert client.objects[key] == legacy_bytes
    assert retried.catalogue_receipt["catalogue_record_sha256"] == hashlib.sha256(legacy_bytes).hexdigest()


def test_existing_capture_cannot_be_relabelled_through_optional_provenance(tmp_path):
    client = MemoryClient()
    evidence = store(client)
    capture_id = "44444444-4444-4444-8444-444444444444"
    capture(tmp_path / "first", evidence, capture_id=capture_id)

    with pytest.raises(ValueError, match="frozen release capture"):
        capture(
            tmp_path / "relabelled",
            evidence,
            capture_id=capture_id,
            origin_type="official_secondary",
        )
