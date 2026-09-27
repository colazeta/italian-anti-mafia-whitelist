from __future__ import annotations

from copy import deepcopy

import pytest

from white_list_archive.publishing.frozen_release import configuration_sha256
from white_list_archive.storage.release_recovery import (
    distinct_content_object_inputs,
    selected_release_captures,
)


SHA = "a" * 64
URL = "https://example.gov.it/white-list/current.pdf"


def _config():
    return {
        "sources": [
            {"source_key": "alpha-listed", "parser": "alpha", "resource_url": URL, "reference_date": None},
            {"source_key": "beta-listed", "parser": "beta", "resource_url": URL, "reference_date": None},
        ]
    }


def _capture(source_key: str, capture_id: str, *, content_type: str = "application/pdf"):
    return {
        "source_key": source_key,
        "capture_id": capture_id,
        "sha256": SHA,
        "byte_size": 7,
        "content_type": content_type,
        "resource_url": URL,
        "captured_at": "2026-09-23T12:00:00+00:00",
        "reference_date": None,
    }


def _resource(source_key: str, capture_id: str):
    capture = _capture(source_key, capture_id)
    return {
        "label": "primary",
        "capture": capture,
        "catalogue": {"capture_id": capture_id, "sha256": SHA, "byte_size": 7},
    }


def _manifest():
    config = _config()
    return {
        "schema_version": 1,
        "release_id": "national-2026-09-23-test",
        "created_at": "2026-09-23T12:30:00+00:00",
        "code_revision": "deadbeef",
        "source_config_sha256": configuration_sha256(config),
        "sources": [
            {
                "source_key": "alpha-listed",
                "parser": "alpha",
                "parser_revision": "alpha@1",
                "projector_revision": "public-national-registry@1",
                "configuration_sha256": configuration_sha256(config["sources"][0]),
                "resources": [_resource("alpha-listed", "11111111-1111-4111-8111-111111111111")],
            },
            {
                "source_key": "beta-listed",
                "parser": "beta",
                "parser_revision": "beta@1",
                "projector_revision": "public-national-registry@1",
                "configuration_sha256": configuration_sha256(config["sources"][1]),
                "resources": [_resource("beta-listed", "22222222-2222-4222-8222-222222222222")],
            },
        ],
    }


def test_recovery_keeps_distinct_captures_but_deduplicates_unchanged_bytes():
    selected = selected_release_captures(_manifest(), _config())

    assert [item["capture"]["capture_id"] for item in selected] == [
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
    ]
    assert {item["capture"]["resource_url"] for item in selected} == {URL}
    assert len(distinct_content_object_inputs(selected)) == 1


def test_recovery_rejects_reusing_one_capture_for_multiple_release_resources():
    manifest = _manifest()
    manifest["sources"][1]["resources"][0]["capture"]["capture_id"] = (
        "11111111-1111-4111-8111-111111111111"
    )
    manifest["sources"][1]["resources"][0]["catalogue"]["capture_id"] = (
        "11111111-1111-4111-8111-111111111111"
    )

    with pytest.raises(ValueError, match="cannot reuse one capture/check"):
        selected_release_captures(manifest, _config())


def test_recovery_rejects_conflicting_metadata_for_one_content_identity():
    manifest = _manifest()
    manifest["sources"][1]["resources"][0]["capture"]["content_type"] = "application/octet-stream"

    with pytest.raises(ValueError, match="conflicting frozen metadata"):
        selected_release_captures(manifest, _config())


def test_recovery_selection_does_not_mutate_frozen_release_manifest():
    manifest = _manifest()
    before = deepcopy(manifest)
    selected_release_captures(manifest, _config())
    assert manifest == before
