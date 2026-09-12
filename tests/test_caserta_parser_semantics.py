from __future__ import annotations

import pytest

from white_list_archive.parsers.caserta_tables import (
    _EXPECTED_APPLICANT_ID_TOKEN_DISTRIBUTION,
    _EXPECTED_APPLICANT_RECORDS,
    _EXPECTED_APPLICANT_STATUS_COUNTS,
    _EXPECTED_LISTED_ID_TOKEN_DISTRIBUTION,
    _EXPECTED_LISTED_RECORDS,
    _EXPECTED_LISTED_STATUS_COUNTS,
    _identifier_tokens,
    _listed_status,
    _parse_expiry,
    _parse_strict_date,
    _sections,
)


def test_caserta_source_denominators_are_frozen() -> None:
    assert _EXPECTED_LISTED_RECORDS == 950
    assert _EXPECTED_APPLICANT_RECORDS == 1208
    assert _EXPECTED_LISTED_STATUS_COUNTS == {
        "listed": 395,
        "renewal_update_in_progress": 548,
        "other_or_unknown": 7,
    }
    assert _EXPECTED_APPLICANT_STATUS_COUNTS == {"pending": 1208}
    assert _EXPECTED_LISTED_ID_TOKEN_DISTRIBUTION == {0: 46, 1: 804, 2: 100}
    assert _EXPECTED_APPLICANT_ID_TOKEN_DISTRIBUTION == {0: 125, 1: 1012, 2: 71}


def test_caserta_dates_are_strict_but_expiry_notes_are_preserved() -> None:
    assert _parse_strict_date("31/08/2026") == "2026-08-31"
    assert _parse_expiry("24/04/2027 fermo restando il permanere del Controllo Giudiziario") == (
        "2027-04-24",
        "fermo restando il permanere del Controllo Giudiziario",
    )
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _parse_strict_date("31-08-2026")
    with pytest.raises(RuntimeError, match="invalid calendar date"):
        _parse_strict_date("31/02/2026")


def test_caserta_statuses_do_not_reinterpret_special_conditions() -> None:
    assert _listed_status("") == "listed"
    assert _listed_status("In aggiornamento") == "renewal_update_in_progress"
    assert _listed_status("Prevenzione collaborativa ex art 94 bis per anni 1") == "other_or_unknown"
    assert _listed_status("16/09/2026") == "other_or_unknown"


def test_caserta_identifiers_are_extracted_only_when_source_explicit() -> None:
    assert _identifier_tokens("03430130611") == ["03430130611"]
    assert _identifier_tokens("FLCCLN65C26G333J 04559850617") == ["FLCCLN65C26G333J", "04559850617"]
    assert _identifier_tokens("06284440580 / 01523021002") == ["06284440580", "01523021002"]
    assert _identifier_tokens("0414550614") == []
    assert _identifier_tokens("") == []


def test_caserta_sections_accept_source_delimiters_but_not_invent_values() -> None:
    assert _sections("1-3-5-", index=10, population="listed") == ["Sezione 1", "Sezione 3", "Sezione 5"]
    assert _sections("2 - 4 - 5 - 10 -", index=14, population="listed") == [
        "Sezione 2",
        "Sezione 4",
        "Sezione 5",
        "Sezione 10",
    ]
    assert _sections("45721", index=190, population="listed") == []
    with pytest.raises(RuntimeError, match="reviewed section drift"):
        _sections("5", index=190, population="listed")
    with pytest.raises(RuntimeError, match="unreviewed section value"):
        _sections("11", index=9999, population="listed")
