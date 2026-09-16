from __future__ import annotations

from white_list_archive.parsers.sassari_openxml import (
    _BYTE_COUNT,
    _EXPECTED_HEADER_ROW,
    _EXPECTED_IDENTIFIER_COVERAGE,
    _EXPECTED_RAW_IDENTIFIER_ONLY,
    _EXPECTED_STATUS_COUNTS,
    _EXPECTED_TABLE_SHEET,
    _EXPECTED_WORKSHEETS,
    _RECORD_COUNT,
    _REFERENCE_DATE,
    _REVIEWED_COLUMN_SWAP,
    _REVIEWED_MALFORMED_APPLICATION_DATE,
    _REVIEWED_MALFORMED_IDENTIFIER_FIELDS,
    _REVIEWED_NONSTANDARD_STATUSES,
    _SHA256,
    _source_date,
    _status,
)


def test_sassari_byte_pinned_source_boundary_is_frozen() -> None:
    assert _REFERENCE_DATE == "2026-08-31"
    assert _SHA256 == "e5cf9776971e4c0b46b97c56e2764f906bd07e3d573ac07b59fcd6605ab9c370"
    assert _BYTE_COUNT == 123745
    assert _RECORD_COUNT == 478
    assert _EXPECTED_WORKSHEETS == ("Foglio1", "Foglio2", "Foglio3", "Foglio4")
    assert _EXPECTED_TABLE_SHEET == "Foglio1"
    assert _EXPECTED_HEADER_ROW == 7


def test_sassari_source_status_and_identifier_denominators_are_frozen() -> None:
    assert _EXPECTED_STATUS_COUNTS == {
        "listed": 335,
        "pending": 129,
        "renewal_update_in_progress": 12,
        "expired_observed": 1,
        "other_or_unknown": 1,
    }
    assert _EXPECTED_IDENTIFIER_COVERAGE == 472
    assert _EXPECTED_RAW_IDENTIFIER_ONLY == 6


def test_sassari_status_mapping_requires_positive_source_evidence() -> None:
    assert _status("12/08/2026", "") == "listed"
    assert _status("RICHIESTA ISCRIZIONE", "") == "pending"
    assert _status("RICHIESTA  ISCRIZIONE", "") == "pending"
    assert _status("RICHIESTA ISCRIZONE", "") == "pending"
    assert _status("RICHIESTA PERMANENZA", "") == "renewal_update_in_progress"
    assert _status("12/08/2026", "AGGIORNAMENTO") == "renewal_update_in_progress"
    assert _status("RICHIESTA ISCRIZIONE", "SCADUTA") == "expired_observed"
    assert _status("", "") == "other_or_unknown"


def test_sassari_dates_do_not_repair_source_digits() -> None:
    assert _source_date("09.01.2026") == "2026-01-09"
    assert _source_date("09/01/2026") == "2026-01-09"
    assert _source_date("129.01.2025") == ""
    assert _source_date("31.02.2026") == ""
    assert _source_date("") == ""


def test_sassari_reviewed_source_anomalies_are_explicit_and_not_repaired() -> None:
    assert _REVIEWED_COLUMN_SWAP == {
        "DE.SCA.RI DEL GEOM. CALIA GIANLUCA": ("CLAGLC74B11E736M", "OLBIA")
    }
    assert _REVIEWED_MALFORMED_APPLICATION_DATE == {"M.I.A. SRL": "129.01.2025"}
    assert _REVIEWED_NONSTANDARD_STATUSES == {
        "AAC COOPERATIVA SOCIALE": "other_or_unknown",
        "ROMANO FRANCA": "expired_observed",
    }
    assert _REVIEWED_MALFORMED_IDENTIFIER_FIELDS == {
        "COOPERATIVA SO.LI.DA. SOCIETA' COOPERATIVA SOCIALE": "0267999099",
        "CROCE SARDA BONORVA SOCIETA' COOPERATIVA SOCIALE ONLUS": "0247890903",
        "DE.SCA.RI DEL GEOM. CALIA GIANLUCA": "OLBIA",
        "MEDITERRANEA AMBIENTE SRL": "2517630907",
        "SACCU DAVIDE": "SCCDVD85RA192Y",
        "SOLIMAS SRL": "0233440906",
    }
