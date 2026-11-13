"""Historical readback materialisation cannot infer evidence, editions or dates."""
from __future__ import annotations

import hashlib
import io
import json
from uuid import UUID

from white_list_archive.storage.capture_catalogue import capture_record_key, freeze_capture_record
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, digest_object_key
from white_list_archive.storage import historical_capture_reconciliation as backfill


class Client:
    def __init__(self):
        self.objects = {}
        self.truncated = False

    def list_objects_v2(self, *, Bucket, Prefix, MaxKeys):
        assert Bucket == "archive-bucket"
        assert MaxKeys <= 64
        matches = sorted(k for k in self.objects if k.startswith(Prefix))
        return {
            "Contents": [{"Key": k} for k in matches[:MaxKeys]],
            "IsTruncated": self.truncated or len(matches) > MaxKeys,
        }

    def get_object(self, *, Bucket, Key):
        return {
            "Body": io.BytesIO(self.objects[Key]),
            "ContentLength": len(self.objects[Key]),
        }


def fixture(*, metadata=True, source="lodi-listed"):
    client = Client()
    store = EvidenceStore(
        client, StoreConfig(
            bucket="archive-bucket", endpoint="https://archive.example",
            region="auto", policy_evidence="reviewed-private",
        ),
    )
    original = b"synthetic white-list content not a real administrative edition"
    sha = hashlib.sha256(original).hexdigest()
    manifest = {
        "schema_version": 2,
        "capture_id": str(UUID("11111111-1111-4111-8111-111111111111")),
        "source_key": source, "sha256": sha, "byte_size": len(original),
        "content_type": "text/csv",
        "resource_url": "https://official.example/reviewed.csv",
        "resolved_url": "https://official.example/reviewed.csv",
        "captured_at": "2026-09-27T12:00:00Z",
        "reference_date": None,
        "http_status": 200,
    }
    if metadata:
        manifest.update(
            origin_type="official_current",
            authority_rank_code="primary_official",
            resource_type_code="other",
        )
    manifest_digest = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    receipt = {
        "sha256": sha, "byte_size": len(original),
        "manifest_sha256": manifest_digest,
        "verified_at": "2026-09-27T12:01:00Z",
    }
    record = freeze_capture_record(manifest, receipt)
    client.objects[capture_record_key(record)] = json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode()
    client.objects[digest_object_key(sha)] = original
    return store, sha


def targets(sha):
    return (("lodi-listed", "fixture", sha),)


def test_only_exact_verified_immutable_capture_provenance_is_eligible():
    store, sha = fixture()
    checked, report = backfill.select_verified_historical_checks(
        store, targets=targets(sha),
    )
    assert len(checked) == 1
    assert report["eligible_capture_checks"] == 1
    assert report["pins_with_eligible_capture_provenance"] == 1
    assert checked[0][0]["reference_date"] is None
    assert "official.example" not in json.dumps(report)
    assert sha not in json.dumps(report)


def test_missing_provenance_fields_never_reconstructed_from_a_source_url():
    store, sha = fixture(metadata=False)
    checked, report = backfill.select_verified_historical_checks(
        store, targets=targets(sha),
    )
    assert checked == []
    assert report["missing_writer_metadata_checks"] == 1
    assert report["eligible_capture_checks"] == 0


def test_bounded_truncation_and_bad_byte_digest_fail_closed():
    store, sha = fixture()
    store.client.truncated = True
    assert backfill.select_verified_historical_checks(
        store, targets=targets(sha),
    )[0] == []
    store.client.truncated = False
    store.client.objects[digest_object_key(sha)] = b"damaged"
    assert backfill.select_verified_historical_checks(
        store, targets=targets(sha),
    )[0] == []


def test_missing_writer_does_not_materialise_or_approve():
    store, sha = fixture()
    result = backfill.reconcile_historical_capture_checks(
        store, "", targets=targets(sha),
    )
    assert result["eligible_capture_checks"] == 1
    assert result["writer_configured"] is False
    assert result["source_capture_checks_postcommit_verified"] == 0
    assert result["new_content_objects"] == 0
    assert result["editions_approved"] == 0
    assert result["semantic_or_canonical_writes"] == 0
    assert result["public_promotions"] == 0


def test_success_requires_independent_postcommit_readback(monkeypatch):
    store, sha = fixture()
    seen = []
    def fake_readback(store, manifest, receipt, dsn):
        seen.append((manifest["sha256"], manifest["capture_id"]))
        return True, True
    monkeypatch.setattr(backfill, "persist_and_independently_readback", fake_readback)
    result = backfill.reconcile_historical_capture_checks(
        store, "test-only-dsn", targets=targets(sha),
    )
    assert len(seen) == 1
    assert result["source_capture_checks_postcommit_verified"] == 1
    assert result["new_source_capture_checks"] == 1
    assert result["new_content_objects"] == 1
    assert result["relational_reconciliation_failures"] == 0


