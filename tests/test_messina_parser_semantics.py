from __future__ import annotations

import pytest

from white_list_archive.parsers.messina_tables import (
    _applicant_source_fields,
    _iso_if_valid,
    _listed_source_fields,
    _listed_status,
    _sections,
    _strict_identifiers,
)
from white_list_archive.publishing.public_contract import SOURCE_FIELDS


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
    assert _sections("I -II-III-IV-V-VII") == [
        "Sezione I",
        "Sezione II",
        "Sezione III",
        "Sezione IV",
        "Sezione V",
        "Sezione VII",
    ]
    assert _sections("III - V - IX") == ["Sezione III", "Sezione V", "Sezione IX"]
    with pytest.raises(RuntimeError, match="unreviewed section encoding"):
        _sections("I; III")


def test_messina_source_fields_remain_inside_closed_public_contract() -> None:
    listed = _listed_source_fields("I-III", "01/01/2026", "01/01/2027", "SI")
    applicant = _applicant_source_fields("III-IV", "02/01/2026")

    assert set(listed) <= SOURCE_FIELDS
    assert set(applicant) <= SOURCE_FIELDS
    assert listed == {
        "requested_activities_source": "I-III",
        "listing_date_raw_variants": ["01/01/2026"],
        "expiry_date_raw_variants": ["01/01/2027"],
        "in_aggiornamento": "SI",
    }
    assert applicant == {
        "requested_activities_source": "III-IV",
        "application_date_raw": "02/01/2026",
    }
