from __future__ import annotations

import pytest

from white_list_archive.parsers.genova_tables import (
    _EXPECTED_APPLICANT_RECORDS,
    _EXPECTED_APPLICANT_SPLIT_ROWS,
    _EXPECTED_LISTED_RECORDS,
    _EXPECTED_LISTED_STATUS_COUNTS,
    _REVIEWED_APPLICANT_PAGE7_IDS,
    _applicant_outcome,
    _listed_status,
    _parse_observed_date,
    _sections,
    _strict_identifiers,
)


def test_genova_source_denominators_are_frozen() -> None:
    assert _EXPECTED_LISTED_RECORDS == 652
    assert _EXPECTED_LISTED_STATUS_COUNTS == {
        "listed": 528,
        "renewal_update_in_progress": 124,
    }
    assert _EXPECTED_APPLICANT_RECORDS == 110
    assert _EXPECTED_APPLICANT_SPLIT_ROWS == 6


def test_genova_status_vocabulary_is_fail_closed() -> None:
    assert _listed_status("") == "listed"
    assert _listed_status("IN FASE DI RINNOVO") == "renewal_update_in_progress"
    assert _listed_status("in fase di rinnovo") == "renewal_update_in_progress"
    assert _listed_status("I N FASE DI RINNOVO") == "renewal_update_in_progress"
    with pytest.raises(RuntimeError, match="unreviewed listed status"):
        _listed_status("RINNOVO")

    assert _applicant_outcome("") == ""
    assert _applicant_outcome("IN ISTRUTTORIA") == "IN ISTRUTTORIA"
    assert _applicant_outcome("I N ISTRUTTORIA") == "I N ISTRUTTORIA"
    with pytest.raises(RuntimeError, match="unreviewed applicant outcome"):
        _applicant_outcome("ACCOLTA")


def test_genova_identifiers_are_never_repaired() -> None:
    assert _strict_identifiers("01345600991") == ["01345600991"]
    assert _strict_identifiers("RSSMRA80A01D969A") == ["RSSMRA80A01D969A"]
    assert _strict_identifiers("018509000992") == []
    assert _strict_identifiers("2226130991") == []


def test_genova_sections_require_canonical_or_reviewed_source_evidence() -> None:
    assert _sections("Sez. I Sez. V Sez. X", scope="listed", name="TEST") == [
        "Sezione 1",
        "Sezione 5",
        "Sezione 10",
    ]
    assert _sections("Se. V", scope="listed", name="AMICO A. SRL") == ["Sezione 5"]
    assert _sections("Sex. IX", scope="applicant", name="S & C SRL") == ["Sezione 9"]
    with pytest.raises(RuntimeError, match="unreviewed White List section typography"):
        _sections("Sez. XI", scope="listed", name="TEST")
    with pytest.raises(RuntimeError, match="unreviewed White List section typography"):
        _sections("Se. V", scope="listed", name="ANOTHER COMPANY")


def test_genova_reviewed_invalid_dates_remain_raw_only() -> None:
    assert (
        _parse_observed_date(
            "26//09/2023", scope="listed", name="GENOVARENT SRL", field="listing"
        )
        == ""
    )
    assert (
        _parse_observed_date(
            "16/072026", scope="applicant", name="LO SCACCIA PENSIERI SRL", field="application"
        )
        == ""
    )
    with pytest.raises(RuntimeError, match="unreviewed date typography"):
        _parse_observed_date("26//09/2023", scope="listed", name="OTHER", field="listing")


def test_genova_page7_identity_reconstruction_is_exact() -> None:
    assert _REVIEWED_APPLICANT_PAGE7_IDS == {
        "CRESTA & DELFINO SRL": "01345600991",
        "CUNEO LUIGI": "01067080992",
        "CURZI LUIGI - AUTOTRASPORTI C/TERZI": "03185270109",
        "DAMA SRL": "02830520991",
        "DASSORI SRL": "02665830994",
        "DE BREEZE SRL": "03047520998",
    }