def test_error_after_selection_is_fail_closed_and_redacted(monkeypatch):
    store, sha = fixture()
    def fake_failure(*args):
        raise RuntimeError("secret, source row, private object key")
    monkeypatch.setattr(backfill, "persist_and_independently_readback", fake_failure)
    result = backfill.reconcile_historical_capture_checks(
        store, "test-only-dsn", targets=targets(sha),
    )
    assert result["source_capture_checks_postcommit_verified"] == 0
    assert result["relational_reconciliation_failures"] == 1
    assert "secret" not in json.dumps(result)
    assert "private" not in json.dumps(result)


def test_failed_capture_diagnostic_has_only_closed_aggregates(monkeypatch):
    store, sha = fixture()
    def fake_failure(*args):
        raise RuntimeError("secret private URL, source row")
    monkeypatch.setattr(backfill, "persist_and_independently_readback", fake_failure)
    monkeypatch.setattr(
        backfill, "classify_failed_capture",
        lambda *args: "capture_uuid_original_conflict",
    )
    result = backfill.reconcile_historical_capture_checks(
        store, "test-dsn", targets=targets(sha),
    )
    assert result["relational_reconciliation_failures"] == 1
    assert result["reconciliation_failure_categories"]["capture_uuid_original_conflict"] == 1
    assert sum(result["reconciliation_failure_categories"].values()) == 1
    assert "secret" not in json.dumps(result)
    assert "official.example" not in json.dumps(result)


def test_unexpected_diagnostic_class_never_leaks(monkeypatch):
    store, sha = fixture()
    def fake_failure(*args):
        raise RuntimeError("secret")
    monkeypatch.setattr(backfill, "persist_and_independently_readback", fake_failure)
    monkeypatch.setattr(backfill, "classify_failed_capture", lambda *args: "secret")
    result = backfill.reconcile_historical_capture_checks(
        store, "test-dsn", targets=targets(sha),
    )
    assert result["reconciliation_failure_categories"]["diagnostic_unavailable"] == 1
    assert "secret" not in json.dumps(result)


def test_resource_conflict_classification_separates_type_and_locator_without_leaking_values():
    loc = "https://private.example/never-output"
    other = "https://private.example/also-never-output"
    assert backfill._resource_conflict_reason(
        stored_url=loc, stored_type="html", archived_url=loc, archived_type="other",
    ) == "resource_locator_type_conflict"
    assert backfill._resource_conflict_reason(
        stored_url=loc, stored_type="html", archived_url=other, archived_type="html",
    ) == "resource_locator_web_url_conflict"
    assert backfill._resource_conflict_reason(
        stored_url=loc, stored_type="html", archived_url=other, archived_type="other",
    ) == "resource_locator_web_url_and_type_conflict"
    assert backfill._resource_conflict_reason(
        stored_url=loc, stored_type="html", archived_url=loc, archived_type="html",
    ) is None
    assert loc not in json.dumps(sorted(backfill._FAILURE_CODES))


def test_resource_conflicts_are_bounded_series_aggregates(monkeypatch):
    store, sha = fixture(source="milano-combined")
    def fake_failure(*args):
        raise ValueError("private locator and capture UUID must never be reported")
    monkeypatch.setattr(backfill, "persist_and_independently_readback", fake_failure)
    monkeypatch.setattr(
        backfill, "classify_failed_capture",
        lambda *args: "resource_locator_type_conflict",
    )
    result = backfill.reconcile_historical_capture_checks(
        store, "test-dsn", targets=(("milano-combined", "fixture", sha),),
    )
    assert result["resource_metadata_conflicts_by_series"] == {
        "lodi-applicants": 0,
        "lodi-listed": 0,
        "milano-combined": 1,
    }
    assert result["relational_reconciliation_failures"] == 1
    assert result["reconciliation_failure_categories"]["resource_locator_type_conflict"] == 1
    assert "private locator" not in json.dumps(result)
    assert "private.example" not in json.dumps(result)
    assert sha not in json.dumps(result)


def test_no_writer_has_zero_closed_scope_counts():
    store, sha = fixture()
    result = backfill.reconcile_historical_capture_checks(
        store, "", targets=targets(sha),
    )
    assert result["resource_metadata_conflicts_by_series"] == {
        "lodi-applicants": 0,
        "lodi-listed": 0,
        "milano-combined": 0,
    }
