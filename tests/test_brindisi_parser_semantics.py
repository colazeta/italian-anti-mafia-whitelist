from __future__ import annotations

import pytest

from white_list_archive.parsers.brindisi_tables import (
    _EXPECTED_APPLICANT_BLANK_DATES,
    _EXPECTED_APPLICANT_PAGE_COUNTS,
    _EXPECTED_LISTED_RECORDS,
    _EXPECTED_LISTED_STATUS_COUNTS,
    _EXPECTED_SECTOR_COUNTS,
    _EXPECTED_SECTOR_ROWS,
    _REVIEWED_BAD_DATES,
    _parse_source_date,
    _strict_identifiers,
)


def test_brindisi_source_denominators_are_frozen() -> None:
    assert _EXPECTED_SECTOR_ROWS == 830
    assert sum(_EXPECTED_SECTOR_COUNTS.values()) == 830
    assert set(_EXPECTED_SECTOR_COUNTS) == {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}
    assert _EXPECTED_LISTED_RECORDS == 385
    assert _EXPECTED_LISTED_STATUS_COUNTS == {"listed": 341, "renewal_update_in_progress": 44}
    assert _EXPECTED_APPLICANT_PAGE_COUNTS == (10, 15, 1)
    assert sum(_EXPECTED_APPLICANT_PAGE_COUNTS) == 26
    assert _EXPECTED_APPLICANT_BLANK_DATES == {(1, 1)}


def test_brindisi_dates_normalise_only_supported_typography() -> None:
    assert _parse_source_date("08-09-2026", source_key="brindisi-listed", page=1, row=1) == "2026-09-08"
    assert _parse_source_date("17.07.2027", source_key="brindisi-listed", page=1, row=1) == "2027-07-17"
    for value in _REVIEWED_BAD_DATES:
        assert _parse_source_date(value, source_key="brindisi-listed", page=1, row=1) == ""
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _parse_source_date("2026-09-08", source_key="brindisi-listed", page=1, row=1)
    with pytest.raises(RuntimeError, match="invalid calendar date"):
        _parse_source_date("32/01/2026", source_key="brindisi-listed", page=1, row=1)


def test_brindisi_identifiers_are_never_reconstructed() -> None:
    assert _strict_identifiers("02547390746") == ["02547390746"]
    assert _strict_identifiers("SCRGPP71M22D508U 02199210747") == ["SCRGPP71M22D508U", "02199210747"]
    assert _strict_identifiers("0274900747") == []
    assert _strict_identifiers("0275751044") == []
    assert _strict_identifiers("1833000746") == []
