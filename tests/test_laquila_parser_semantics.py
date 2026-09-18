from __future__ import annotations

import pytest

from white_list_archive.parsers.laquila_tables import (
    PARSERS,
    _parse_source_date,
    _strict_identifier_coverage,
)


def test_laquila_parser_bindings_are_explicit() -> None:
    assert set(PARSERS) == {"laquila_listed", "laquila_applicants"}


def test_laquila_dates_are_calendar_valid_and_not_repaired() -> None:
    assert _parse_source_date("11/09/2026", source_key="test", field="date") == "2026-09-11"
    assert _parse_source_date("28/06/207", source_key="test", field="expiry", allow_reviewed_bad=True) == ""
    with pytest.raises(RuntimeError, match="unreviewed date date typography"):
        _parse_source_date("11-09-2026", source_key="test", field="date")


def test_laquila_identifier_boundary_does_not_repair_malformed_values() -> None:
    rows = [
        {"identifier_raw": "01234567890"},
        {"identifier_raw": "1373501007"},
        {"identifier_raw": "01234567890"},
    ]
    coverage, malformed, duplicates = _strict_identifier_coverage(rows)
    assert coverage == 2
    assert malformed == {"1373501007"}
    assert duplicates == {"01234567890"}
