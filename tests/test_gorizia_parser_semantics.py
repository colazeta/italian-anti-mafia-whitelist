from __future__ import annotations

import pytest

from white_list_archive.parsers.gorizia_tables import (
    _EXPECTED_APPLICANT_IDENTIFIERS, _EXPECTED_APPLICANT_NAMES,
    _EXPECTED_LISTED_REGISTRATIONS, _EXPECTED_LISTED_SECTOR_ROWS,
    _EXPECTED_LISTED_STATUS_COUNTS, _REVIEWED_BLANK_EXPIRY_ROWS,
    _normalise_italian_date,
)

def test_gorizia_source_denominators_are_frozen() -> None:
    assert _EXPECTED_LISTED_SECTOR_ROWS == 186
    assert _EXPECTED_LISTED_REGISTRATIONS == 117
    assert _EXPECTED_LISTED_STATUS_COUNTS == {"listed": 86, "renewal_update_in_progress": 31}
    assert len(_EXPECTED_APPLICANT_IDENTIFIERS) == 10
    assert len(_EXPECTED_APPLICANT_NAMES) == 10
    assert len(_REVIEWED_BLANK_EXPIRY_ROWS) == 2

def test_gorizia_date_handling_is_fail_closed() -> None:
    assert _normalise_italian_date("24.06.2025") == "2025-06-24"
    assert _normalise_italian_date("1° giugno 2027") == "2027-06-01"
    assert _normalise_italian_date("2 1 aprile 2026") == "2026-04-21"
    assert _normalise_italian_date("Dal 10.12.202") == ""
    assert _normalise_italian_date("14 agosto 204") == ""
    with pytest.raises(RuntimeError, match="unexpected date lexeme"):
        _normalise_italian_date("10-12-2026")
