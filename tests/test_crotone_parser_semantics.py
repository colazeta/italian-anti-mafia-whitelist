from __future__ import annotations

import pytest

from white_list_archive.parsers.crotone_tables import (
    _EXPECTED_APPLICANT_CONTINUATIONS,
    _EXPECTED_APPLICANT_RECORDS,
    _EXPECTED_APPLICANT_STATUS_COUNTS,
    _EXPECTED_LISTED_RECORDS,
    _EXPECTED_LISTED_SECTOR_ROWS,
    _EXPECTED_LISTED_STATUS_COUNTS,
    _normalise_address,
    _parse_date,
    _parse_expiry,
    _status,
    _strict_identifiers,
)


def test_crotone_source_denominators_are_frozen() -> None:
    assert _EXPECTED_LISTED_SECTOR_ROWS == 743
    assert _EXPECTED_LISTED_RECORDS == 328
    assert _EXPECTED_LISTED_STATUS_COUNTS == {"listed": 73, "renewal_update_in_progress": 255}
    assert _EXPECTED_APPLICANT_RECORDS == 180
    assert _EXPECTED_APPLICANT_STATUS_COUNTS == {"pending": 180}
    assert _EXPECTED_APPLICANT_CONTINUATIONS == 25


def test_crotone_italian_dates_are_strict_but_allow_source_ordinal() -> None:
    assert _parse_date("23 settembre 2025") == "2025-09-23"
    assert _parse_date("1° agosto 2025") == "2025-08-01"
    assert _parse_date("", allow_blank=True) == ""
    assert _parse_date("23 giungo 2025") == "2025-06-23"
    assert _parse_date("17 febbraio 2015 15 febbraio 2022") == ""
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _parse_date("24 giungo 2025")
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _parse_date("17 febbraio 2016 15 febbraio 2022")
    assert _parse_expiry("23 settembre 2026 Richiesta rinnovo") == (
        "2026-09-23",
        "Richiesta rinnovo",
    )
    assert _parse_expiry("7 dicembre2022 Richiesta rinnovo") == (
        "2022-12-07",
        "Richiesta rinnovo",
    )
    assert _parse_expiry("14 giungo 2022 Richiesta rinnovo") == (
        "2022-06-14",
        "Richiesta rinnovo",
    )
    with pytest.raises(RuntimeError, match="unreviewed expiry typography"):
        _parse_expiry("8 dicembre2022 Richiesta rinnovo")
    with pytest.raises(RuntimeError, match="unreviewed expiry typography"):
        _parse_expiry("15 giungo 2022 Richiesta rinnovo")
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _parse_date("23/09/2025")
    with pytest.raises(RuntimeError, match="invalid calendar date"):
        _parse_date("31 febbraio 2026")


def test_crotone_status_is_only_derived_from_explicit_source_words() -> None:
    assert _status("", "") == "listed"
    assert _status("Richiesta rinnovo", "istruttoria") == "renewal_update_in_progress"
    assert _status("", "aggiornamento") == "renewal_update_in_progress"


def test_crotone_identifiers_are_never_reconstructed() -> None:
    assert _strict_identifiers("02613630793") == ["02613630793"]
    assert _strict_identifiers("RSSMRA80A01H501U") == ["RSSMRA80A01H501U"]
    assert _strict_identifiers("VRTGPP43P20 E339O") == []
    assert _strict_identifiers("RLLGGR87M29 B774G/ 03332600794") == []
    assert _strict_identifiers("0330033796") == []


def test_crotone_address_normalisation_is_formatting_only() -> None:
    assert _normalise_address("Loc. Lipuda snc - CIRO’ MARINA (KR)") == _normalise_address(
        "Loc. Lipuda snc- CIRO’ MARINA (KR)"
    )
    assert _normalise_address("Via Roma 1") != _normalise_address("Via Roma 2")
