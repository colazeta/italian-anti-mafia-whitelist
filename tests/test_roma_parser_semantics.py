from __future__ import annotations

import pytest

from white_list_archive.parsers.roma_positioned import (
    _APPLICANT_EXPECTED_STATUS_COUNTS,
    _APPLICANT_MISSING_DATE_IDS,
    _APPLICANT_PAGES,
    _APPLICANT_RECORDS,
    _APPLICANT_SHA256,
    _LISTED_EXPECTED_STATUS_COUNTS,
    _LISTED_MISSING_CORE_IDS,
    _LISTED_PAGES,
    _LISTED_RECORDS,
    _LISTED_SHA256,
    _REVIEWED_BAD_APPLICANT_DATES,
    _REVIEWED_BAD_LISTED_DATES,
    _strict_date,
)


def test_roma_byte_pinned_boundaries_are_frozen() -> None:
    assert _LISTED_SHA256 == "8a2bbdb210757a8e7bf1da74db4bd7440c4fc45b3198b09e225c0aee2e6ef4af"
    assert _APPLICANT_SHA256 == "9bf34641f92b7480492646f0ab442b47305438a06547e1739dafd324c2b1b32a"
    assert (_LISTED_PAGES, _LISTED_RECORDS) == (168, 2169)
    assert (_APPLICANT_PAGES, _APPLICANT_RECORDS) == (142, 2259)


def test_roma_status_denominators_are_source_bound() -> None:
    assert _LISTED_EXPECTED_STATUS_COUNTS == {
        "listed": 1215,
        "renewal_update_in_progress": 954,
    }
    assert _APPLICANT_EXPECTED_STATUS_COUNTS == {
        "pending": 2256,
        "renewal_update_in_progress": 3,
    }


def test_roma_missing_source_dates_are_preserved_not_inferred() -> None:
    assert len(_LISTED_MISSING_CORE_IDS) == 9
    assert len(_APPLICANT_MISSING_DATE_IDS) == 20
    assert "FRNPLG69L30H501X" in _LISTED_MISSING_CORE_IDS
    assert "NL001194082B01" in _APPLICANT_MISSING_DATE_IDS


def test_only_reviewed_roma_date_typography_is_tolerated() -> None:
    assert _REVIEWED_BAD_LISTED_DATES == {"28/01/205", "27/07/202"}
    assert _REVIEWED_BAD_APPLICANT_DATES == {"10/12/215", "23/04/201"}
    assert _strict_date(
        "14/09/2026", reviewed_bad=_REVIEWED_BAD_LISTED_DATES,
        source_key="roma-listed", page=1, row=1,
    ) == "2026-09-14"
    assert _strict_date(
        "28/01/205", reviewed_bad=_REVIEWED_BAD_LISTED_DATES,
        source_key="roma-listed", page=31, row=9,
    ) == ""
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _strict_date(
            "14-09-2026", reviewed_bad=_REVIEWED_BAD_LISTED_DATES,
            source_key="roma-listed", page=1, row=1,
        )
    with pytest.raises(RuntimeError, match="invalid calendar date"):
        _strict_date(
            "31/02/2026", reviewed_bad=_REVIEWED_BAD_LISTED_DATES,
            source_key="roma-listed", page=1, row=1,
        )
