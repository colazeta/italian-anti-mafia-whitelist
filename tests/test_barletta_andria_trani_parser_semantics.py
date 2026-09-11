from __future__ import annotations

import pytest

from white_list_archive.parsers.barletta_andria_trani_tables import (
    _EXPECTED_SECTOR_COUNTS,
    _EXPECTED_SECTOR_ROWS,
    _REVIEWED_BAD_DATES,
    _activity_sections,
    _parse_source_date,
    _strict_identifiers,
)


def test_reviewed_sector_denominator_is_frozen() -> None:
    assert _EXPECTED_SECTOR_ROWS == 1013
    assert sum(_EXPECTED_SECTOR_COUNTS.values()) == 1013
    assert set(_EXPECTED_SECTOR_COUNTS) == {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}


def test_source_dates_normalise_only_supported_typography() -> None:
    assert _parse_source_date("2/9/2026", source_key="barletta-listed", page=1, row=1) == "2026-09-02"
    assert _parse_source_date("22.05.2026", source_key="barletta-listed", page=1, row=1) == "2026-05-22"
    assert _parse_source_date("31/07/2026 Aggiornamento in corso", source_key="barletta-listed", page=80, row=2) == "2026-07-31"
    for value in _REVIEWED_BAD_DATES:
        assert _parse_source_date(value, source_key="barletta-listed", page=1, row=1) == ""
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _parse_source_date("2026/09/02", source_key="barletta-listed", page=1, row=1)
    with pytest.raises(RuntimeError, match="invalid calendar date"):
        _parse_source_date("32/01/2026", source_key="barletta-listed", page=1, row=1)


def test_reviewed_split_update_status_typography_is_frozen_in_parser_source() -> None:
    source = __import__("inspect").getsource(__import__("white_list_archive.parsers.barletta_andria_trani_tables", fromlist=["*"]).parse_barletta_andria_trani_listed)
    assert "aggiornament o" in source


def test_identifiers_are_exact_and_never_reconstructed() -> None:
    assert _strict_identifiers("P.IVA 07030880723") == ["07030880723"]
    assert _strict_identifiers("08658770725/ SPRMHL85H17A285E") == ["08658770725", "SPRMHL85H17A285E"]
    assert _strict_identifiers("0477750720") == []
    assert _strict_identifiers("C.F. MSCGPP72R08 Z110I") == []


def test_applicant_activity_sections_preserve_source_sections() -> None:
    assert _activity_sections("X – I – III – V - VI", source_key="barletta-applicants", page=1, row=1) == [
        "Sezione 10", "Sezione 1", "Sezione 3", "Sezione 5", "Sezione 6"
    ]
    with pytest.raises(RuntimeError, match="unresolved applicant activity"):
        _activity_sections("", source_key="barletta-applicants", page=1, row=1)
