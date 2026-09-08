import csv
from copy import deepcopy
import json
from pathlib import Path

import pytest

from white_list_archive.acquisition.operations import GATES, mode_for, priority_queue, record_check, transition, validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def ledger():
    return json.loads((ROOT / "data/monitoring/national_coverage.json").read_text())


def test_national_ledger_matches_existing_authorities_and_preserves_public_boundary(ledger):
    with (ROOT / "data/source_registry/territorial_authorities.csv").open() as f:
        keys = {r["authority_key"] for r in csv.DictReader(f)}
    validate(ledger, keys)
    assert len(keys) == 106
    assert {r["authority_key"] for r in ledger["prefectures"] if r["public_export_enabled"]} == {"cosenza", "bologna", "parma", "pistoia"}
    assert ledger["mode"] == "EXPANSION_MODE"
    assert not any(r["coverage_status"] == "PUBLISHED" for r in ledger["prefectures"])


def complete(ledger):
    result = deepcopy(ledger)
    for row in result["prefectures"]:
        row.update({key: True for key in GATES})
        row.update(coverage_status="PUBLISHED", completion_evidence=["test-fixture-only"])
    return transition(result, "2026-09-09T10:00:00Z")


def test_transition_requires_every_authority_and_all_gates(ledger):
    done = complete(ledger)
    assert done["mode"] == "MAINTENANCE_MODE"
    assert done["mode_transitions"][-1]["from"] == "EXPANSION_MODE"
    done["prefectures"][-1]["durable_evidence_verified"] = False
    assert mode_for(done["prefectures"]) == "EXPANSION_MODE"
    with pytest.raises(ValueError, match="Unjustified terminal"):
        validate(done, {r["authority_key"] for r in done["prefectures"]})


def test_no_change_rotates_stalest_first_without_altering_editions(ledger):
    done = complete(ledger)
    for row in done["prefectures"]:
        row.update(last_successful_source_check_at="2026-09-08T12:00:00Z", last_attempted_source_check_at="2026-09-08T12:00:00Z", known_content_sha256=["a" * 64], monitoring_status="CURRENT")
    first = done["prefectures"][-1]
    first.update(last_successful_source_check_at="2026-09-01T12:00:00Z",latest_source_reference_date="2026-09-01")
    assert priority_queue(done)[0] == first
    after = record_check(done, first["authority_key"], at="2026-09-09T12:00:00Z", evidence="fixture", content_sha256=["a" * 64])
    assert priority_queue(after)[0]["authority_key"] != first["authority_key"]
    updated = after["prefectures"][-1]
    assert updated["latest_source_reference_date"] == "2026-09-01"
    assert updated["last_content_change_at"] is None
    assert after["checks"][-1]["content_changed"] is False
    assert done["checks"] == ledger["checks"]


def test_failed_check_keeps_last_success_and_known_bytes(ledger):
    row = next(r for r in ledger["prefectures"] if r["authority_key"] == "cosenza")
    after = record_check(ledger, "cosenza", at="2026-09-09T12:00:00Z", evidence="fixture", error="403")
    updated = next(r for r in after["prefectures"] if r["authority_key"] == "cosenza")
    assert updated["monitoring_status"] == "CHECK_FAILED"
    assert updated["last_successful_source_check_at"] == row["last_successful_source_check_at"]
    assert updated["known_content_sha256"] == row["known_content_sha256"]
    with pytest.raises(ValueError, match="advance"):
        record_check(after, "cosenza", at="2026-09-09T12:00:00Z", evidence="fixture", error="403")


def test_new_content_does_not_publish_or_overwrite_the_previous_check(ledger):
    after = record_check(ledger, "cosenza", at="2026-09-09T12:00:00Z", evidence="fixture", content_sha256=["b" * 64])
    again = record_check(after, "cosenza", at="2026-09-10T12:00:00Z", evidence="fixture", content_sha256=["b" * 64])
    row = next(r for r in again["prefectures"] if r["authority_key"] == "cosenza")
    assert row["monitoring_status"] == "SOURCE_CHANGED"
    assert row["last_content_change_at"] == "2026-09-09T12:00:00Z"
    assert row["latest_source_reference_date"] == "2026-08-03"
    assert len(again["checks"]) == len(ledger["checks"]) + 2


def test_expansion_prioritises_existing_validated_work_then_actionable_issues(ledger):
    for row in ledger["prefectures"]:
        if row["public_export_enabled"]:
            row["coverage_status"] = "VALIDATED"
    assert priority_queue(ledger)[0]["authority_key"] == "cosenza"
    for row in ledger["prefectures"]:
        if row["public_export_enabled"]:
            row["coverage_status"] = "BLOCKED"
    assert priority_queue(ledger)[0]["actionable_issue"]


def test_unknown_stale_or_missing_monitoring_data_fails_closed(ledger):
    keys = {r["authority_key"] for r in ledger["prefectures"]}
    ledger["prefectures"][0]["monitoring_status"] = "CURRENT"
    with pytest.raises(ValueError, match="successful evidence"):
        validate(ledger, keys)
    ledger["prefectures"].pop()
    with pytest.raises(ValueError, match="every canonical"):
        validate(ledger, keys)


def test_failure_between_changed_and_unchanged_checks_cannot_hide_pending_update(ledger):
    changed = record_check(ledger, "cosenza", at="2026-09-09T12:00:00Z", evidence="fixture", content_sha256=["c" * 64])
    failed = record_check(changed, "cosenza", at="2026-09-10T12:00:00Z", evidence="fixture", error="timeout")
    checked = record_check(failed, "cosenza", at="2026-09-11T12:00:00Z", evidence="fixture", content_sha256=["c" * 64])
    row = next(r for r in checked["prefectures"] if r["authority_key"] == "cosenza")
    assert row["source_update_pending"] is True
    assert row["monitoring_status"] == "SOURCE_CHANGED"
    assert row["last_content_change_at"] == "2026-09-09T12:00:00Z"
