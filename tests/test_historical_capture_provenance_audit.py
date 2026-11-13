from __future__ import annotations

import hashlib
import io
import json

from white_list_archive.acquisition.historical_object_audit import PINS
from white_list_archive.storage.capture_catalogue import (
    capture_record_key, freeze_capture_record,
)
from white_list_archive.storage.evidence import (
    EvidenceStore, StoreConfig, digest_object_key,
)
from white_list_archive.storage.historical_capture_provenance_audit import (
    MAX_KEYS_PER_SOURCE, TARGETS, _valid_capture_key,
    audit_historical_catalogue,
)


class FakeClient:
    def __init__(self):
        self.objects = {}
        self.raise_on_list = False
        self.truncated = False
        self.reads = []

    def list_objects_v2(self, *, Bucket, Prefix, MaxKeys):
        assert Bucket == "archive-bucket"
        assert MaxKeys <= MAX_KEYS_PER_SOURCE
        if self.raise_on_list:
            raise RuntimeError("secret/provider endpoint/private URL")
        keys = sorted(key for key in self.objects if key.startswith(Prefix))
        return {
            "Contents": [{"Key": key} for key in keys[:MaxKeys]],
            "IsTruncated": self.truncated or len(keys) > MaxKeys,
        }

    def get_object(self, *, Bucket, Key):
        assert Bucket == "archive-bucket"
        self.reads.append(Key)
        if Key not in self.objects:
            raise RuntimeError("private bucket coordinate")
        body = self.objects[Key]
        return {"Body": io.BytesIO(body), "ContentLength": len(body)}


def store(client):
    return EvidenceStore(
        client,
        StoreConfig(
            bucket="archive-bucket",
            endpoint="https://archive.example",
            region="auto",
            policy_evidence="reviewed-private-policy",
        ),
    )


