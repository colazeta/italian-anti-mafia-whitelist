from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import io
from pathlib import Path

import pytest

from white_list_archive.acquisition.archive_first import ArchivedCapture, archive_payload
from white_list_archive.publishing import public_national_registry as registry
from white_list_archive.publishing.frozen_release import (
    archived_downloads,
    configuration_sha256,
    validate_release_manifest,
)
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, object_key


class ExistingObject(Exception):
    def __init__(self):
        self.response = {"Error": {"Code": "PreconditionFailed"}}


class MemoryClient:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.fail_catalogue = False

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        assert Bucket == "archive-bucket"
        if self.fail_catalogue and Key.startswith("captures/"):
            raise RuntimeError("catalogue unavailable")
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


def capture(
    tmp_path: Path,
    evidence: EvidenceStore,
    *,
    source_key: str,
    url: str,
    data: bytes,
    capture_id: str,
    reference_date: str | None = "2026-09-22",
):
    return archive_payload(
        data=data,
        source_key=source_key,
        resource_url=url,
        reference_date=reference_date,
        content_type="application/pdf",
        store=evidence,
        work_dir=tmp_path,
        captured_at=datetime(2026, 9, 22, 18, 0, tzinfo=timezone.utc),
        capture_id=capture_id,
        http_status=200,
    )


def test_same_locator_equal_time_distinct_bytes_are_both_preserved(tmp_path):
    evidence = store()
    url = "https://prefettura.example/white-list.pdf"
    first = capture(
        tmp_path,
        evidence,
        source_key="alpha-listed",
        url=url,
        data=b"first official bytes",
        capture_id="11111111-1111-4111-8111-111111111111",
    )
    second = capture(
        tmp_path,
        evidence,
        source_key="alpha-listed",
        url=url,
        data=b"format-only-or-substantive-change",
        capture_id="22222222-2222-4222-8222-222222222222",
    )
    assert first.sha256 != second.sha256
    assert first.manifest["captured_at"] == second.manifest["captured_at"]
    content_keys = [key for key in evidence.client.objects if key.startswith("sha256/")]
    capture_keys = [key for key in evidence.client.objects if key.startswith("captures/")]
    assert len(content_keys) == 2
    assert len(capture_keys) == 2


def test_unchanged_bytes_reuse_content_but_keep_separate_capture_checks(tmp_path):
    evidence = store()
    kwargs = dict(
        source_key="alpha-listed",
        url="https://prefettura.example/white-list.pdf",
        data=b"unchanged bytes",
    )
    first = capture(
        tmp_path,
        evidence,
        capture_id="33333333-3333-4333-8333-333333333333",
        **kwargs,
    )
    second = capture(
        tmp_path,
        evidence,
        capture_id="44444444-4444-4444-8444-444444444444",
        **kwargs,
    )
    assert first.sha256 == second.sha256
    assert first.content_receipt["created"] is True
    assert second.content_receipt["created"] is False
    assert first.catalogue_receipt["capture_id"] != second.catalogue_receipt["capture_id"]
    assert len([key for key in evidence.client.objects if key.startswith("sha256/")]) == 1
    assert len([key for key in evidence.client.objects if key.startswith("captures/")]) == 2


def test_capture_id_cannot_be_relabelled_after_first_durable_record(tmp_path):
    evidence = store()
    capture_id = "55555555-5555-4555-8555-555555555555"
    capture(
        tmp_path,
        evidence,
        source_key="alpha-listed",
        url="https://prefettura.example/white-list.pdf",
        data=b"same bytes",
        capture_id=capture_id,
        reference_date="2026-09-21",
    )
    with pytest.raises(ValueError, match="capture provenance"):
        capture(
            tmp_path,
            evidence,
            source_key="alpha-listed",
            url="https://prefettura.example/white-list.pdf",
            data=b"same bytes",
            capture_id=capture_id,
            reference_date="2026-09-22",
        )


def test_catalogue_failure_keeps_recoverable_content_object_and_blocks_parser_boundary(tmp_path):
    client = MemoryClient()
    client.fail_catalogue = True
    evidence = store(client)
    with pytest.raises(RuntimeError, match="catalogue unavailable"):
        capture(
            tmp_path,
            evidence,
            source_key="alpha-listed",
            url="https://prefettura.example/white-list.pdf",
            data=b"preserve me despite metadata outage",
            capture_id="66666666-6666-4666-8666-666666666666",
        )
    assert len([key for key in client.objects if key.startswith("sha256/")]) == 1
    assert len([key for key in client.objects if key.startswith("captures/")]) == 0


def _release(config: dict, captures: dict[str, ArchivedCapture]) -> dict:
    sources = []
    for cfg in config["sources"]:
        archived = captures[cfg["source_key"]]
        sources.append(
            {
                "source_key": cfg["source_key"],
                "parser": cfg["parser"],
                "parser_revision": f"{cfg['parser']}@test-revision",
                "projector_revision": "public-contract@test-revision",
                "configuration_sha256": configuration_sha256(cfg),
                "resources": [
                    {
                        "label": "primary",
                        "capture": archived.manifest,
                        "catalogue": archived.catalogue_receipt,
                    }
                ],
            }
        )
    return {
        "schema_version": 1,
        "release_id": "test-release-two-scopes",
        "created_at": "2026-09-22T18:30:00+00:00",
        "code_revision": "test-code-revision",
        "source_config_sha256": configuration_sha256(config),
        "sources": sources,
    }


