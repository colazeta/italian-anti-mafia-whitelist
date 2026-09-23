from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io

import pytest

from white_list_archive.acquisition.archive_first import archive_payload
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig
from white_list_archive.storage.recovery_denominator import build_recovery_denominator
from white_list_archive.storage.recovery_materialize import apply_recovery_plan


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


def repository_expectations(*, sha256: str, byte_size=None, second=False):
    versions = [
        {
            "authority_key": "legacy",
            "source_key": None,
            "evidence_version_key": "monitoring-check:0:2026-09-22T10:00:00Z:" + sha256,
            "sha256": sha256,
            "byte_size": byte_size,
            "evidence_refs": ["data/monitoring/national_coverage.json#check-0"],
            "recovery_paths": [],
            "durable_absence_confirmed": False,
        }
    ]
    if second:
        versions.append(
            {
                "authority_key": "other",
                "source_key": None,
                "evidence_version_key": "coverage-known:" + "b" * 64,
                "sha256": "b" * 64,
                "byte_size": 77,
                "evidence_refs": ["data/monitoring/national_coverage.json#prefecture-1"],
                "recovery_paths": [],
                "durable_absence_confirmed": False,
            }
        )
    return {
        "schema_version": 1,
        "generated_at": "2026-09-23T01:00:00+00:00",
        "recovery_search_complete": False,
        "captures": [],
        "known_versions": versions,
        "published_release_scopes": [],
    }


def plan(*, sha256: str, byte_size=None, recovery_paths=None,
         durable_absence_confirmed=False, captures=None, search_complete=False,
         evidence_refs=None):
    return {
        "schema_version": 1,
        "generated_at": "2026-09-23T02:30:00+00:00",
        "recovery_search_complete": search_complete,
        "captures": captures or [],
        "known_version_recovery": [
            {
                "authority_key": "legacy",
                "evidence_version_key": "monitoring-check:0:2026-09-22T10:00:00Z:" + sha256,
                "sha256": sha256,
                "byte_size": byte_size,
                "recovery_paths": recovery_paths or [],
                "durable_absence_confirmed": durable_absence_confirmed,
                "operator_evidence_refs": evidence_refs or [],
            }
        ],
    }


def test_reviewed_package_can_resolve_known_size_without_minting_capture(tmp_path):
    data = b"historical exact bytes"
    digest = hashlib.sha256(data).hexdigest()
    package = tmp_path / "historical.pdf"
    package.write_bytes(data)

    expectations = apply_recovery_plan(
        repository_expectations(sha256=digest),
        plan(
            sha256=digest,
            byte_size=len(data),
            recovery_paths=[str(package)],
            evidence_refs=["operator:recovery-package-2026-09-23"],
        ),
    )
    row = expectations["known_versions"][0]
    assert row["byte_size"] == len(data)
    assert row["source_key"] is None
    assert row["recovery_paths"] == [str(package)]
    assert row["evidence_refs"][-1] == "operator:recovery-package-2026-09-23"

    inventory = build_recovery_denominator(expectations, store())
    recovered = inventory["items"][0]
    assert recovered["identity_kind"] == "known_version"
    assert recovered["capture_id"] is None
    assert recovered["status"] == "recoverable_pending"


def test_archive_first_capture_enters_plan_and_verifies_both_bytes_and_provenance(tmp_path):
    evidence = store()
    archived = archive_payload(
        data=b"current mutable bytes",
        source_key="mutable-listed",
        resource_url="https://prefettura.example/current.pdf",
        reference_date=None,
        content_type="application/pdf",
        store=evidence,
        work_dir=tmp_path,
        captured_at=datetime(2026, 9, 23, 2, 0, tzinfo=timezone.utc),
        capture_id="9edc50d3-9ef9-4b8c-bb25-c9300a1d8017",
        http_status=200,
    )
    capture = {
        "authority_key": "mutable",
        "capture": archived.manifest,
        "catalogue": archived.catalogue_receipt,
        "recovery_paths": [],
        "durable_absence_confirmed": False,
    }
    digest = "a" * 64
    expectations = apply_recovery_plan(
        repository_expectations(sha256=digest),
        plan(sha256=digest, captures=[capture]),
    )
    inventory = build_recovery_denominator(expectations, evidence)
    capture_rows = [row for row in inventory["items"] if row["identity_kind"] == "capture"]
    assert len(capture_rows) == 1
    assert capture_rows[0]["status"] == "verified"
    assert capture_rows[0]["durable_original_verified"] is True
    assert capture_rows[0]["capture_provenance_verified"] is True
    assert inventory["metrics"]["captures_expected"] == 1
    assert inventory["metrics"]["captures_with_verified_provenance"] == 1


def test_plan_cannot_create_historical_version_absent_from_repository_evidence():
    digest = "a" * 64
    bad = plan(sha256="c" * 64)
    with pytest.raises(ValueError, match="absent from repository evidence"):
        apply_recovery_plan(repository_expectations(sha256=digest), bad)


def test_reviewed_byte_size_cannot_override_conflicting_repository_size():
    digest = "a" * 64
    with pytest.raises(ValueError, match="byte_size conflicts"):
        apply_recovery_plan(
            repository_expectations(sha256=digest, byte_size=100),
            plan(
                sha256=digest,
                byte_size=101,
                evidence_refs=["operator:size-review"],
            ),
        )


def test_missing_requires_explicit_item_absence_and_completed_global_search():
    digest = "a" * 64
    expectations = apply_recovery_plan(
        repository_expectations(sha256=digest, byte_size=100, second=True),
        plan(
            sha256=digest,
            byte_size=100,
            durable_absence_confirmed=True,
            search_complete=True,
            evidence_refs=["operator:completed-provider-and-package-search"],
        ),
    )
    inventory = build_recovery_denominator(expectations, store())
    rows = {row["authority_key"]: row for row in inventory["items"]}
    assert rows["legacy"]["status"] == "missing"
    assert rows["other"]["status"] == "not_verified"


def test_operational_recovery_fact_requires_operator_evidence_reference():
    digest = "a" * 64
    with pytest.raises(ValueError, match="require operator_evidence_refs"):
        apply_recovery_plan(
            repository_expectations(sha256=digest),
            plan(sha256=digest, byte_size=100),
        )


def test_recovery_plan_requires_timezone_aware_generation_time():
    digest = "a" * 64
    bad = plan(sha256=digest)
    bad["generated_at"] = "2026-09-23T02:30:00"
    with pytest.raises(ValueError, match="explicit timezone"):
        apply_recovery_plan(repository_expectations(sha256=digest), bad)
