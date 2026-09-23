from __future__ import annotations

import pytest

from white_list_archive.storage.recovery_materialize import (
    _attach_capture_operator_evidence,
    apply_recovery_plan,
)


def repository_expectations():
    return {
        "schema_version": 1,
        "generated_at": "2026-09-23T12:00:00+00:00",
        "recovery_search_complete": False,
        "captures": [],
        "known_versions": [],
        "published_release_scopes": [],
    }


def capture_row(*, recovery_paths=None, durable_absence_confirmed=False,
                operator_evidence_refs=None, include_evidence_field=False):
    row = {
        "authority_key": "mutable",
        "capture": {
            "source_key": "mutable-listed",
            "capture_id": "11111111-1111-4111-8111-111111111111",
        },
        "catalogue": None,
        "recovery_paths": recovery_paths or [],
        "durable_absence_confirmed": durable_absence_confirmed,
    }
    if include_evidence_field:
        row["operator_evidence_refs"] = operator_evidence_refs or []
    return row


def plan(capture):
    return {
        "schema_version": 1,
        "generated_at": "2026-09-23T12:30:00+00:00",
        "recovery_search_complete": False,
        "captures": [capture],
        "known_version_recovery": [],
    }


def test_legacy_capture_without_operational_claim_remains_compatible():
    expectations = apply_recovery_plan(
        repository_expectations(),
        plan(capture_row()),
        source_authorities={"mutable-listed": "mutable"},
    )
    assert len(expectations["captures"]) == 1
    assert "operator_evidence_refs" not in expectations["captures"][0]


def test_capture_recovery_path_requires_operator_evidence_reference():
    with pytest.raises(ValueError, match="Capture operational recovery facts require operator_evidence_refs"):
        apply_recovery_plan(
            repository_expectations(),
            plan(capture_row(recovery_paths=["/private/recovery/original.pdf"])),
            source_authorities={"mutable-listed": "mutable"},
        )


def test_capture_durable_absence_requires_operator_evidence_reference():
    with pytest.raises(ValueError, match="Capture operational recovery facts require operator_evidence_refs"):
        apply_recovery_plan(
            repository_expectations(),
            plan(capture_row(durable_absence_confirmed=True)),
            source_authorities={"mutable-listed": "mutable"},
        )


def test_capture_operational_evidence_is_private_materialisation_metadata():
    reviewed = plan(
        capture_row(
            recovery_paths=["/private/recovery/original.pdf"],
            operator_evidence_refs=["operator:package-index:2026-09-23"],
            include_evidence_field=True,
        )
    )
    expectations = apply_recovery_plan(
        repository_expectations(),
        reviewed,
        source_authorities={"mutable-listed": "mutable"},
    )
    # The lower-level inventory input contract is unchanged; private decision evidence
    # is attached only to the private materialised report.
    assert "operator_evidence_refs" not in expectations["captures"][0]

    report = {
        "items": [
            {
                "identity_kind": "capture",
                "source_key": "mutable-listed",
                "capture_id": "11111111-1111-4111-8111-111111111111",
                "evidence_refs": [],
            },
            {
                "identity_kind": "known_version",
                "source_key": None,
                "capture_id": None,
                "evidence_refs": ["repository:historical-evidence"],
            },
        ]
    }
    result = _attach_capture_operator_evidence(report, reviewed)
    assert result["items"][0]["evidence_refs"] == ["operator:package-index:2026-09-23"]
    assert result["items"][1]["evidence_refs"] == ["repository:historical-evidence"]


def test_capture_evidence_references_must_be_non_empty_text():
    bad = capture_row(include_evidence_field=True)
    bad["operator_evidence_refs"] = [""]
    with pytest.raises(ValueError, match="Capture operator_evidence_refs"):
        apply_recovery_plan(
            repository_expectations(),
            plan(bad),
            source_authorities={"mutable-listed": "mutable"},
        )
