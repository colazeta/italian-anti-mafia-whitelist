from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from white_list_archive.publishing.frozen_release import PUBLIC_PROJECTOR_REVISION
from white_list_archive.publishing.frozen_release_select import (
    select_verified_release,
    write_new_release,
)


class FakeStore:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.reads: list[str] = []

    def read_verified(self, capture: dict) -> bytes:
        self.reads.append(capture["capture_id"])
        if self.fail:
            raise ValueError("Stored evidence failed independent size/SHA-256 verification")
        return b"official-bytes"


class FakeCatalogue:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.reads: list[str] = []

    def verify_receipt(self, capture: dict, receipt: dict) -> dict:
        self.reads.append(capture["capture_id"])
        if self.fail:
            raise ValueError("Stored capture provenance failed immutable readback verification")
        assert receipt["capture_id"] == capture["capture_id"]
        return dict(capture)


def _config(*, two_sources: bool = False) -> dict:
    sources = [
        {
            "source_key": "alpha-combined",
            "parser": "alpha_parser",
            "resource_url": "https://prefettura.example/alpha.pdf",
            "reference_date": "2026-09-22",
            "approval_mode": "semantic_sha256",
        }
    ]
    if two_sources:
        sources.append(
            {
                "source_key": "beta-combined",
                "parser": "beta_parser",
                "resource_url": "https://prefettura.example/beta.pdf",
                "reference_date": None,
                "approval_mode": "semantic_sha256",
            }
        )
    return {"schema_version": 1, "sources": sources}


def _capture(source_key: str, url: str, reference_date: str | None, *, capture_id: str | None = None) -> dict:
    payload = b"official-bytes"
    return {
        "capture_id": capture_id or str(uuid4()),
        "source_key": source_key,
        "resource_url": url,
        "resolved_url": url,
        "captured_at": "2026-09-23T04:00:00+00:00",
        "reference_date": reference_date,
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


def _selection(config: dict) -> dict:
    selected = []
    for cfg in config["sources"]:
        capture = _capture(cfg["source_key"], cfg["resource_url"], cfg.get("reference_date"))
        selected.append(
            {
                "source_key": cfg["source_key"],
                "parser_revision": f"{cfg['parser']}@1",
                "projector_revision": PUBLIC_PROJECTOR_REVISION,
                "resources": [_resource(capture)],
            }
        )
    return {
        "schema_version": 1,
        "release_id": "national-2026-09-23T0400Z",
        "created_at": "2026-09-23T04:00:00+00:00",
        "code_revision": "a" * 40,
        "sources": selected,
    }


def test_selector_requires_provider_readback_of_bytes_and_capture_provenance() -> None:
    config = _config(two_sources=True)
    selection = _selection(config)
    store = FakeStore()
    catalogue = FakeCatalogue()

    manifest = select_verified_release(config, selection, store, catalogue=catalogue)

    capture_ids = {r["capture"]["capture_id"] for s in manifest["sources"] for r in s["resources"]}
    assert set(store.reads) == capture_ids
    assert set(catalogue.reads) == capture_ids
    assert {s["source_key"] for s in manifest["sources"]} == {"alpha-combined", "beta-combined"}
    assert manifest["code_revision"] == "a" * 40


def test_selector_fails_closed_when_content_readback_fails() -> None:
    config = _config()
    with pytest.raises(ValueError, match="Stored evidence failed"):
        select_verified_release(config, _selection(config), FakeStore(fail=True), catalogue=FakeCatalogue())


def test_selector_fails_closed_when_capture_provenance_readback_fails() -> None:
    config = _config()
    with pytest.raises(ValueError, match="capture provenance"):
        select_verified_release(config, _selection(config), FakeStore(), catalogue=FakeCatalogue(fail=True))


def test_selector_refuses_partial_national_scope() -> None:
    config = _config(two_sources=True)
    selection = _selection(config)
    selection["sources"] = selection["sources"][:1]
    with pytest.raises(ValueError, match="cover every and only configured source"):
        select_verified_release(config, selection, FakeStore(), catalogue=FakeCatalogue())


def test_selector_refuses_reusing_one_capture_for_two_resources() -> None:
    config = _config(two_sources=True)
    selection = _selection(config)
    shared = selection["sources"][0]["resources"][0]["capture"]["capture_id"]
    selection["sources"][1]["resources"][0]["capture"]["capture_id"] = shared
    selection["sources"][1]["resources"][0]["catalogue"]["capture_id"] = shared
    with pytest.raises(ValueError, match="distinct capture/check"):
        select_verified_release(config, selection, FakeStore(), catalogue=FakeCatalogue())


def test_release_output_is_create_only(tmp_path: Path) -> None:
    config = _config()
    manifest = select_verified_release(config, _selection(config), FakeStore(), catalogue=FakeCatalogue())
    output = tmp_path / "release.json"
    write_new_release(output, manifest)
    with pytest.raises(FileExistsError):
        write_new_release(output, manifest)
