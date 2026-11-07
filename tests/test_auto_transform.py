from __future__ import annotations

import hashlib

import pytest

from white_list_archive.acquisition.auto_transform import (
    _parse_config,
    _parser_revision,
    select_reviewed_jobs,
)


H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64


def _history(source_key, sha, capture_id, when="2026-11-06T08:00:00+00:00"):
    return {
        "source_key": source_key,
        "sha256": sha,
        "capture_id": capture_id,
        "captured_at": when,
        "byte_size": 500,
    }


def _scalar():
    cfg = {
        "source_key": "sample-listed",
        "authority_key": "sample",
        "resource_url": "https://official.example/white-list.pdf",
        "sha256": H1,
        "reference_date": "2026-10-01",
        "parser": "sample_parser",
    }
    state = {
        "schema_version": 1,
        "robots": {
            "sample": {
                "population_mapping_reviewed": True,
                "resources": {
                    cfg["resource_url"]: {
                        "capture_history": [
                            _history("sample-listed", H1, "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"),
                            _history("sample-listed", H2, "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb", "2026-11-07T08:00:00+00:00"),
                        ]
                    }
                },
            }
        },
    }
    return state, {"sources": [cfg]}


def test_changed_reviewed_scalar_is_selected_without_silent_source_date_reuse():
    state, config = _scalar()
    jobs, deferred = select_reviewed_jobs(state, config)
    assert not deferred
    assert len(jobs) == 1
    assert jobs[0]["captures"]["primary"]["state"]["sha256"] == H2
    prepared = _parse_config(jobs[0])
    assert prepared["reference_date"] == ""
    assert prepared["sha256"] == H2
    assert config["sources"][0]["reference_date"] == "2026-10-01"
    assert config["sources"][0]["sha256"] == H1


def test_unchanged_captures_do_not_reparse_or_create_a_new_edition():
    state, config = _scalar()
    state["robots"]["sample"]["resources"][config["sources"][0]["resource_url"]]["capture_history"].pop()
    jobs, deferred = select_reviewed_jobs(state, config)
    assert jobs == []
    assert deferred == []


def test_only_exact_reviewed_source_capture_is_considered():
    state, config = _scalar()
    url = config["sources"][0]["resource_url"]
    state["robots"]["sample"]["resources"][url]["capture_history"] = [
        _history("sample-robot-discovery", H2, "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb")
    ]
    jobs, deferred = select_reviewed_jobs(state, config)
    assert jobs == []
    assert deferred == [{"source_key": "sample-listed", "reason": "missing_verified_capture"}]


def test_unreviewed_robot_never_triggers_parser():
    state, config = _scalar()
    state["robots"]["sample"]["population_mapping_reviewed"] = False
    jobs, deferred = select_reviewed_jobs(state, config)
    assert jobs == []
    assert deferred == [{"source_key": "sample-listed", "reason": "unreviewed_authority"}]


def test_incomplete_bundle_fails_closed_before_parsing():
    state, config = _scalar()
    source = config["sources"][0]
    source.pop("resource_url")
    source["resources"] = {
        "listed": {"resource_url": "https://official.example/listed.pdf", "sha256": H1},
        "applicant": {"resource_url": "https://official.example/applicant.pdf", "sha256": H3},
    }
    state["robots"]["sample"]["resources"] = {
        "https://official.example/listed.pdf": {
            "capture_history": [_history("sample-listed", H2, "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb")]
        }
    }
    jobs, deferred = select_reviewed_jobs(state, config)
    assert not jobs
    assert deferred == [{"source_key": "sample-listed", "reason": "missing_verified_capture"}]


def test_bundle_uses_independent_labelled_hashes_without_synthetic_date():
    state, config = _scalar()
    source = config["sources"][0]
    source.pop("resource_url")
    source["resources"] = {
        "listed": {"resource_url": "https://official.example/listed.pdf", "sha256": H1},
        "applicant": {"resource_url": "https://official.example/applicant.pdf", "sha256": H3},
    }
    state["robots"]["sample"]["resources"] = {
        "https://official.example/listed.pdf": {
            "capture_history": [_history("sample-listed", H2, "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb")]
        },
        "https://official.example/applicant.pdf": {
            "capture_history": [_history("sample-listed", H3, "cccccccc-cccc-4ccc-cccc-cccccccccccc")]
        },
    }
    jobs, deferred = select_reviewed_jobs(state, config)
    assert not deferred
    assert len(jobs) == 1
    transformed_cfg = _parse_config(jobs[0])
    assert transformed_cfg["resources"]["listed"]["sha256"] == H2
    assert transformed_cfg["resources"]["applicant"]["sha256"] == H3
    assert transformed_cfg["sha256"] == "bundle:" + hashlib.sha256((H3 + H2).encode()).hexdigest()
    assert transformed_cfg["reference_date"] == ""


def test_invalid_robot_state_and_duplicate_approved_source_are_rejected():
    state, config = _scalar()
    with pytest.raises(ValueError):
        select_reviewed_jobs({"robots": {}}, config)
    with pytest.raises(ValueError):
        select_reviewed_jobs(state, {"sources": [config["sources"][0]] * 2})
    with pytest.raises(ValueError):
        select_reviewed_jobs(state, config, shards=0)


def test_parser_revision_requires_consistent_lineage():
    class Batch:
        records = [{"parser_name": "foo", "parser_version": "3"}]
    assert _parser_revision(Batch(), "foo") == "foo@3"
    with pytest.raises(ValueError):
        _parser_revision(Batch(), "different")
