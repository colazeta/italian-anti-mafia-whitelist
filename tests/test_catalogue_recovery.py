from __future__ import annotations

from datetime import datetime, timezone
import io
import json
from pathlib import Path

import pytest

from white_list_archive.acquisition.archive_first import archive_payload
from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.catalogue_recovery import load_catalogued_capture
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


def archived_capture(tmp_path: Path, evidence: EvidenceStore, *, capture_id: str):
    return archive_payload(
        data=b"official source bytes",
        source_key="alpha-listed",
        resource_url="https://prefettura.example/white-list.pdf",
        reference_date=None,
        content_type="application/pdf",
        store=evidence,
        work_dir=tmp_path,
        captured_at=datetime(2026, 9, 24, 11, 0, tzinfo=timezone.utc),
        capture_id=capture_id,
        resolved_url="https://cdn.prefettura.example/white-list.pdf",
        http_status=200,
        etag='"example-etag"',
        last_modified="Thu, 24 Sep 2026 10:55:00 GMT",
        origin_type="official_primary",
        authority_rank_code="prefecture",
        resource_type_code="white_list",
    )


def canonical_json(value: dict) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def test_new_catalogue_record_can_rehydrate_exact_capture_for_recovery(tmp_path):
    client = MemoryClient()
    evidence = store(client)
    result = archived_capture(
        tmp_path,
        evidence,
        capture_id="11111111-1111-4111-8111-111111111111",
    )

    manifest, receipt = load_catalogued_capture(
        CaptureCatalogue(evidence),
        source_key="alpha-listed",
        capture_id=result.manifest["capture_id"],
    )

    assert manifest == result.manifest
    assert receipt["catalogue_key"] == result.catalogue_receipt["catalogue_key"]
    assert receipt["catalogue_record_sha256"] == result.catalogue_receipt["catalogue_record_sha256"]
    assert receipt["created"] is False
    assert manifest["reference_date"] is None
    assert manifest["origin_type"] == "official_primary"
    evidence.read_verified(manifest)
    CaptureCatalogue(evidence).verify_receipt(manifest, receipt)


def test_legacy_catalogue_without_complete_manifest_fails_closed(tmp_path):
    client = MemoryClient()
    evidence = store(client)
    result = archived_capture(
        tmp_path,
        evidence,
        capture_id="22222222-2222-4222-8222-222222222222",
    )
    key = result.catalogue_receipt["catalogue_key"]
    legacy = json.loads(client.objects[key])
    legacy.pop("capture_manifest")
    legacy_bytes = canonical_json(legacy)
    client.objects[key] = legacy_bytes

    with pytest.raises(ValueError, match="Legacy capture provenance"):
        load_catalogued_capture(
            CaptureCatalogue(evidence),
            source_key="alpha-listed",
            capture_id=result.manifest["capture_id"],
        )

    assert client.objects[key] == legacy_bytes


def test_tampered_embedded_manifest_is_rejected(tmp_path):
    client = MemoryClient()
    evidence = store(client)
    result = archived_capture(
        tmp_path,
        evidence,
        capture_id="33333333-3333-4333-8333-333333333333",
    )
    key = result.catalogue_receipt["catalogue_key"]
    tampered = json.loads(client.objects[key])
    tampered["capture_manifest"]["origin_type"] = "official_secondary"
    client.objects[key] = canonical_json(tampered)

    with pytest.raises(ValueError, match="disagrees with frozen release capture"):
        load_catalogued_capture(
            CaptureCatalogue(evidence),
            source_key="alpha-listed",
            capture_id=result.manifest["capture_id"],
        )
