from __future__ import annotations

import pytest

from white_list_archive.parsers.perugia_tables import (
    _APPLICANT_BARE_OUTCOME,
    _APPLICANT_BLANK_NAME,
    _APPLICANT_CONTINUATIONS,
    _APPLICANT_EMPTY_APPLICATION_ORDINALS,
    _APPLICANT_FORWARD_FRAGMENT,
    _APPLICANT_MISSING_DECISION_DATES,
    _APPLICANT_RECORDS,
    _APPLICANT_UNPARSED_APPLICATION,
    _EXPECTED_APPLICANT_STATUS_COUNTS,
    _EXPECTED_LISTED_STATUS_COUNTS,
    _EXPECTED_SECTION_ROWS,
    _LISTED_CONTINUATIONS,
    _LISTED_DATE_EXCEPTIONS,
    _LISTED_DATE_INVERSIONS,
    _LISTED_RECORDS,
    _LISTED_SECTION_ROWS,
    _applicant_status_and_decision,
    _calendar_date,
    _strict_identifier,
)


def test_perugia_source_denominators_and_statuses_are_frozen() -> None:
    assert _LISTED_SECTION_ROWS == 1854
    assert _LISTED_RECORDS == 1016
    assert _APPLICANT_RECORDS == 1213
    assert _EXPECTED_LISTED_STATUS_COUNTS == {
        "listed": 674,
        "renewal_update_in_progress": 342,
    }
    assert _EXPECTED_APPLICANT_STATUS_COUNTS == {
        "listed": 1036,
        "pending": 176,
        "other_or_unknown": 1,
    }
    assert _EXPECTED_SECTION_ROWS == {
        "I": 257,
        "II": 106,
        "III": 402,
        "IV": 138,
        "V": 441,
        "VI": 251,
        "VII": 12,
        "VIII": 9,
        "IX": 66,
        "X": 172,
    }


def test_perugia_reviewed_exception_populations_are_finite() -> None:
    assert len(_LISTED_CONTINUATIONS) == 8
    assert len(_LISTED_DATE_EXCEPTIONS) == 7
    assert len(_LISTED_DATE_INVERSIONS) == 5
    assert len(_APPLICANT_CONTINUATIONS) == 54
    assert _APPLICANT_FORWARD_FRAGMENT == (6, 6)
    assert _APPLICANT_EMPTY_APPLICATION_ORDINALS == {8, 149, 387, 650, 766, 900, 1196}
    assert set(_APPLICANT_UNPARSED_APPLICATION) == {689, 790, 810, 811, 812}
    assert set(_APPLICANT_MISSING_DECISION_DATES) == {73, 413, 951}
    assert set(_APPLICANT_BLANK_NAME) == {1052}
    assert set(_APPLICANT_BARE_OUTCOME) == {1026}


def test_perugia_identifiers_require_positive_source_evidence() -> None:
    assert _strict_identifier("03785310545") == "03785310545"
    assert _strict_identifier("NNCFNC69E11I921A") == "NNCFNC69E11I921A"
    assert _strict_identifier("0389625054 9") == "03896250549"
    assert _strict_identifier("not-a-positive-identifier") == ""
    assert _strict_identifier("") == ""


def test_perugia_calendar_parser_accepts_only_real_source_calendar_dates() -> None:
    assert _calendar_date("8/11/2018", context="test") == "8/11/2018"
    assert _calendar_date("05.12.2025", context="test") == "05.12.2025"
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _calendar_date("1°/04/2025", context="test")
    with pytest.raises(RuntimeError, match="invalid calendar date"):
        _calendar_date("31/02/2025", context="test")


def test_perugia_applicant_outcomes_do_not_infer_unlabelled_dates() -> None:
    assert _applicant_status_and_decision(1, "A", "") == ("pending", "")
    assert _applicant_status_and_decision(
        1,
        "A",
        "Rinnovo iscrizione in data 22/04/2026",
    ) == ("listed", "22/04/2026")
    assert _applicant_status_and_decision(
        1026,
        "BORGIONI PREFABBRICATI S.R.L.",
        "25/03/2026",
    ) == ("other_or_unknown", "")
    assert _applicant_status_and_decision(
        73,
        "F.LLI TENERINI SERGIO & ALVARO S.R.L.",
        "Rinnovo iscrizione in data",
    ) == ("listed", "")
    with pytest.raises(RuntimeError, match="unreviewed nonblank outcome"):
        _applicant_status_and_decision(1, "A", "25/03/2026")
