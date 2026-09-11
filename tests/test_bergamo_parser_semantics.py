from __future__ import annotations

import pytest

from white_list_archive.parsers.bergamo_positioned import (
    _APPLICANT_BLANK_ACTIVITY,
    _APPLICANT_BLANK_APPLICATIONS,
    _APPLICANT_PAGE_COUNTS,
    _APPLICANT_UNLABELLED_ACTIVITY,
    _LISTED_BLANK_ACTIVITY,
    _LISTED_PAGE_COUNTS,
    _LISTED_UNLABELLED_ACTIVITY,
    _section,
    _strict_date,
    _strict_identifiers,
    _targets,
)


def test_reviewed_denominators_are_frozen() -> None:
    assert len(_APPLICANT_PAGE_COUNTS) == 56
    assert sum(_APPLICANT_PAGE_COUNTS) == 612
    assert _APPLICANT_PAGE_COUNTS[0] == 10
    assert _APPLICANT_PAGE_COUNTS[-1] == 8
    assert len(_LISTED_PAGE_COUNTS) == 131
    assert sum(_LISTED_PAGE_COUNTS) == 1434
    assert _LISTED_PAGE_COUNTS[0] == 9
    assert _LISTED_PAGE_COUNTS[-1] == 6


def test_reviewed_source_exceptions_are_exact() -> None:
    assert len(_APPLICANT_BLANK_APPLICATIONS) == 12
    assert _APPLICANT_BLANK_ACTIVITY == {(11, 9)}
    assert _LISTED_BLANK_ACTIVITY == {(130, 9)}
    assert len(_APPLICANT_UNLABELLED_ACTIVITY) == 11
    assert len(_LISTED_UNLABELLED_ACTIVITY) == 47
    assert _APPLICANT_BLANK_ACTIVITY < _APPLICANT_UNLABELLED_ACTIVITY
    assert _LISTED_BLANK_ACTIVITY < _LISTED_UNLABELLED_ACTIVITY


def test_identifier_extraction_never_reconstructs_split_values() -> None:
    assert _strict_identifiers("04447980162/FRRGRL93T11B1 57V") == ["04447980162"]
    assert _strict_identifiers("000152050308") == []
    assert _strict_identifiers("03381740167 / 02175060161") == ["03381740167", "02175060161"]
    assert _strict_identifiers("FERRARI DAMIANO") == []


def test_date_parser_is_fail_closed_except_reviewed_blanks() -> None:
    assert _strict_date("27/08/2026", allow_blank=False, source_key="x", page=1, row=1) == "2026-08-27"
    assert _strict_date("", allow_blank=True, source_key="x", page=1, row=1) == ""
    with pytest.raises(RuntimeError, match="unexpected blank date"):
        _strict_date("", allow_blank=False, source_key="x", page=1, row=1)
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _strict_date("27.08.2026", allow_blank=False, source_key="x", page=1, row=1)
    with pytest.raises(RuntimeError, match="invalid calendar date"):
        _strict_date("31/02/2026", allow_blank=False, source_key="x", page=1, row=1)


def test_activity_section_is_never_inferred_when_prefix_is_missing() -> None:
    assert _section(
        "XII Servizi ambientali", reviewed_unlabelled=False, source_key="x", page=1, row=1
    ) == (["Sezione 12"], "XII Servizi ambientali")
    assert _section(
        "Fornitura di ferro lavorato", reviewed_unlabelled=True, source_key="x", page=25, row=6
    ) == ([], "Fornitura di ferro lavorato")
    assert _section("", reviewed_unlabelled=True, source_key="x", page=11, row=9) == ([], "")
    with pytest.raises(RuntimeError, match="unreviewed activity prefix"):
        _section("Servizi ambientali", reviewed_unlabelled=False, source_key="x", page=1, row=1)
    with pytest.raises(RuntimeError, match="unexpected blank activity"):
        _section("", reviewed_unlabelled=False, source_key="x", page=1, row=1)


def test_row_lattice_is_fixed_to_reviewed_geometry() -> None:
    assert _targets("applicant", 1, 3) == [117.3, 159.8, 202.3]
    assert _targets("applicant", 2, 3) == [54.2, 96.7, 139.2]
    assert _targets("listed", 1, 3) == [157.7, 200.2, 242.7]
    assert _targets("listed", 2, 3) == [73.0, 115.5, 158.0]
