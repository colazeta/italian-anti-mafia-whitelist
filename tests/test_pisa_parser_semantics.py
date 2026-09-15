from __future__ import annotations

import pytest

from white_list_archive.parsers.pisa_tables import (
    _APPLICANT_BYTES,
    _APPLICANT_PAGES,
    _APPLICANT_RECORDS,
    _APPLICANT_SHA256,
    _EXPECTED_APPLICANT_STATUS_COUNTS,
    _EXPECTED_LISTED_STATUS_COUNTS,
    _EXPECTED_RENEWAL_STATUS_COUNTS,
    _LISTED_BYTES,
    _LISTED_PAGES,
    _LISTED_RECORDS,
    _LISTED_SHA256,
    _REFERENCE_DATE,
    _RENEWAL_BYTES,
    _RENEWAL_PAGES,
    _RENEWAL_RECORDS,
    _RENEWAL_SHA256,
    _REVIEWED_BLANK_LISTED_IDENTIFIER_NAME,
    _strict_date,
    _strict_identifier,
)


def test_pisa_byte_pinned_boundaries_are_frozen() -> None:
    assert _REFERENCE_DATE == "2026-09-08"
    assert (_LISTED_SHA256, _LISTED_BYTES, _LISTED_PAGES, _LISTED_RECORDS) == (
        "30eea93e542aea6ceb13bcfd4e3f1358e1c3f9cfb274b23e738dfb304b1dea23",
        169257,
        6,
        398,
    )
    assert (_APPLICANT_SHA256, _APPLICANT_BYTES, _APPLICANT_PAGES, _APPLICANT_RECORDS) == (
        "ed3bbf19670dbed899f6386836f4723898e4c20f9315e4d4297156fd1dcd6b12",
        68334,
        1,
        18,
    )
    assert (_RENEWAL_SHA256, _RENEWAL_BYTES, _RENEWAL_PAGES, _RENEWAL_RECORDS) == (
        "8658cd2e6048c44de18687b3933980778dd36bbf3721cd944063f61c0e2ceedb",
        73013,
        1,
        33,
    )


def test_pisa_status_denominators_are_source_bound() -> None:
    assert _EXPECTED_LISTED_STATUS_COUNTS == {"listed": 398}
    assert _EXPECTED_APPLICANT_STATUS_COUNTS == {"pending": 18}
    assert _EXPECTED_RENEWAL_STATUS_COUNTS == {"renewal_update_in_progress": 33}
    assert _LISTED_RECORDS + _APPLICANT_RECORDS + _RENEWAL_RECORDS == 449


def test_pisa_blank_foreign_identifier_is_reviewed_not_inferred() -> None:
    assert _REVIEWED_BLANK_LISTED_IDENTIFIER_NAME == "ROHDE NIELSEN A/S"
    assert _strict_identifier("") == ""
    assert _strict_identifier("02427880501") == "02427880501"
    assert _strict_identifier("RSSMRA80A01H501Z") == "RSSMRA80A01H501Z"
    assert _strict_identifier("02427 880501") == ""


def test_pisa_dates_are_strict_calendar_dates() -> None:
    assert _strict_date(
        "23/07/2026", source_key="pisa-listed", locator="p1:r2"
    ) == "2026-07-23"
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _strict_date("23-07-2026", source_key="pisa-listed", locator="p1:r2")
    with pytest.raises(RuntimeError, match="invalid calendar date"):
        _strict_date("31/02/2026", source_key="pisa-listed", locator="p1:r2")
