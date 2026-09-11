from __future__ import annotations

import pytest

from white_list_archive.parsers.caltanissetta_tables import (
    _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE,
    _EXPECTED_APPLICANT_RECORDS,
    _EXPECTED_APPLICANT_STATUS_COUNTS,
    _EXPECTED_LISTED_IDENTIFIER_COVERAGE,
    _EXPECTED_LISTED_RECORDS,
    _EXPECTED_LISTED_STATUS_COUNTS,
    _listed_status,
    _parse_application_date,
    _parse_date,
    _strict_identifiers,
)


def test_caltanissetta_source_denominators_are_frozen() -> None:
    assert _EXPECTED_LISTED_RECORDS == 518
    assert _EXPECTED_LISTED_STATUS_COUNTS == {
        "listed": 281,
        "renewal_update_in_progress": 232,
        "other_or_unknown": 5,
    }
    assert _EXPECTED_APPLICANT_RECORDS == 288
    assert _EXPECTED_APPLICANT_STATUS_COUNTS == {"pending": 288}
    assert _EXPECTED_LISTED_IDENTIFIER_COVERAGE == 515
    assert _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE == 285


def test_caltanissetta_dates_are_strict_and_preserve_application_note() -> None:
    assert _parse_date("09/09/2026") == "2026-09-09"
    assert _parse_application_date("12/12/2016 (variazione compagine societaria)") == (
        "2016-12-12",
        "(variazione compagine societaria)",
    )
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _parse_date("09-09-2026")
    with pytest.raises(RuntimeError, match="invalid calendar date"):
        _parse_date("31/02/2026")


def test_caltanissetta_special_listed_statuses_are_not_reinterpreted() -> None:
    assert _listed_status("") == "listed"
    assert _listed_status("In corso di aggiornamento") == "renewal_update_in_progress"
    assert _listed_status("Misura di prevenzione collaborativa ex art. 94 bis del D. Lgs. 159/2011") == "other_or_unknown"
    assert _listed_status("SOSPESA (in corso di accertamenti)") == "other_or_unknown"


def test_caltanissetta_identifiers_are_never_reconstructed() -> None:
    assert _strict_identifiers("02095750853") == ["02095750853"]
    assert _strict_identifiers("NZLGPP66M07H281T") == ["NZLGPP66M07H281T"]
    assert _strict_identifiers("020826508502") == []
    assert _strict_identifiers("0143890854") == []
    assert _strict_identifiers("") == []
