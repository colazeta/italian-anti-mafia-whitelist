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


def test_capture_selection_uses_utc_instant_not_lexical_offset_order():
    state, config = _scalar()
    url = config["sources"][0]["resource_url"]
    state["robots"]["sample"]["resources"][url]["capture_history"] = [
        _history("sample-listed", H1, "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa",
                 "2026-11-06T08:00:00+00:00"),
        _history("sample-listed", H2, "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb",
                 "2026-11-06T09:00:00+02:00"),
    ]
    # The newer real instant is the H1 original: no changed-source dispatch.
    jobs, deferred = select_reviewed_jobs(state, config)
    assert jobs == []
    assert deferred == []


def test_untrusted_capture_timestamps_do_not_mask_a_valid_capture():
    state, config = _scalar()
    url = config["sources"][0]["resource_url"]
    history = state["robots"]["sample"]["resources"][url]["capture_history"]
    history.extend([
        _history("sample-listed", H3, "cccccccc-cccc-4ccc-cccc-cccccccccccc",
                 "not-a-capture-date"),
        _history("sample-listed", H3, "dddddddd-dddd-4ddd-dddd-dddddddddddd",
                 "2026-12-01T00:00:00"),
    ])
    jobs, deferred = select_reviewed_jobs(state, config)
    assert deferred == []
    assert len(jobs) == 1
    assert jobs[0]["captures"]["primary"]["state"]["sha256"] == H2

    # Missing an unambiguous UTC instant is not evidence of a new version.
    state["robots"]["sample"]["resources"][url]["capture_history"] = history[-2:]
    jobs, deferred = select_reviewed_jobs(state, config)
    assert jobs == []
    assert deferred == [{"source_key": "sample-listed", "reason": "missing_verified_capture"}]


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


def test_existing_private_snapshot_reuses_complete_labelled_bytes_without_reparsing():
    from white_list_archive.acquisition.auto_transform import _reuse_existing_snapshot

    class Cursor:
        def __init__(self, matches):
            self.matches = matches
            self.statements = []
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, sql, values):
            self.statements.append((sql, values))
        def fetchall(self):
            return self.matches

    class Connection:
        def __init__(self, matches):
            self.current = Cursor(matches)
        def cursor(self):
            return self.current

    inputs = [
        {"label": "listed", "capture_id": "first"},
        {"label": "applicant", "capture_id": "second"},
    ]
    conn = Connection([("run-1", {"listed": H2, "applicant": H3})])
    assert _reuse_existing_snapshot(
        conn, parser_name="approved_parser", code_revision="f" * 40,
        configuration_hash=H1, capture_inputs=inputs,
        input_hashes={"listed": H2, "applicant": H3},
    )
    assert len(conn.current.statements) == 3
    assert conn.current.statements[1][1] == ("first", "run-1", "listed")
    assert conn.current.statements[2][1] == ("second", "run-1", "applicant")

    conn = Connection([("wrong", {"listed": H2})])
    assert not _reuse_existing_snapshot(
        conn, parser_name="approved_parser", code_revision="f" * 40,
        configuration_hash=H1, capture_inputs=inputs,
        input_hashes={"listed": H2, "applicant": H3},
    )
    assert len(conn.current.statements) == 1


def test_ambiguous_existing_parse_identity_fails_closed():
    from white_list_archive.acquisition.auto_transform import _reuse_existing_snapshot

    class Cursor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, sql, values):
            pass
        def fetchall(self):
            return [("one", {"primary": H2}), ("two", {"primary": H2})]
    class Connection:
        def cursor(self):
            return Cursor()

    with pytest.raises(ValueError, match="Multiple interpretation"):
        _reuse_existing_snapshot(
            Connection(), parser_name="approved_parser", code_revision="f" * 40,
            configuration_hash=H1,
            capture_inputs=[{"label": "primary", "capture_id": "capture"}],
            input_hashes={"primary": H2},
        )


def test_private_qa_flags_detect_drift_without_approving_publication():
    from white_list_archive.acquisition.auto_transform import _quality_flags

    flags = _quality_flags(
        {"expected_source_rows": 4, "expected_sector_rows": 5},
        [{"source_status": "listed"}, {"source_status": ""}],
        {"sector_rows": 7, "dropped_date_rows": 1},
    )
    assert flags == [
        "source_row_count_changed",
        "source_sector_count_changed",
        "source_date_rows_dropped",
        "missing_source_status",
    ]
    assert _quality_flags(
        {"expected_source_rows": 1},
        [{"source_status": "listed"}],
        {"dropped_date_rows": 0},
    ) == []


