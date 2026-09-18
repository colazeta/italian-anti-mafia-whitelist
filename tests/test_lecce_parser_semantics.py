from __future__ import annotations

import pytest

from white_list_archive.parsers.lecce_tables import (
    _ALLOWED_NON_UPDATE_NOTES,
    _ALLOWED_UPDATE_RAW,
    _iso_if_valid,
    _status,
    _strict_identifiers,
)


def test_lecce_status_mapping_is_positive_evidence_only() -> None:
    assert _status("") == "listed"
    for value in _ALLOWED_UPDATE_RAW:
        assert _status(value) == "renewal_update_in_progress"
    for value in _ALLOWED_NON_UPDATE_NOTES:
        assert _status(value) == "listed"

    with pytest.raises(RuntimeError, match="unreviewed listed status/note"):
        _status("NUOVO STATO NON REVISIONATO")


def test_lecce_dates_preserve_malformed_source_typography() -> None:
    assert _iso_if_valid("09/09/2026") == "2026-09-09"
    assert _iso_if_valid("16/101/2026") == ""
    assert _iso_if_valid("09-apr") == ""
    assert _iso_if_valid("0 9/09/2026") == ""
    assert _iso_if_valid("2 8 / 0 8 /2026") == ""
    assert _iso_if_valid("14//04/2025") == ""


def test_lecce_identifier_extraction_retains_multiple_valid_tokens_without_repair() -> None:
    assert _strict_identifiers("SNSDDT71L13Z133V 05003150751") == [
        "SNSDDT71L13Z133V",
        "05003150751",
    ]
    assert _strict_identifiers("A62931142 P.I.05129800750") == ["05129800750"]
    assert _strict_identifiers("0507010759") == []
    assert _strict_identifiers("") == []
