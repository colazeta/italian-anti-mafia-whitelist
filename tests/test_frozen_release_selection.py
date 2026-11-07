from __future__ import annotations

import pytest

from white_list_archive.publishing.frozen_release import validate_release_manifest
from white_list_archive.publishing.frozen_release_selection import plan_frozen_release_candidate


def _capture(source_key, capture_id, sha256, captured_at, reference_date=None):
    manifest = {
        "source_key": source_key,
        "capture_id": capture_id,
        "sha256": sha256,
        "byte_size": 100,
        "content_type": "application/pdf",
        "resource_url": "https://prefettura.example/source.pdf",
        "captured_at": captured_at,
        "reference_date": reference_date,
    }
    return {
        "capture": manifest,
        "catalogue": {"capture_id": capture_id, "sha256": sha256, "byte_size": 100},
    }


def _config(mode="raw_sha256"):
    source = {
        "source_key": "alpha-listed",
        "parser": "alpha_parser",
        "resource_url": "https://prefettura.example/source.pdf",
        "reference_date": "2026-09-22",
        "sha256": "a" * 64,
        "approval_mode": mode,
    }
    if mode == "semantic_sha256":
        source["semantic_sha256"] = "f" * 64
    return {"sources": [source]}


def _plan(config, rows):
    return plan_frozen_release_candidate(
        config,
        rows,
        release_id="candidate-test",
        created_at="2026-09-29T05:00:00+00:00",
        code_revision="deadbeef",
    )


def test_v2_keeps_unknown_capture_date_separate_from_reviewed_source_date():
    row = _capture(
        "alpha-listed",
        "11111111-1111-4111-8111-111111111111",
        "a" * 64,
        "2026-09-22T17:00:00+00:00",
    )
    manifest, report = _plan(_config(), [row])
    assert report["selection_complete"]
    resource = manifest["sources"][0]["resources"][0]
    assert resource["capture"]["reference_date"] is None
    assert resource["source_reference_date"] == "2026-09-22"
    validate_release_manifest(manifest, _config())


def test_known_reference_conflict_is_a_gap():
    row = _capture(
        "alpha-listed",
        "22222222-2222-4222-8222-222222222222",
        "a" * 64,
        "2026-09-22T17:00:00+00:00",
        "2026-09-21",
    )
    manifest, report = _plan(_config(), [row])
    assert manifest is None
    assert report["gaps"][0]["reason"] == "known_reference_date_conflict"


def test_raw_selection_ignores_newer_unapproved_bytes():
    rows = [
        _capture("alpha-listed", "33333333-3333-4333-8333-333333333333", "a" * 64, "2026-09-22T17:00:00+00:00"),
        _capture("alpha-listed", "44444444-4444-4444-8444-444444444444", "a" * 64, "2026-09-22T18:00:00+00:00"),
        _capture("alpha-listed", "55555555-5555-4555-8555-555555555555", "b" * 64, "2026-09-22T19:00:00+00:00"),
    ]
    manifest, _ = _plan(_config(), rows)
    selected = manifest["sources"][0]["resources"][0]["capture"]
    assert selected["capture_id"] == "44444444-4444-4444-8444-444444444444"


def test_semantic_selection_pins_latest_wrapper_for_replay_gate():
    rows = [
        _capture("alpha-listed", "66666666-6666-4666-8666-666666666666", "1" * 64, "2026-09-22T17:00:00+00:00"),
        _capture("alpha-listed", "77777777-7777-4777-8777-777777777777", "2" * 64, "2026-09-22T18:00:00+00:00"),
    ]
    manifest, _ = _plan(_config("semantic_sha256"), rows)
    assert manifest["sources"][0]["resources"][0]["capture"]["sha256"] == "2" * 64


def test_equal_time_distinct_semantic_payloads_require_explicit_choice():
    when = "2026-09-22T18:00:00+00:00"
    rows = [
        _capture("alpha-listed", "88888888-8888-4888-8888-888888888888", "1" * 64, when),
        _capture("alpha-listed", "99999999-9999-4999-8999-999999999999", "2" * 64, when),
    ]
    manifest, report = _plan(_config("semantic_sha256"), rows)
    assert manifest is None
    assert report["gaps"][0]["reason"] == "equal-time distinct payloads require explicit selection"


def test_v2_changed_locator_keeps_historical_capture_eligible():
    row = _capture(
        "alpha-listed",
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "a" * 64,
        "2026-09-22T17:00:00+00:00",
    )
    config = _config()
    config["sources"][0]["resource_url"] = "https://prefettura.example/moved/source.pdf"

    manifest, report = _plan(config, [row])

    assert report["selection_complete"]
    resource = manifest["sources"][0]["resources"][0]
    assert resource["capture"]["resource_url"] == "https://prefettura.example/source.pdf"
    assert resource["reviewed_resource_url"] == "https://prefettura.example/moved/source.pdf"
    validate_release_manifest(manifest, config)


def test_v2_rejects_tampered_reviewed_locator_without_rewriting_capture():
    row = _capture(
        "alpha-listed",
        "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "a" * 64,
        "2026-09-22T17:00:00+00:00",
    )
    config = _config()
    config["sources"][0]["resource_url"] = "https://prefettura.example/moved/source.pdf"
    manifest, report = _plan(config, [row])
    assert report["selection_complete"]

    resource = manifest["sources"][0]["resources"][0]
    original_capture_url = resource["capture"]["resource_url"]
    resource["reviewed_resource_url"] = "https://prefettura.example/other/source.pdf"

    with pytest.raises(ValueError, match="reviewed resource locator differs"):
        validate_release_manifest(manifest, config)
    assert resource["capture"]["resource_url"] == original_capture_url
