from __future__ import annotations

import hashlib
from uuid import uuid4

from white_list_archive.publishing import frozen_release
from white_list_archive.publishing.frozen_release import (
    PUBLIC_PROJECTOR_REVISION,
    _verified_payloads_by_url,
    configuration_sha256,
)

PAYLOAD = b"same official bytes"
SHA256 = hashlib.sha256(PAYLOAD).hexdigest()
URL = "https://prefettura.example/shared.pdf"


class FakeStore:
    def __init__(self):
        self.reads: list[str] = []

    def read_verified(self, capture: dict) -> bytes:
        self.reads.append(capture["capture_id"])
        return PAYLOAD


class FakeCatalogue:
    instances: list["FakeCatalogue"] = []

    def __init__(self, store):
        self.store = store
        self.verified: list[str] = []
        self.__class__.instances.append(self)

    def verify_receipt(self, capture: dict, receipt: dict) -> dict:
        assert receipt["capture_id"] == capture["capture_id"]
        assert receipt["sha256"] == capture["sha256"]
        assert receipt["byte_size"] == capture["byte_size"]
        self.verified.append(capture["capture_id"])
        return dict(capture)


def _capture(source_key: str, capture_id: str) -> dict:
    return {
        "capture_id": capture_id,
        "source_key": source_key,
        "resource_url": URL,
        "resolved_url": URL,
        "captured_at": "2026-09-23T04:10:00+00:00",
        "reference_date": None,
        "http_status": 200,
        "etag": None,
        "last_modified": None,
        "content_type": "application/pdf",
        "sha256": SHA256,
        "byte_size": len(PAYLOAD),
    }


def _resource(capture: dict) -> dict:
    return {
        "label": "primary",
        "capture": capture,
        "catalogue": {
            "capture_id": capture["capture_id"],
            "sha256": SHA256,
            "byte_size": len(PAYLOAD),
        },
    }


def _fixture() -> tuple[dict, dict, set[str]]:
    config = {
        "schema_version": 1,
        "sources": [
            {
                "source_key": "alpha-combined",
                "parser": "alpha_parser",
                "resource_url": URL,
                "reference_date": None,
                "approval_mode": "semantic_sha256",
            },
            {
                "source_key": "beta-combined",
                "parser": "beta_parser",
                "resource_url": URL,
                "reference_date": None,
                "approval_mode": "semantic_sha256",
            },
        ],
    }
    capture_ids = {str(uuid4()), str(uuid4())}
    sources = []
    for cfg, capture_id in zip(config["sources"], sorted(capture_ids), strict=True):
        capture = _capture(cfg["source_key"], capture_id)
        sources.append(
            {
                "source_key": cfg["source_key"],
                "parser": cfg["parser"],
                "parser_revision": f"{cfg['parser']}@1",
                "projector_revision": PUBLIC_PROJECTOR_REVISION,
                "configuration_sha256": configuration_sha256(cfg),
                "resources": [_resource(capture)],
            }
        )
    manifest = {
        "schema_version": 1,
        "release_id": "same-locator-distinct-captures",
        "created_at": "2026-09-23T04:20:00+00:00",
        "code_revision": "a" * 40,
        "source_config_sha256": configuration_sha256(config),
        "sources": sources,
    }
    return config, manifest, capture_ids


def test_shared_locator_does_not_collapse_distinct_capture_checks(monkeypatch) -> None:
    config, manifest, capture_ids = _fixture()
    FakeCatalogue.instances.clear()
    monkeypatch.setattr(frozen_release, "CaptureCatalogue", FakeCatalogue)
    store = FakeStore()

    payloads = _verified_payloads_by_url(manifest, config, store)

    assert payloads == {URL: PAYLOAD}
    assert set(store.reads) == capture_ids
    assert len(store.reads) == 2
    assert len(FakeCatalogue.instances) == 1
    assert set(FakeCatalogue.instances[0].verified) == capture_ids
    assert len(FakeCatalogue.instances[0].verified) == 2
