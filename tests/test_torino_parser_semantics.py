from __future__ import annotations

import pytest

from white_list_archive.parsers.torino_tables import (
    _APPLICANT_BYTES,
    _APPLICANT_PAGES,
    _APPLICANT_RECORDS,
    _APPLICANT_SHA256,
    _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE,
    _EXPECTED_APPLICANT_STATUS_COUNTS,
    _EXPECTED_LISTED_APPLICATION_DATE_COVERAGE,
    _EXPECTED_LISTED_EXPIRY_DATE_COVERAGE,
    _EXPECTED_LISTED_IDENTIFIER_COVERAGE,
    _EXPECTED_LISTED_LISTING_DATE_COVERAGE,
    _EXPECTED_LISTED_STATUS_COUNTS,
    _LISTED_BYTES,
    _LISTED_PAGES,
    _LISTED_RECORDS,
    _LISTED_SHA256,
    _REFERENCE_DATE,
    _REVIEWED_ACTIVITY_TYPOGRAPHY,
    _REVIEWED_MALFORMED_LISTED_IDENTIFIER_FIELDS,
    _REVIEWED_NOTES,
    _activities,
    _identifier_residue,
    _strict_date,
    _strict_identifiers,
)


def test_torino_byte_pinned_source_boundaries_are_frozen() -> None:
    assert _REFERENCE_DATE == "2026-09-11"
    assert (_LISTED_SHA256, _LISTED_BYTES, _LISTED_PAGES, _LISTED_RECORDS) == (
        "5c8341cd984de01f6472e049b9fa22569798ebc41761e6f85763796c8a90ba0d",
        2967519,
        37,
        1501,
    )
    assert (_APPLICANT_SHA256, _APPLICANT_BYTES, _APPLICANT_PAGES, _APPLICANT_RECORDS) == (
        "f84d6da09090d557ba85cd216bc1e4962935f0f43ddb2614e77995b613ed2f51",
        676216,
        7,
        162,
    )
    assert _LISTED_RECORDS + _APPLICANT_RECORDS == 1663


def test_torino_status_identifier_and_date_denominators_are_source_bound() -> None:
    assert _EXPECTED_LISTED_STATUS_COUNTS == {
        "listed": 1237,
        "renewal_update_in_progress": 264,
    }
    assert _EXPECTED_APPLICANT_STATUS_COUNTS == {"pending": 162}
    assert _EXPECTED_LISTED_IDENTIFIER_COVERAGE == 1496
    assert _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE == 162
    assert _EXPECTED_LISTED_APPLICATION_DATE_COVERAGE == 260
    assert _EXPECTED_LISTED_LISTING_DATE_COVERAGE == 1500
    assert _EXPECTED_LISTED_EXPIRY_DATE_COVERAGE == 1501


def test_torino_combined_identifier_fields_extract_only_strict_source_tokens() -> None:
    assert _strict_identifiers("CSTGLI87M55L727I-11572420013") == [
        "CSTGLI87M55L727I",
        "11572420013",
    ]
    assert _strict_identifiers("ZZLCST90E21D208O/11566290018") == [
        "ZZLCST90E21D208O",
        "11566290018",
    ]
    assert _strict_identifiers("GLVVTR77S12L219-08560640016") == ["08560640016"]
    assert _identifier_residue("GLVVTR77S12L219-08560640016") == "GLVVTR77S12L219"
    assert _strict_identifiers("0526550017") == []


def test_torino_reviewed_malformed_identifier_fields_are_not_repaired() -> None:
    assert _REVIEWED_MALFORMED_LISTED_IDENTIFIER_FIELDS == {
        "BENA SNC": "0526550017",
        "CAL.E.S.A. SRL": "6197640011",
        "EDIL TRIVAL SRLS": "1228500019",
        "G.V. TRASPORTI DI GALVAGNO VITTORIO": "GLVVTR77S12L219-08560640016",
        "ORIGLIA SERGIO AZIENDA AGRICOLA": "RGLSRG67C31777X-07050560015",
        "PICCO BARTOLOMEO SRL": "1280650050",
        "SOCIETA’ COOPERATIVA EUROPA": "9800980014",
    }


def test_torino_activity_parser_is_strict_with_two_byte_pinned_typography_exceptions() -> None:
    assert _REVIEWED_ACTIVITY_TYPOGRAPHY == {
        "DUAL SRL": "I - III - V-VI-X",
        "EDIL VIO SAS": "I--II-III-V",
    }
    assert _activities("I-III-VI-X", name="X", source_key="torino-listed", locator="p1:r1") == [
        "Sezione I", "Sezione III", "Sezione VI", "Sezione X"
    ]
    assert _activities(
        "I - III - V-VI-X", name="DUAL SRL", source_key="torino-listed", locator="p13:r2"
    ) == ["Sezione I", "Sezione III", "Sezione V", "Sezione VI", "Sezione X"]
    assert _activities(
        "I--II-III-V", name="EDIL VIO SAS", source_key="torino-listed", locator="p14:r12"
    ) == ["Sezione I", "Sezione II", "Sezione III", "Sezione V"]
    with pytest.raises(RuntimeError, match="unreviewed activity typography"):
        _activities("I - III", name="UNREVIEWED", source_key="torino-listed", locator="p1:r1")


def test_torino_dates_are_strict_and_blank_only_when_caller_allows_it() -> None:
    assert _strict_date("11/09/2026", source_key="torino-listed", locator="p1:r1") == "2026-09-11"
    assert _strict_date("", source_key="torino-listed", locator="p1:r1") == ""
    with pytest.raises(RuntimeError, match="required date is blank"):
        _strict_date("", source_key="torino-applicants", locator="p1:r1", required=True)
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _strict_date("11-09-2026", source_key="torino-listed", locator="p1:r1")
    with pytest.raises(RuntimeError, match="invalid calendar date"):
        _strict_date("31/02/2026", source_key="torino-listed", locator="p1:r1")


def test_torino_reviewed_annotations_are_preserved_as_notes_not_status_overrides() -> None:
    assert _REVIEWED_NOTES == {
        "“iscrizione ai sensi dell’art.34 bis del d.lgs. n.159/2011”",
        '"iscrizione ai sensi dell’art. 94 bis d.lgs. 159/2011"',
    }
