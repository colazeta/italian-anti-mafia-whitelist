from __future__ import annotations

import pytest

from white_list_archive.parsers import lodi_sheets as lodi


def test_lodi_source_and_record_denominators_are_frozen() -> None:
    assert lodi._LISTED_PHYSICAL_ROWS == 324
    assert lodi._LISTED_SOURCE_ROWS == 291
    assert lodi._LISTED_RECORDS == 169
    assert lodi._APPLICANT_PHYSICAL_ROWS == 8
    assert lodi._APPLICANT_RECORDS == 4
    assert lodi._LISTED_RECORDS + lodi._APPLICANT_RECORDS == 173


def test_lodi_content_identity_and_observation_date_are_frozen() -> None:
    assert lodi._REFERENCE_DATE == "2026-09-15"
    assert lodi._LISTED_SHA256 == "ad64ab8669084bc31b80938a384b41849be4db28b448e9b2c0ce199f6af1d6ec"
    assert lodi._APPLICANT_SHA256 == "55aeab7e809cb90cc1ebd1ad9c1f08db78e91648a2c2e1a2b603188c77846228"


def test_lodi_listed_section_and_status_boundaries_are_frozen() -> None:
    assert lodi._EXPECTED_SECTION_ROWS == {
        "I": 44,
        "II": 24,
        "III": 47,
        "IV": 18,
        "V": 55,
        "VI": 54,
        "VII": 6,
        "VIII": 1,
        "IX": 3,
        "X": 39,
    }
    assert lodi._EXPECTED_LISTED_SOURCE_STATUS_COUNTS == {
        "listed": 254,
        "renewal_update_in_progress": 37,
    }
    assert lodi._EXPECTED_LISTED_STATUS_COUNTS == {
        "listed": 146,
        "renewal_update_in_progress": 23,
    }
    assert lodi._EXPECTED_APPLICANT_STATUS_COUNTS == {
        "rejected_or_denied": 2,
        "pending": 2,
    }


def test_lodi_listed_structure_and_grouping_are_frozen() -> None:
    assert lodi._LISTED_SECTION_ROWS == {
        3: "I",
        50: "II",
        77: "III",
        127: "IV",
        148: "V",
        206: "VI",
        263: "VII",
        272: "VIII",
        276: "IX",
        283: "X",
    }
    assert lodi._LISTED_BLANK_ROWS == {282}
    assert lodi._LISTED_ACTIVITY_ROWS == {4, 51, 78, 128, 149, 207, 264, 273, 277, 284}
    assert lodi._LISTED_HEADER_ROWS == {5, 52, 79, 129, 150, 208, 265, 274, 278, 285}
    assert lodi._EXPECTED_GROUP_OCCURRENCES == {
        1: 108,
        2: 32,
        3: 14,
        4: 5,
        5: 6,
        6: 2,
        7: 1,
        8: 1,
    }


def test_lodi_applicant_structure_is_frozen() -> None:
    assert lodi._APPLICANT_TITLE_ROWS == {1, 2}
    assert lodi._APPLICANT_BLANK_ROWS == {3}
    assert lodi._APPLICANT_HEADER_ROWS == {4}


def test_lodi_positive_identifier_extraction_is_conservative() -> None:
    assert lodi._positive_identifiers("03554730790") == ["03554730790"]
    assert lodi._positive_identifiers("RSSMRA80A01H501U") == ["RSSMRA80A01H501U"]
    assert lodi._positive_identifiers("035547307900") == []
    assert lodi._positive_identifiers("P.IVA 03554730790") == ["03554730790"]


def test_lodi_dates_fail_closed() -> None:
    assert lodi._calendar_date("07/09/2026", context="test") == "07/09/2026"
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        lodi._calendar_date("7/09/2026", context="test")
    with pytest.raises(RuntimeError, match="invalid calendar date"):
        lodi._calendar_date("31/02/2026", context="test")


def test_lodi_denial_outcome_requires_exact_reviewed_shape() -> None:
    match = lodi._DENIAL.fullmatch(
        "CHIUSA CON PROVV. INTERDITTIVO DI DINIEGO DELL'ISCRIZIONE IN WHITE LIST IL 17/06/2021"
    )
    assert match is not None
    assert match.group(1) == "17/06/2021"
    assert lodi._DENIAL.fullmatch("DINIEGO 17/06/2021") is None
