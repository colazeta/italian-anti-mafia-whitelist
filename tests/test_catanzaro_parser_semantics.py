from __future__ import annotations

import pytest

from white_list_archive.parsers.catanzaro_tables import (
    _APPLICANT_BYTES,
    _APPLICANT_PAGES,
    _APPLICANT_SHA256,
    _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE,
    _EXPECTED_APPLICANT_RECORDS,
    _EXPECTED_APPLICANT_STATUS_COUNTS,
    _EXPECTED_LISTED_IDENTIFIER_COVERAGE,
    _EXPECTED_LISTED_RECORDS,
    _EXPECTED_LISTED_SECTOR_ROWS,
    _EXPECTED_LISTED_SECTION_ROWS,
    _EXPECTED_LISTED_STATUS_COUNTS,
    _LISTED_BYTES,
    _LISTED_PAGES,
    _LISTED_SHA256,
    _REFERENCE_DATE,
    _parse_date,
    _strict_identifiers,
)


def test_catanzaro_byte_pinned_boundaries_are_frozen() -> None:
    assert _REFERENCE_DATE == "2026-09-10"
    assert (_LISTED_SHA256, _LISTED_BYTES, _LISTED_PAGES) == (
        "8578a1b2d3ef0e2d71f1133381082d63d131182fd1b74c456cffe708ed94df7f",
        619398,
        82,
    )
    assert (_APPLICANT_SHA256, _APPLICANT_BYTES, _APPLICANT_PAGES) == (
        "8c5b0ea684b20f0893016e4a528bac57fb2b05c40aa9669340bdf7bd7dab115c",
        338826,
        46,
    )


def test_catanzaro_denominators_are_source_bound() -> None:
    assert _EXPECTED_LISTED_SECTOR_ROWS == 1556
    assert _EXPECTED_LISTED_RECORDS == 610
    assert _EXPECTED_APPLICANT_RECORDS == 277
    assert _EXPECTED_LISTED_RECORDS + _EXPECTED_APPLICANT_RECORDS == 887
    assert _EXPECTED_LISTED_STATUS_COUNTS == {
        "listed": 377,
        "renewal_update_in_progress": 233,
    }
    assert _EXPECTED_APPLICANT_STATUS_COUNTS == {"pending": 277}
    assert _EXPECTED_LISTED_IDENTIFIER_COVERAGE == 601
    assert _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE == 272
    assert _EXPECTED_LISTED_SECTION_ROWS == {
        1: 254,
        2: 108,
        3: 394,
        4: 115,
        5: 388,
        6: 146,
        7: 1,
        8: 8,
        9: 18,
        10: 124,
    }


def test_catanzaro_identifier_handling_is_conservative() -> None:
    # Whitespace caused by PDF line wrapping is removed, while the explicit source slash is
    # retained as the only reason these are treated as two identifiers.
    assert _strict_identifiers("* FZAGTN83D07D969N/037022807 97") == [
        "FZAGTN83D07D969N",
        "03702280797",
    ]
    assert _strict_identifiers("* 04005810793") == ["04005810793"]
    # Do not split a malformed concatenation when the source provides no delimiter.
    assert _strict_identifiers("* TRPFNC66L25C352Q02012210 791") == []
    assert _strict_identifiers("*") == []


def test_catanzaro_dates_preserve_reviewed_source_anomalies_without_repair() -> None:
    assert _parse_date("23/07/2026", field="listing") == "2026-07-23"
    assert _parse_date("01/07/205", field="listing") == ""
    assert _parse_date("x", field="listing") == ""
    assert _parse_date("17/112026", field="expiry") == ""
    assert _parse_date("", field="expiry") == ""
    assert _parse_date("1/8/12/2025", field="applicant") == ""
    assert _parse_date("", field="applicant") == ""

    with pytest.raises(RuntimeError, match="unreviewed listing date typography"):
        _parse_date("23-07-2026", field="listing")
    with pytest.raises(RuntimeError, match="invalid calendar applicant date"):
        _parse_date("31/02/2026", field="applicant")