def test_two_scope_release_replay_uses_archive_when_official_urls_are_unavailable(tmp_path):
    evidence = store()
    alpha = capture(
        tmp_path / "capture-a",
        evidence,
        source_key="alpha-listed",
        url="https://prefettura.example/alpha.pdf",
        data=b"alpha pinned bytes",
        capture_id="77777777-7777-4777-8777-777777777777",
    )
    beta = capture(
        tmp_path / "capture-b",
        evidence,
        source_key="beta-applicants",
        url="https://mutable.example/current.pdf",
        data=b"beta mutable endpoint pinned bytes",
        capture_id="88888888-8888-4888-8888-888888888888",
    )
    config = {
        "sources": [
            {
                "source_key": "alpha-listed",
                "parser": "alpha_parser",
                "resource_url": alpha.manifest["resource_url"],
                "reference_date": "2026-09-22",
                "sha256": alpha.sha256,
                "approval_mode": "raw_sha256",
            },
            {
                "source_key": "beta-applicants",
                "parser": "beta_parser",
                "resource_url": beta.manifest["resource_url"],
                "reference_date": "2026-09-22",
                "sha256": "live-byte-hash-is-not-release-identity",
                "approval_mode": "semantic_sha256",
                "semantic_sha256": "0" * 64,
            },
        ]
    }
    release = _release(config, {"alpha-listed": alpha, "beta-applicants": beta})
    validate_release_manifest(release, config)

    # The existing release builder asks its _download helper for the official URL.
    # During replay that helper is archive-only, so DNS/live endpoint availability is irrelevant.
    with archived_downloads(release, config, evidence):
        alpha_path = tmp_path / "replay" / "alpha.pdf"
        beta_path = tmp_path / "replay" / "beta.pdf"
        assert registry._download(alpha.manifest["resource_url"], alpha_path) == alpha.sha256
        assert registry._download(beta.manifest["resource_url"], beta_path) == beta.sha256
        assert alpha_path.read_bytes() == b"alpha pinned bytes"
        assert beta_path.read_bytes() == b"beta mutable endpoint pinned bytes"
        with pytest.raises(RuntimeError, match="no archived capture"):
            registry._download("https://new-live.example/not-in-release.pdf", tmp_path / "forbidden.pdf")


def test_release_replay_rejects_missing_or_corrupted_archived_input(tmp_path):
    evidence = store()
    archived = capture(
        tmp_path / "capture",
        evidence,
        source_key="alpha-listed",
        url="https://prefettura.example/alpha.pdf",
        data=b"alpha pinned bytes",
        capture_id="99999999-9999-4999-8999-999999999999",
    )
    cfg = {
        "source_key": "alpha-listed",
        "parser": "alpha_parser",
        "resource_url": archived.manifest["resource_url"],
        "reference_date": "2026-09-22",
        "sha256": archived.sha256,
        "approval_mode": "raw_sha256",
    }
    config = {"sources": [cfg]}
    release = _release(config, {"alpha-listed": archived})

    missing = deepcopy(release)
    missing["sources"] = []
    with pytest.raises(ValueError, match="every and only"):
        validate_release_manifest(missing, config)

    evidence.client.objects[object_key(archived.manifest)] = b"corrupt"
    with archived_downloads(release, config, evidence):
        with pytest.raises(ValueError, match="Stored evidence"):
            registry._download(archived.manifest["resource_url"], tmp_path / "corrupt-replay.pdf")


def test_release_replay_rejects_corrupted_or_missing_capture_provenance(tmp_path):
    evidence = store()
    archived = capture(
        tmp_path / "capture",
        evidence,
        source_key="alpha-listed",
        url="https://prefettura.example/alpha.pdf",
        data=b"alpha pinned bytes",
        capture_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    )
    cfg = {
        "source_key": "alpha-listed",
        "parser": "alpha_parser",
        "resource_url": archived.manifest["resource_url"],
        "reference_date": "2026-09-22",
        "sha256": archived.sha256,
        "approval_mode": "raw_sha256",
    }
    config = {"sources": [cfg]}
    release = _release(config, {"alpha-listed": archived})
    key = archived.catalogue_receipt["catalogue_key"]

    original = evidence.client.objects.pop(key)
    with pytest.raises(KeyError):
        with archived_downloads(release, config, evidence):
            pass

    evidence.client.objects[key] = b"{}"
    with pytest.raises(ValueError, match="provenance digest"):
        with archived_downloads(release, config, evidence):
            pass

    evidence.client.objects[key] = original
    tampered = deepcopy(release)
    tampered["sources"][0]["resources"][0]["catalogue"]["catalogue_record_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="provenance digest"):
        with archived_downloads(tampered, config, evidence):
            pass