def register_capture(client, *, source="lodi-listed", raw=b"test-only bytes", capture_id="11111111-1111-4111-8111-111111111111"):
    digest = hashlib.sha256(raw).hexdigest()
    manifest = {
        "source_key": source,
        "capture_id": capture_id,
        "sha256": digest,
        "byte_size": len(raw),
        "content_type": "text/csv",
        "captured_at": "2026-09-27T11:00:00+00:00",
        "reference_date": None,
        "resource_url": "https://official.example/reviewed-source.csv",
    }
    receipt = {
        "sha256": digest,
        "byte_size": len(raw),
        "manifest_sha256": hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "verified_at": "2026-09-27T11:01:00+00:00",
    }
    record = freeze_capture_record(manifest, receipt)
    key = capture_record_key(record)
    client.objects[key] = json.dumps(
        record, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    client.objects[digest_object_key(digest)] = raw
    return digest, key


def result_for(report, scope):
    return next(row for row in report["results"] if row["scope"] == scope)


def test_closed_historical_source_pins_remain_exact():
    assert TARGETS == (
        ("lodi-listed", PINS[0][0], PINS[0][1]),
        ("lodi-applicants", PINS[1][0], PINS[1][1]),
        ("milano-combined", PINS[2][0], PINS[2][1]),
        ("milano-combined", PINS[3][0], PINS[3][1]),
    )


def test_full_manifest_catalogue_and_original_are_both_required():
    client = FakeClient()
    digest, key = register_capture(client)
    scope = "synthetic-lodi"
    report = audit_historical_catalogue(
        store(client), targets=(("lodi-listed", scope, digest),)
    )
    row = result_for(report, scope)
    assert row["status"] == "verified_immutable_capture_provenance"
    assert row["verified_capture_checks"] == 1
    assert row["bounded_catalogue_listing_complete"] is True
    assert report["pins_with_verified_capture_provenance"] == 1
    assert report["explicit_writer_provenance_ready_checks"] == 0
    assert report["missing_writer_provenance_checks"] == 1
    assert row["missing_writer_provenance_checks"] == 1
    assert report["postgresql_writer_or_commit_verified_here"] is False
    assert report["capture_or_database_writes"] == 0
    assert report["administrative_editions_approved"] == 0
    assert report["public_promotions"] == 0
    assert report["independent_restore_verified"] is False
    # Two distinct provider checks plus the underlying immutable original.
    assert client.reads.count(key) >= 2
    assert digest_object_key(digest) in client.reads


def test_bytes_without_capture_provenance_never_count_as_archived_acquisition():
    client = FakeClient()
    raw = b"historical content with no captured manifest"
    digest = hashlib.sha256(raw).hexdigest()
    client.objects[digest_object_key(digest)] = raw
    report = audit_historical_catalogue(
        store(client), targets=(("lodi-listed", "source-only", digest),)
    )
    row = result_for(report, "source-only")
    assert row["status"] == "unknown"
    assert row["verified_capture_checks"] == 0
    assert row["bounded_catalogue_listing_complete"] is True
    assert report["pins_with_verified_capture_provenance"] == 0


def test_malformed_or_legacy_catalogue_is_unknown_not_inferred():
    client = FakeClient()
    digest, key = register_capture(client)
    legacy = json.loads(client.objects[key])
    legacy.pop("capture_manifest")
    client.objects[key] = json.dumps(
        legacy, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()
    report = audit_historical_catalogue(
        store(client), targets=(("lodi-listed", "legacy", digest),)
    )
    assert result_for(report, "legacy")["status"] == "unknown"
    # It must not mutate or upgrade the legacy record.
    assert "capture_manifest" not in json.loads(client.objects[key])


def test_corrupt_original_and_wrong_series_fail_closed():
    client = FakeClient()
    digest, _ = register_capture(client, source="lodi-applicants")
    report = audit_historical_catalogue(
        store(client), targets=(("lodi-listed", "different-series", digest),)
    )
    assert result_for(report, "different-series")["status"] == "unknown"
    report = audit_historical_catalogue(
        store(client), targets=(("lodi-applicants", "correct-series", digest),)
    )
    assert result_for(report, "correct-series")["verified_capture_checks"] == 1
    client.objects[digest_object_key(digest)] = b"wrong historical bytes"
    report = audit_historical_catalogue(
        store(client), targets=(("lodi-applicants", "corrupt", digest),)
    )
    assert result_for(report, "corrupt")["status"] == "unknown"


def test_incomplete_listing_provider_error_and_secret_redaction():
    client = FakeClient()
    digest, _ = register_capture(client)
    client.truncated = True
    report = audit_historical_catalogue(
        store(client), targets=(("lodi-listed", "bounded", digest),), max_keys=1,
    )
    assert result_for(report, "bounded")["bounded_catalogue_listing_complete"] is False
    # A positive fully verified match may still be retained with an incomplete listing.
    assert result_for(report, "bounded")["status"] == "verified_immutable_capture_provenance"
    client.raise_on_list = True
    report = audit_historical_catalogue(
        store(client), targets=(("lodi-listed", "unavailable", digest),)
    )
    assert result_for(report, "unavailable")["status"] == "unknown"
    assert result_for(report, "unavailable")["bounded_catalogue_listing_complete"] is False
    output = json.dumps(report)
    assert "secret" not in output and "private URL" not in output
    assert "archive.example" not in output and digest not in output


def test_bad_inputs_are_rejected_without_listing():
    client = FakeClient()
    valid = ("lodi-listed", "scope", "f" * 64)
    for targets, limit in (
        ((valid, valid), 64), ((("lodi-listed", "scope", "bad"),), 64),
        ((valid,), 65), ((valid,), 0),
    ):
        try:
            audit_historical_catalogue(store(client), targets=targets, max_keys=limit)
        except ValueError:
            pass
        else:
            raise AssertionError("Bad archive identity or scan bound accepted")
    assert client.reads == []


def test_capture_key_validation_never_uses_untrusted_locator():
    assert _valid_capture_key(
        "captures/v1/lodi-listed/11111111-1111-4111-8111-111111111111.json",
        source_key="lodi-listed",
    ) == "11111111-1111-4111-8111-111111111111"
    assert _valid_capture_key(
        "captures/v1/lodi-applicants/11111111-1111-4111-8111-111111111111.json",
        source_key="lodi-listed",
    ) is None
    assert _valid_capture_key(
        "captures/v1/lodi-listed/../../private.json", source_key="lodi-listed"
    ) is None


def test_explicit_writer_provenance_is_a_separate_verified_gate():
    client = FakeClient()
    raw = b"synthetic reviewed writer preflight"
    digest, key = register_capture(client, raw=raw)
    record = json.loads(client.objects[key])
    manifest = record["capture_manifest"]
    manifest.update(
        origin_type="official_current",
        authority_rank_code="primary_official",
        resource_type_code="other",
    )
    receipt = {
        "sha256": digest,
        "byte_size": len(raw),
        "manifest_sha256": hashlib.sha256(json.dumps(
            manifest, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest(),
        "verified_at": "2026-09-27T11:01:00+00:00",
    }
    rewritten = freeze_capture_record(manifest, receipt)
    client.objects[key] = json.dumps(
        rewritten, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    report = audit_historical_catalogue(
        store(client), targets=(("lodi-listed", "synthetic", digest),)
    )
    assert report["pins_with_verified_capture_provenance"] == 1
    assert report["explicit_writer_provenance_ready_checks"] == 1
    assert report["missing_writer_provenance_checks"] == 0
    assert report["capture_or_database_writes"] == 0
    assert report["administrative_editions_approved"] == 0
    assert "https://official.example" not in json.dumps(report)
    assert digest not in json.dumps(report)
