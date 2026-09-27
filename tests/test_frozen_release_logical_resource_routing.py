from __future__ import annotations

import hashlib
from uuid import uuid4

from white_list_archive.publishing import frozen_release
from white_list_archive.publishing import public_national_registry as registry
from white_list_archive.publishing.frozen_release import (
    PUBLIC_PROJECTOR_REVISION,
    configuration_sha256,
)

URL = "https://prefettura.example/shared.pdf"


class FakeStore:
    def __init__(self, payloads: dict[str, bytes]):
        self.payloads = payloads
        self.reads: list[str] = []

    def read_verified(self, capture: dict) -> bytes:
        capture_id = capture["capture_id"]
        self.reads.append(capture_id)
        return self.payloads[capture_id]


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


def _capture(source_key: str, capture_id: str, payload: bytes) -> dict:
    return {
        "capture_id": capture_id,
        "source_key": source_key,
        "resource_url": URL,
        "resolved_url": URL,
        "captured_at": "2026-09-24T00:10:00+00:00",
        "reference_date": None,
        "http_status": 200,
        "etag": None,
        "last_modified": None,
        "content_type": "application/pdf",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_size": len(payload),
    }


def _resource(capture: dict) -> dict:
    return {
        "label": "primary",
        "capture": capture,
        "catalogue": {
            "capture_id": capture["capture_id"],
            "sha256": capture["sha256"],
            "byte_size": capture["byte_size"],
        },
    }


def test_same_locator_can_replay_distinct_bytes_by_logical_resource(monkeypatch, tmp_path) -> None:
    payload_by_source = {
        "alpha-combined": b"alpha archived edition",
        "beta-combined": b"beta archived edition",
    }
    config = {
        "schema_version": 1,
        "sources": [
            {
                "source_key": source_key,
                "parser": f"{source_key}-parser",
                "resource_url": URL,
                "reference_date": None,
                "approval_mode": "raw_sha256",
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            for source_key, payload in payload_by_source.items()
        ],
    }

    payloads_by_capture: dict[str, bytes] = {}
    manifest_sources = []
    capture_ids: set[str] = set()
    for cfg in config["sources"]:
        capture_id = str(uuid4())
        payload = payload_by_source[cfg["source_key"]]
        capture = _capture(cfg["source_key"], capture_id, payload)
        payloads_by_capture[capture_id] = payload
        capture_ids.add(capture_id)
        manifest_sources.append(
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
        "release_id": "shared-locator-distinct-bytes",
        "created_at": "2026-09-24T00:20:00+00:00",
        "code_revision": "a" * 40,
        "source_config_sha256": configuration_sha256(config),
        "sources": manifest_sources,
    }

    FakeCatalogue.instances.clear()
    monkeypatch.setattr(frozen_release, "CaptureCatalogue", FakeCatalogue)
    monkeypatch.setattr(
        registry,
        "_download",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("live download must not be used")),
    )
    store = FakeStore(payloads_by_capture)

    with frozen_release.archived_downloads(manifest, config, store):
        alpha_path, alpha_sha = registry._acquire_source_input(config["sources"][0], tmp_path)
        beta_path, beta_sha = registry._acquire_source_input(config["sources"][1], tmp_path)

    assert alpha_path.read_bytes() == payload_by_source["alpha-combined"]
    assert beta_path.read_bytes() == payload_by_source["beta-combined"]
    assert alpha_sha != beta_sha
    assert set(store.reads) == capture_ids
    assert len(store.reads) == 2
    assert len(FakeCatalogue.instances) == 1
    assert set(FakeCatalogue.instances[0].verified) == capture_ids
