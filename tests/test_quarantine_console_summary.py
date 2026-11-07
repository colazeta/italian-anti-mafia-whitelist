"""Only verified complete receipt evidence can establish the maximum age."""
import json

import pytest

from white_list_archive.acquisition.auto_transform import quarantine_console_summary


def quarantined(age):
    return {"status": "quarantined", "source_key": "PRIVATE-SOURCE", "quarantine_age": age}


def test_verified_receipts_expose_only_aggregate_evidence():
    result = quarantine_console_summary([
        quarantined({"verified": True, "age_seconds": 12, "private_key": "PRIVATE-KEY"}),
        quarantined({"verified": True, "age_seconds": 0}),
        {"status": "parsed_private_review_required", "records": ["PRIVATE-ROW"]},
    ])
    assert result == {"quarantine_receipts_verified": 2, "quarantine_receipts_expected": 2,
                      "tracker_age_max_seconds": 12, "diagnostic_failures": 0}
    assert "PRIVATE" not in json.dumps(result)


@pytest.mark.parametrize("receipt", [None, {}, {"verified": False},
    {"verified": True}, {"verified": True, "age_seconds": None},
    {"verified": True, "age_seconds": -1}, {"verified": True, "age_seconds": True},
    {"verified": True, "age_seconds": "0"}, {"verified": 1, "age_seconds": 0}])
def test_missing_or_invalid_age_never_implies_zero_or_complete_verification(receipt):
    result = quarantine_console_summary([quarantined(receipt)])
    assert result == {"quarantine_receipts_verified": 0, "quarantine_receipts_expected": 1,
                      "tracker_age_max_seconds": None, "diagnostic_failures": 1}


def test_partial_receipt_coverage_cannot_claim_population_maximum():
    result = quarantine_console_summary([
        quarantined({"verified": True, "age_seconds": 5}), quarantined(None)])
    assert result["quarantine_receipts_verified"] == 1
    assert result["quarantine_receipts_expected"] == 2
    assert result["tracker_age_max_seconds"] is None
    assert result["diagnostic_failures"] == 1


def test_no_quarantine_has_unknown_age_and_report_failure_is_separate():
    result = quarantine_console_summary([], report_persistence_failed=True)
    assert result == {"quarantine_receipts_verified": 0, "quarantine_receipts_expected": 0,
                      "tracker_age_max_seconds": None, "diagnostic_failures": 1}
    assert quarantine_console_summary([])["diagnostic_failures"] == 0
