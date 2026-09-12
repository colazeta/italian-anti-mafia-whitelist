from __future__ import annotations

import pytest

from white_list_archive.parsers.catania_openxml import (
    _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE,
    _EXPECTED_APPLICANT_RECORDS,
    _EXPECTED_APPLICANT_STATUS_COUNTS,
    _EXPECTED_LISTED_FORMULAS,
    _EXPECTED_LISTED_IDENTIFIER_COVERAGE,
    _EXPECTED_LISTED_RECORDS,
    _EXPECTED_LISTED_STANDARD_FORMULAS,
    _EXPECTED_LISTED_STATUS_COUNTS,
    _listed_status,
    _sections,
    _strict_date,
    _strict_identifiers,
)


def test_catania_source_denominators_are_frozen() -> None:
    assert _EXPECTED_LISTED_RECORDS == 1632
    assert _EXPECTED_APPLICANT_RECORDS == 324
    assert _EXPECTED_LISTED_STATUS_COUNTS == {
        "listed": 1281,
        "renewal_update_in_progress": 351,
    }
    assert _EXPECTED_APPLICANT_STATUS_COUNTS == {"pending": 324}
    assert _EXPECTED_LISTED_IDENTIFIER_COVERAGE == 1588
    assert _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE == 322
    assert _EXPECTED_LISTED_FORMULAS == 1491
    assert _EXPECTED_LISTED_STANDARD_FORMULAS == 1490


def test_catania_status_interpretation_requires_explicit_renewal_wording() -> None:
    assert _listed_status("") == "listed"
    assert _listed_status("richiesto rinnovo") == "renewal_update_in_progress"
    assert _listed_status("Richiesta rinnovo") == "renewal_update_in_progress"
    assert _listed_status("NI") == "listed"
    assert _listed_status("R") == "listed"


def test_catania_identifiers_are_never_repaired() -> None:
    assert _strict_identifiers("01234567890") == ["01234567890"]
    assert _strict_identifiers("RSSMRA80A01C351A") == ["RSSMRA80A01C351A"]
    assert _strict_identifiers("061411110871") == []
    assert _strict_identifiers("CCOSVT731C351M") == []


def test_catania_dates_are_calendar_strict() -> None:
    assert _strict_date("11/09/2026", context="test") == "2026-09-11"
    assert _strict_date("2026-09-11 00:00:00", context="test") == "2026-09-11"
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _strict_date("16/072026", context="test")
    with pytest.raises(RuntimeError, match="invalid calendar date"):
        _strict_date("31/02/2026", context="test")


def test_catania_sections_preserve_only_source_explicit_tokens() -> None:
    assert _sections("1, 5, 6", source_row=999, population="listed") == [
        "Sezione 1",
        "Sezione 5",
        "Sezione 6",
    ]
    assert _sections("1, 5, 6 10", source_row=350, population="listed") == [
        "Sezione 1",
        "Sezione 5",
    ]
    with pytest.raises(RuntimeError, match="reviewed section anomaly drift"):
        _sections("1, 5, 6, 10", source_row=350, population="listed")
    with pytest.raises(RuntimeError, match="unreviewed section value"):
        _sections("1, 11", source_row=999, population="listed")