def test_database_readbacks_require_committed_capture_and_snapshot_identity():
    from white_list_archive.acquisition.auto_transform import (
        _check_capture_relational_readback, _check_snapshot_relational_readback,
    )

    class Cursor:
        def __init__(self, row):
            self.row = row
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, sql, args):
            self.args = args
        def fetchone(self):
            return self.row

    class Connection:
        def __init__(self, row):
            self.current = Cursor(row)
        def cursor(self):
            return self.current

    capture = Connection((H1, "durable"))
    _check_capture_relational_readback(capture, "capture-1", H1)
    assert capture.current.args == ("capture-1",)

    with pytest.raises(RuntimeError, match="Relational capture readback"):
        _check_capture_relational_readback(Connection((H2, "pending")), "capture-1", H1)
    _check_snapshot_relational_readback(
        Connection((H2, 6)), parse_run_id="run-1", digest=H2, record_count=6,
    )
    with pytest.raises(RuntimeError, match="Relational parse snapshot"):
        _check_snapshot_relational_readback(
            Connection((H2, 5)), parse_run_id="run-1", digest=H2, record_count=6,
        )


def test_automatic_pipeline_is_private_and_has_independent_catchup_trigger():
    from pathlib import Path

    workflow = (Path(__file__).resolve().parents[1] /
        ".github/workflows/transform-reviewed-captures.yml").read_text()
    assert "workflow_run:" in workflow
    assert "schedule:" in workflow
    assert "  push:" in workflow
    assert "ref: main" in workflow
    assert "needs: freeze-inputs" in workflow
    assert "ref: ${{ needs.freeze-inputs.outputs.code_revision }}" in workflow
    assert 'git show "$ROBOT_STATE_REVISION:state.json"' in workflow
    assert "git show FETCH_HEAD:state.json" not in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "contents: read" in workflow
    assert "environment: evidence-archive" in workflow
    assert "Retain aggregate public operational verification only" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "actions/deploy-pages" not in workflow
    assert "pages: write" not in workflow


def test_missing_private_database_reports_blocked_capture_instead_of_success(tmp_path, monkeypatch):
    import json

    from white_list_archive.acquisition.auto_transform import main

    state, config = _scalar()
    state_path = tmp_path / "state.json"
    config_path = tmp_path / "config.json"
    report = tmp_path / "status.json"
    state_path.write_text(json.dumps(state))
    config_path.write_text(json.dumps(config))
    monkeypatch.delenv("EVIDENCE_DATABASE_URL", raising=False)
    result = main([
        "--state", str(state_path),
        "--source-config", str(config_path),
        "--report", str(report),
        "--code-revision", "a" * 40,
    ])
    saved = json.loads(report.read_text())
    assert result == 1
    assert saved["changed_sources"] == 1
    assert saved["blocked"] == 1
    assert saved["transformed"] == 0
    assert saved["outcomes"] == [{
        "source_key": "sample-listed",
        "status": "blocked",
        "reason": "private_database_writer_unavailable",
        "capture_inputs": {"primary": {"capture_id": "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb", "sha256": H2}},
    }]
    assert saved["publications"] == 0


def test_actions_artifact_contains_only_aggregate_safe_operational_fields():
    from white_list_archive.acquisition.auto_transform import public_operational_summary

    report = {
        "schema_version": 1,
        "run_at": "2026-11-07T10:30:00+00:00",
        "shard": 0,
        "shards": 4,
        "changed_sources": 1,
        "transformed": 0,
        "reused": 0,
        "quarantined": 1,
        "blocked": 0,
        "deferred": 0,
        "database_verified": 0,
        "source_quality_flags": 1,
        "publications": 0,
        "outcomes": [{
            "source_key": "sensitive-source",
            "records": [{"company_name": "Not for public upload"}],
            "sha256": H2,
            "error_type": "ParserError",
        }],
        "deferred_reasons": {"internal_secret": 1},
    }
    output = public_operational_summary(report)
    text = __import__("json").dumps(output)
    assert output["quarantined"] == 1
    assert output["publications"] == 0
    assert "sensitive-source" not in text
    assert "company_name" not in text
    assert H2 not in text
    assert "outcomes" not in output
    assert "deferred_reasons" not in output

    report["publications"] = 1
    with pytest.raises(ValueError, match="never publish"):
        public_operational_summary(report)
