from __future__ import annotations

import pytest

from white_list_archive.parsers.udine_positioned import (
    _APPLICANT_PAGE_COUNTS,
    _EXPECTED_SECTION_HEADINGS,
    _LISTED_PAGE_COUNTS,
    _REVIEWED_BAD_DATES,
    _activity_codes,
    _strict_source_date,
)


def test_reviewed_udine_denominators_are_frozen() -> None:
    assert len(_LISTED_PAGE_COUNTS) == 64
    assert sum(_LISTED_PAGE_COUNTS) == 1431
    assert _APPLICANT_PAGE_COUNTS == (17, 2)
    assert sum(_APPLICANT_PAGE_COUNTS) == 19


def test_all_ten_source_sections_have_reviewed_transition_points() -> None:
    assert _EXPECTED_SECTION_HEADINGS == (
        (1, "I"), (11, "II"), (15, "III"), (26, "IV"), (31, "V"),
        (46, "VI"), (54, "VII"), (54, "VIII"), (56, "IX"), (58, "X"),
    )


def test_only_reviewed_malformed_date_is_tolerated() -> None:
    assert _REVIEWED_BAD_DATES == {"269/01/2027"}
    assert _strict_source_date("09/09/2026", page=1, row=1, source_key="udine-listed") == "2026-09-09"
    assert _strict_source_date("269/01/2027", page=1, row=1, source_key="udine-listed") == ""
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _strict_source_date("9/9/2026", page=1, row=1, source_key="udine-listed")
    with pytest.raises(RuntimeError, match="invalid calendar date"):
        _strict_source_date("32/01/2026", page=1, row=1, source_key="udine-listed")


def test_applicant_activity_codes_preserve_only_source_legend_codes() -> None:
    assert _activity_codes("A-C-D-E", page=1, row=1, source_key="udine-applicants") == ["A", "C", "D", "E"]
    assert _activity_codes("F", page=1, row=1, source_key="udine-applicants") == ["F"]
    assert _activity_codes("L", page=1, row=1, source_key="udine-applicants") == ["L"]
    with pytest.raises(RuntimeError, match="unreviewed activity code"):
        _activity_codes("Z", page=1, row=1, source_key="udine-applicants")
