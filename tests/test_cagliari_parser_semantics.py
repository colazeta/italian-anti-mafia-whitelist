from __future__ import annotations

import pytest

from white_list_archive.parsers.cagliari_tables import (
    _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE,
    _EXPECTED_APPLICANT_PAGE_COUNTS,
    _EXPECTED_APPLICANT_RECORDS,
    _EXPECTED_APPLICANT_STATUS_COUNTS,
    _EXPECTED_LISTED_IDENTIFIER_COVERAGE,
    _EXPECTED_LISTED_RECORDS,
    _EXPECTED_LISTED_STATUS_COUNTS,
    _EXPECTED_SECTOR_COUNTS,
    _EXPECTED_SECTOR_ROWS,
    _EXPECTED_SECTOR_STATUS_COUNTS,
    _parse_source_date,
    _requested_sections,
    _strict_identifiers,
)


def test_cagliari_source_denominators_are_frozen() -> None:
    assert _EXPECTED_SECTOR_ROWS == 1832
    assert sum(_EXPECTED_SECTOR_COUNTS.values()) == 1832
    assert _EXPECTED_SECTOR_COUNTS == {1: 263, 2: 117, 3: 297, 4: 125, 5: 348, 6: 266, 7: 53, 8: 33, 9: 62, 10: 268}
    assert _EXPECTED_SECTOR_STATUS_COUNTS == {"listed": 1723, "renewal_update_in_progress": 109}
    assert _EXPECTED_LISTED_RECORDS == 750
    assert _EXPECTED_LISTED_STATUS_COUNTS == {"listed": 713, "renewal_update_in_progress": 37}
    assert _EXPECTED_APPLICANT_PAGE_COUNTS == (40, 11)
    assert _EXPECTED_APPLICANT_RECORDS == 51
    assert _EXPECTED_APPLICANT_STATUS_COUNTS == {"pending": 51}
    assert _EXPECTED_LISTED_IDENTIFIER_COVERAGE == 749
    assert _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE == 50


def test_cagliari_dates_are_strict_and_calendar_valid() -> None:
    assert _parse_source_date("06/09/2026") == "2026-09-06"
    assert _parse_source_date("05/09/2027") == "2027-09-05"
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _parse_source_date("06-09-2026")
    with pytest.raises(RuntimeError, match="invalid calendar date"):
        _parse_source_date("31/02/2026")


def test_cagliari_identifiers_are_never_reconstructed() -> None:
    assert _strict_identifiers("03905700922") == ["03905700922"]
    assert _strict_identifiers("TZNSRG62D04B354Q") == ["TZNSRG62D04B354Q"]
    assert _strict_identifiers("0336817853") == []
    assert _strict_identifiers("3814850925") == []
    assert _strict_identifiers("") == []


def test_cagliari_requested_sections_are_explicit_only() -> None:
    assert _requested_sections("I,X") == ["Sezione 1", "Sezione 10"]
    assert _requested_sections("I,II,III,IV,V,VI") == [
        "Sezione 1", "Sezione 2", "Sezione 3", "Sezione 4", "Sezione 5", "Sezione 6"
    ]
    assert _requested_sections("") == []
    with pytest.raises(RuntimeError, match="unknown requested section token"):
        _requested_sections("XI")
