from __future__ import annotations

import pytest

from white_list_archive.parsers.frosinone_tables import (
    _EXPECTED_APPLICANT_FRAGMENT_ROWS,
    _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE,
    _EXPECTED_APPLICANT_RAW_IDENTIFIER_ONLY,
    _EXPECTED_APPLICANT_RECORDS,
    _EXPECTED_APPLICANT_STATUS_COUNTS,
    _EXPECTED_LISTED_FRAGMENT_ROWS,
    _EXPECTED_LISTED_IDENTIFIER_COVERAGE,
    _EXPECTED_LISTED_RAW_IDENTIFIER_ONLY,
    _EXPECTED_LISTED_RECORDS,
    _EXPECTED_LISTED_STATUS_COUNTS,
    _listed_status,
    _parse_date,
    _strict_identifiers,
)


def test_frosinone_source_denominators_are_frozen() -> None:
    assert _EXPECTED_LISTED_RECORDS == 761
    assert _EXPECTED_LISTED_STATUS_COUNTS == {"listed": 529, "renewal_update_in_progress": 232}
    assert _EXPECTED_LISTED_FRAGMENT_ROWS == 44
    assert _EXPECTED_LISTED_IDENTIFIER_COVERAGE == 737
    assert _EXPECTED_LISTED_RAW_IDENTIFIER_ONLY == 24
    assert _EXPECTED_APPLICANT_RECORDS == 475
    assert _EXPECTED_APPLICANT_STATUS_COUNTS == {"pending": 475}
    assert _EXPECTED_APPLICANT_FRAGMENT_ROWS == 5
    assert _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE == 473
    assert _EXPECTED_APPLICANT_RAW_IDENTIFIER_ONLY == 2


def test_frosinone_listed_status_vocabulary_is_fail_closed() -> None:
    assert _listed_status("") == "listed"
    assert _listed_status("Aggiornamento in corso per richiesta a permanere del 11/02/2026") == "renewal_update_in_progress"
    with pytest.raises(RuntimeError, match="unreviewed listed note/status"):
        _listed_status("RINNOVO IN CORSO")


def test_frosinone_dates_are_never_repaired() -> None:
    assert _parse_date("02/09/2026") == "2026-09-02"
    assert _parse_date("30/07/*2026") == ""
    assert _parse_date("224/02/2027") == ""
    assert _parse_date("24/02/20270") == ""
    assert _parse_date("13/05/206") == ""


def test_frosinone_identifiers_are_never_repaired() -> None:
    assert _strict_identifiers("03332660608") == ["03332660608"]
    assert _strict_identifiers("PGLLNZ94D01I838U") == ["PGLLNZ94D01I838U"]
    assert _strict_identifiers("0543034730") == []
    assert _strict_identifiers("003332660608") == []
