from __future__ import annotations

import pytest

from white_list_archive.parsers.siracusa_tables import (
    _listed_status,
    _parse_application_date,
    _parse_dotted_date,
    _strict_identifiers,
)


def test_siracusa_listed_status_is_evidence_conservative() -> None:
    assert _listed_status("") == "listed"
    assert _listed_status("Istanza di rinnovo 02.03.2026") == "renewal_update_in_progress"
    assert _listed_status("Istanza di rinovo 04.03.2026") == "renewal_update_in_progress"
    assert _listed_status("11.05.2026 Istanza di modifica assetto societario") == "renewal_update_in_progress"
    assert _listed_status("Comunicazione variazione assetto societario 16.12.2025") == "renewal_update_in_progress"
    assert _listed_status("Istanza di rinnovo 01.10.2025 Integrazione 25.11.2025") == "renewal_update_in_progress"
    assert _listed_status("06.08.2026") == "other_or_unknown"
    assert (
        _listed_status(
            "In data 6.5.2026 presentata istanza di cancellazione per trasferimento sede legale in altra provincia"
        )
        == "other_or_unknown"
    )


def test_siracusa_expiry_typography_is_closed_to_reviewed_variants() -> None:
    assert _parse_dotted_date("17.09.2026") == "2026-09-17"
    assert _parse_dotted_date("13.8.2026") == "2026-08-13"
    assert _parse_dotted_date("18.6.2024") == "2024-06-18"
    with pytest.raises(RuntimeError, match="unreviewed listed expiry typography"):
        _parse_dotted_date("1.6.2024")
    with pytest.raises(RuntimeError, match="invalid calendar date"):
        _parse_dotted_date("31.02.2026")


def test_siracusa_application_dates_preserve_reviewed_annotations_without_repair() -> None:
    assert _parse_application_date("23.04.2026") == "2026-04-23"
    assert (
        _parse_application_date("07.01.2026 Precedente denominazione sociale: “GERVASI PAOLO S.R.L.”")
        == "2026-01-07"
    )
    assert _parse_application_date("24.10.2023 E 11.07.2025") == "2023-10-24"
    assert _parse_application_date("17.01/2024") == ""
    with pytest.raises(RuntimeError, match="unreviewed application-date typography"):
        _parse_application_date("17/01/2024")
    with pytest.raises(RuntimeError, match="unreviewed application-date typography"):
        _parse_application_date("01.01.2026 nuova nota non revisionata")


def test_siracusa_identifiers_are_not_reconstructed() -> None:
    assert _strict_identifiers("01989620891") == ["01989620891"]
    assert _strict_identifiers("GLLLSN81M15F258W") == ["GLLLSN81M15F258W"]
    assert _strict_identifiers("0598740823") == []
    assert _strict_identifiers("RANN") == []
    assert _strict_identifiers("013413108912") == []
    assert _strict_identifiers("10988791215 *") == []
