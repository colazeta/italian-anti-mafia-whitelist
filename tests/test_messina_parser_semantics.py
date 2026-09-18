from __future__ import annotations

import pytest

from white_list_archive.parsers.messina_tables import (
    _iso_if_valid,
    _listed_status,
    _sections,
    _strict_identifiers,
)


def test_messina_listed_status_mapping_uses_explicit_source_marker_only() -> None:
    assert _listed_status("") == "listed"
    assert _listed_status("SI") == "renewal_update_in_progress"
    with pytest.raises(RuntimeError, match="unreviewed listed update marker"):
        _listed_status("SCADUTA")


def test_messina_dates_are_calendar_valid_and_not_repaired() -> None:
    assert _iso_if_valid("10/09/2026") == "2026-09-10"
    assert _iso_if_valid("31/02/2026") == ""
    assert _iso_if_valid("10-09-2026") == ""
    assert _iso_if_valid("") == ""


def test_messina_identifier_extraction_preserves_multiple_tokens_and_blank() -> None:
    assert _strict_identifiers("02578720837 03122600830") == ["02578720837", "03122600830"]
    assert _strict_identifiers("RSSMRA80A01F158X") == ["RSSMRA80A01F158X"]
    assert _strict_identifiers("") == []


def test_messina_sections_are_source_encoded_and_fail_closed() -> None:
    assert _sections("I-III-IV-V-VI") == [
        "Sezione I",
        "Sezione III",
        "Sezione IV",
        "Sezione V",
        "Sezione VI",
    ]
    with pytest.raises(RuntimeError, match="unreviewed section encoding"):
        _sections("I; III")
