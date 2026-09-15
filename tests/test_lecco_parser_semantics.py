from __future__ import annotations

import pytest

from white_list_archive.parsers.lecco_rect_tables import (
    _APPLICANT_BYTES,
    _APPLICANT_PAGES,
    _APPLICANT_RECORDS,
    _APPLICANT_SHA256,
    _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE,
    _EXPECTED_APPLICANT_STATUS_COUNTS,
    _EXPECTED_LISTED_IDENTIFIER_COVERAGE,
    _EXPECTED_LISTED_STATUS_COUNTS,
    _LISTED_BYTES,
    _LISTED_PAGES,
    _LISTED_RECORDS,
    _LISTED_SHA256,
    _REFERENCE_DATE,
    _REVIEWED_BLANK_LISTED_ACTIVITIES,
    _REVIEWED_MALFORMED_LISTED_IDENTIFIERS,
    _sections,
    _strict_date,
    _strict_identifier,
)


def test_lecco_byte_pinned_boundaries_are_frozen() -> None:
    assert _REFERENCE_DATE == "2026-09-14"
    assert (_LISTED_SHA256, _LISTED_BYTES, _LISTED_PAGES, _LISTED_RECORDS) == (
        "80c439521cf2bd4062b54fff3646666487367f0f8b47c1a91a6c8f62bcf8e5bc",
        448763,
        19,
        230,
    )
    assert (_APPLICANT_SHA256, _APPLICANT_BYTES, _APPLICANT_PAGES, _APPLICANT_RECORDS) == (
        "7c24e015342cc2cb61cf4b5bf726621c8b3b90b195cd91c40942fc3ef6b6ba5b",
        235376,
        4,
        26,
    )
    assert _LISTED_RECORDS + _APPLICANT_RECORDS == 256


def test_lecco_status_and_identifier_denominators_are_source_bound() -> None:
    assert _EXPECTED_LISTED_STATUS_COUNTS == {
        "listed": 201,
        "renewal_update_in_progress": 29,
    }
    assert _EXPECTED_APPLICANT_STATUS_COUNTS == {
        "rejected_or_denied": 4,
        "pending": 22,
    }
    assert _EXPECTED_LISTED_IDENTIFIER_COVERAGE == 228
    assert _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE == 26


def test_lecco_reviewed_malformed_identifiers_are_not_repaired() -> None:
    assert _REVIEWED_MALFORMED_LISTED_IDENTIFIERS == {
        "BIGS di Ivan Chavarriaga": "0416200136",
        "Termoidraulica": "035180050137",
    }
    assert _strict_identifier("0416200136") == ""
    assert _strict_identifier("035180050137") == ""
    assert _strict_identifier("00333170132") == "00333170132"
    assert _strict_identifier("RSSMRA80A01H501Z") == "RSSMRA80A01H501Z"


def test_lecco_reviewed_blank_activity_is_explicit_and_not_inferred() -> None:
    assert _REVIEWED_BLANK_LISTED_ACTIVITIES == {"Termoidraulica"}


def test_lecco_activity_sections_accept_only_reviewed_section_tokens() -> None:
    assert _sections(
        "Sez. I Sez. III Sez. V Sez. VI Sez. X",
        source_key="lecco-listed",
        locator="p1:y481-543",
    ) == ["Sez. I", "Sez. III", "Sez. V", "Sez. VI", "Sez. X"]
    with pytest.raises(RuntimeError, match="unreviewed activity typography"):
        _sections(
            "Sez. I attività extra",
            source_key="lecco-listed",
            locator="p1:y481-543",
        )


def test_lecco_dates_are_strict_calendar_dates_with_reviewed_separators() -> None:
    assert _strict_date(
        "14.09.2026", source_key="lecco-listed", locator="p1:y1-2"
    ) == "2026-09-14"
    # One current listed row is source-printed with slash separators; preserve that
    # reviewed typography without broadening to arbitrary date formats.
    assert _strict_date(
        "09/02/2026", source_key="lecco-listed", locator="p2:y388-446"
    ) == "2026-02-09"
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _strict_date("14-09-2026", source_key="lecco-listed", locator="p1:y1-2")
    with pytest.raises(RuntimeError, match="invalid calendar date"):
        _strict_date("31.02.2026", source_key="lecco-listed", locator="p1:y1-2")
