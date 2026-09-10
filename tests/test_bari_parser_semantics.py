from __future__ import annotations

import pytest

from white_list_archive.parsers.bari_tables import (
    _APPLICANT_PAGE_COUNTS,
    _BAD_APPLICANT_DATES,
    _BAD_LISTED_DATES,
    _LISTED_PAGE_COUNTS,
    _applicant_row_repair,
    _listed_row_repair,
    _listed_status,
    _source_date,
    _strict_identifiers,
)


def test_reviewed_denominators_are_frozen() -> None:
    assert len(_LISTED_PAGE_COUNTS) == 29
    assert sum(_LISTED_PAGE_COUNTS) == 1065
    assert len(_APPLICANT_PAGE_COUNTS) == 14
    assert sum(_APPLICANT_PAGE_COUNTS) == 605


def test_identifier_extraction_is_conservative_and_preserves_multiple_exact_tokens() -> None:
    assert _strict_identifiers("08063610722 - LZZFNC81A10A662Y") == ["08063610722", "LZZFNC81A10A662Y"]
    assert _strict_identifiers("RGSNTN65M03I703N/04335410728") == ["RGSNTN65M03I703N", "04335410728"]
    assert _strict_identifiers("12345") == []


def test_only_reviewed_malformed_dates_are_tolerated() -> None:
    assert _source_date("31/08/2026", allowlist=_BAD_LISTED_DATES, source_key="bari-listed", page=1, row=1) == "2026-08-31"
    assert _source_date("19+/06/2027", allowlist=_BAD_LISTED_DATES, source_key="bari-listed", page=11, row=37) == ""
    assert _source_date("18/07/18 - 11/05/23", allowlist=_BAD_APPLICANT_DATES, source_key="bari-applicants", page=2, row=31) == ""
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _source_date("31.08.2026", allowlist=_BAD_LISTED_DATES, source_key="bari-listed", page=1, row=1)


def test_split_rows_are_reconstructed_only_at_reviewed_coordinates() -> None:
    blank_listed = [""] * 20
    listed = _listed_row_repair(19, 11, blank_listed)
    assert listed[0] == "MEDITRANS SRL"
    assert listed[4] == "05945400728"
    assert listed[16:20] == ["14/05/2025", "14/05/2026", "SI", "richiesta PERMANENZA"]

    blank_applicant = [""] * 18
    applicant = _applicant_row_repair(14, 5, blank_applicant)
    assert applicant[0] == "TRIDENTE DOMENICO"
    assert applicant[1] == "MOLFETTA"
    assert applicant[4] == "07151350720"
    assert applicant[16:18] == ["10/11/2023", "in istruttoria"]


def test_blank_listed_status_is_allowed_only_for_two_reviewed_source_rows() -> None:
    row = [""] * 20
    row[18] = "SI"
    assert _listed_status(row, page=23, row_number=13) == "renewal_update_in_progress"
    row[18] = ""
    assert _listed_status(row, page=24, row_number=20) == "listed"
    with pytest.raises(RuntimeError, match="unreviewed source status"):
        _listed_status(row, page=1, row_number=1)
