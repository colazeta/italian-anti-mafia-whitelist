from copy import deepcopy

from white_list_archive.acquisition.reconcile_monitoring import reconcile_monitoring_state

RUN = "https://github.com/colazeta/italian-anti-mafia-whitelist/actions/runs/34327668707"
ACTIVATION = "docs/architecture/evidence-store-activation-2026-09-09.md"
VERIFIED_AT = "2026-09-09T08:10:49Z"


def _coverage():
    return {
        "scopes": [
            {"authority_key": "bari", "source_population_complete": True},
            {"authority_key": "udine", "source_population_complete": True},
            {"authority_key": "cosenza", "source_population_complete": True},
            {"authority_key": "milano", "source_population_complete": False},
        ]
    }


def _state():
    return {
        "prefectures": [
            {
                "authority_key": "bari",
                "population_scopes_complete": False,
                "durable_evidence_verified": False,
                "archived_evidence_storage_status": "not_documented",
                "unresolved_issue": [
                    "https://github.com/colazeta/italian-anti-mafia-whitelist/issues/20",
                    16,
                    20,
                ],
                "actionable_issue": True,
                "coverage_status": "BLOCKED",
                "last_completed_coverage_status": "SOURCE_IDENTIFIED",
                "evidence": ["old"],
            },
            {
                "authority_key": "udine",
                "population_scopes_complete": False,
                "durable_evidence_verified": False,
                "archived_evidence_storage_status": "not_documented",
                "unresolved_issue": [20],
                "actionable_issue": True,
                "coverage_status": "SOURCE_IDENTIFIED",
                "evidence": [],
            },
            {
                "authority_key": "cosenza",
                "population_scopes_complete": True,
                "durable_evidence_verified": False,
                "archived_evidence_storage_status": "workflow_artifact_ephemeral",
                "unresolved_issue": [
                    "https://github.com/colazeta/italian-anti-mafia-whitelist/issues/16"
                ],
                "actionable_issue": False,
                "coverage_status": "BLOCKED",
                "last_completed_coverage_stage": "VALIDATED",
                "evidence": ["capture"],
            },
            {
                "authority_key": "milano",
                "population_scopes_complete": False,
                "durable_evidence_verified": False,
                "archived_evidence_storage_status": "not_documented",
                "unresolved_issue": [20],
                "actionable_issue": True,
                "coverage_status": "SOURCE_IDENTIFIED",
                "evidence": [],
            },
        ],
        "operational_prerequisites": {
            "durable_evidence_storage": {
                "status": "NOT_PROVISIONED",
                "issue": 16,
                "verification_evidence": [],
                "verified_at": None,
                "required_action": "old",
            }
        },
    }


def _reconcile(state):
    return reconcile_monitoring_state(
        state,
        _coverage(),
        durable_storage_run_url=RUN,
        durable_storage_verified_at=VERIFIED_AT,
        activation_record=ACTIVATION,
    )


def test_reconciliation_closes_only_evidenced_population_gaps():
    state = _reconcile(_state())
    rows = {row["authority_key"]: row for row in state["prefectures"]}

    assert rows["bari"]["population_scopes_complete"] is True
    assert rows["bari"]["coverage_status"] == "SOURCE_IDENTIFIED"
    assert rows["bari"]["unresolved_issue"] == []
    assert rows["bari"]["actionable_issue"] is False

    assert rows["udine"]["population_scopes_complete"] is True
    assert rows["udine"]["unresolved_issue"] == []
    assert rows["udine"]["actionable_issue"] is False

    assert rows["milano"]["population_scopes_complete"] is False
    assert rows["milano"]["unresolved_issue"] == [20]
    assert rows["milano"]["actionable_issue"] is True


def test_reconciliation_records_live_cosenza_r2_gate_without_overclaiming_other_rows():
    state = _reconcile(_state())
    rows = {row["authority_key"]: row for row in state["prefectures"]}
    cosenza = rows["cosenza"]

    assert cosenza["durable_evidence_verified"] is True
    assert cosenza["archived_evidence_storage_status"] == "durable_r2_verified"
    assert cosenza["coverage_status"] == "VALIDATED"
    assert cosenza["unresolved_issue"] == []
    assert RUN in cosenza["evidence"]
    assert ACTIVATION in cosenza["evidence"]

    assert rows["udine"]["durable_evidence_verified"] is False

    storage = state["operational_prerequisites"]["durable_evidence_storage"]
    assert storage["status"] == "VERIFIED"
    assert storage["verified_at"] == VERIFIED_AT
    assert storage["verification_evidence"] == [RUN, ACTIVATION]
    assert storage["issue"] == 16
    assert "backup/restore" in storage["required_action"]


def test_reconciliation_is_idempotent():
    once = _reconcile(_state())
    twice = _reconcile(deepcopy(once))
    assert twice == once
