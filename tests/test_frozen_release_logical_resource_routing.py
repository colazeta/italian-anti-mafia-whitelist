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


def _capture(source_key: str, capture_id: str, payload: bytes, *, captured_at: str = "2026-09-24T00:10:00+00:00") -> dict:
    return {
        "capture_id": capture_id,
        "source_key": source_key,
        "resource_url": URL,
        "resolved_url": URL,
        "captured_at": captured_at,
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


def test_frozen_replay_restores_capture_time_instead_of_replay_time(monkeypatch, tmp_path) -> None:
    payloads = {
        "listed": b"listed archived edition",
        "applicant": b"applicant archived edition",
    }
    member_hashes = {label: hashlib.sha256(payload).hexdigest() for label, payload in payloads.items()}
    config = {
        "schema_version": 1,
        "sources": [
            {
                "source_key": "alpha-combined",
                "parser": "alpha-parser",
                "resources": {
                    label: {"resource_url": URL, "sha256": digest}
                    for label, digest in member_hashes.items()
                },
                "reference_date": None,
                "approval_mode": "raw_sha256",
                "sha256": registry._bundle_digest(member_hashes),
            }
        ],
    }
    times = {
        "listed": "2026-09-24T00:10:00+00:00",
        "applicant": "2026-09-24T02:15:00+02:00",
    }
    resources = []
    payloads_by_capture = {}
    for label in ("listed", "applicant"):
        capture_id = str(uuid4())
        capture = _capture(
            "alpha-combined",
            capture_id,
            payloads[label],
            captured_at=times[label],
        )
        resources.append({"label": label, **_resource(capture)})
        payloads_by_capture[capture_id] = payloads[label]

    # _resource includes its own label; replace it with the logical bundle label.
    for item, label in zip(resources, ("listed", "applicant"), strict=True):
        item["label"] = label

    cfg = config["sources"][0]
    manifest = {
        "schema_version": 1,
        "release_id": "capture-time-not-replay-time",
        "created_at": "2026-09-24T05:00:00+00:00",
        "code_revision": "a" * 40,
        "source_config_sha256": configuration_sha256(config),
        "sources": [
            {
                "source_key": cfg["source_key"],
                "parser": cfg["parser"],
                "parser_revision": "alpha-parser@1",
                "projector_revision": PUBLIC_PROJECTOR_REVISION,
                "configuration_sha256": configuration_sha256(cfg),
                "resources": resources,
            }
        ],
    }

    FakeCatalogue.instances.clear()
    monkeypatch.setattr(frozen_release, "CaptureCatalogue", FakeCatalogue)
    monkeypatch.setattr(
        registry,
        "build_registry",
        lambda *_args, **_kwargs: {
            "meta": {
                "generated_at": "2026-09-29T08:00:00+00:00",
                "sources": [
                    {
                        "source_key": "alpha-combined",
                        "document_checked_at": "2026-09-29T08:00:00+00:00",
                    }
                ],
            },
            "records": [],
        },
    )

    built = frozen_release.build_registry_from_release(
        config,
        tmp_path,
        manifest,
        FakeStore(payloads_by_capture),
    )

    # 02:15+02:00 is 00:15Z and therefore the later of the two real captures.
    assert built["meta"]["sources"][0]["document_checked_at"] == times["applicant"]
    # Replay/system time remains distinct rather than being relabelled as capture time.
    assert built["meta"]["generated_at"] == "2026-09-29T08:00:00+00:00"
