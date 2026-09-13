from __future__ import annotations

import pytest

from white_list_archive.parsers.foggia_tables import (
    _EXPECTED_APPLICANT_EMPTY_IDENTIFIER_ROWS,
    _EXPECTED_APPLICANT_RAW_IDENTIFIER_ROWS,
    _EXPECTED_APPLICANT_RECORDS,
    _EXPECTED_APPLICANT_STATUS_COUNTS,
    _EXPECTED_APPLICANT_STRICT_IDENTIFIER_ROWS,
    _EXPECTED_LISTED_RECORDS,
    _EXPECTED_LISTED_SECTOR_ROWS,
    _EXPECTED_LISTED_STATUS_COUNTS,
    _parse_date,
    _representative_name,
    _status_group,
    _strict_identifiers,
)


def test_foggia_source_denominators_are_frozen() -> None:
    assert _EXPECTED_LISTED_SECTOR_ROWS == 942
    assert _EXPECTED_LISTED_RECORDS == 330
    assert _EXPECTED_LISTED_STATUS_COUNTS == {
        "listed": 85,
        "renewal_update_in_progress": 245,
    }
    assert _EXPECTED_APPLICANT_RECORDS == 628
    assert _EXPECTED_APPLICANT_STATUS_COUNTS == {"pending": 628}
    assert _EXPECTED_APPLICANT_STRICT_IDENTIFIER_ROWS == 621
    assert _EXPECTED_APPLICANT_RAW_IDENTIFIER_ROWS == 6
    assert _EXPECTED_APPLICANT_EMPTY_IDENTIFIER_ROWS == 1


def test_foggia_listed_status_vocabulary_is_fail_closed() -> None:
    assert _status_group("") == "listed"
    assert _status_group("IN CORSO") == "renewal_update_in_progress"
    assert _status_group("I N CORSO") == "renewal_update_in_progress"
    with pytest.raises(RuntimeError, match="unreviewed listed status"):
        _status_group("RINNOVO")


def test_foggia_dates_are_parsed_only_when_calendar_valid() -> None:
    assert _parse_date("08.09.2026") == "2026-09-08"
    assert _parse_date("10/09/2026") == "2026-09-10"
    assert _parse_date("31/02/2026") == ""
    assert _parse_date("65.5.2026") == ""
    assert _parse_date("10-09-2026") == ""


def test_foggia_identifiers_are_never_repaired() -> None:
    assert _strict_identifiers("03926080718") == ["03926080718"]
    assert _strict_identifiers("RSSMRA80A01D643X") == ["RSSMRA80A01D643X"]
    assert _strict_identifiers("3926080718") == []
    assert _strict_identifiers("003926080718") == []


def test_foggia_reviewed_luisi_name_reconciliation_is_exact() -> None:
    key = ("id", "03570730717", "ISO::2025-06-11", "ISO::2026-06-11", "listed")
    group = {"name_variants": ["In corso", "LUISI COSTRUZIONI DI LUISI CARMINE"]}
    assert _representative_name(group, key) == (
        "LUISI COSTRUZIONI DI LUISI CARMINE",
        "reviewed_source_name_column_inconsistency",
    )

    drifted = {"name_variants": ["In corso", "LUISI COSTRUZIONI"]}
    with pytest.raises(RuntimeError, match="reviewed name variants drifted"):
        _representative_name(drifted, key)


def test_foggia_unreviewed_multi_name_identity_fails_closed() -> None:
    key = ("id", "03926080718", "ISO::2024-09-09", "ISO::2025-09-09", "listed")
    group = {"name_variants": ["IMPRESA PASQUA S.R.L.", "IMPRESA PASQUA SRL"]}
    with pytest.raises(RuntimeError, match="unreviewed multi-name strict-identity group"):
        _representative_name(group, key)
