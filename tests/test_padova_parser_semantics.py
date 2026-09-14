from __future__ import annotations

import pytest

from white_list_archive.parsers.padova_tables import (
    _APPLICANT_NAME_RECOVERY,
    _APPLICANT_REVIEWED_DUPLICATE,
    _EXPECTED_APPLICANT_RECORDS,
    _EXPECTED_APPLICANT_STATUS_COUNTS,
    _EXPECTED_LISTED_RECORDS,
    _EXPECTED_LISTED_STATUS_COUNTS,
    _LISTED_NONCALENDAR_EXPIRY,
    _LISTED_REVIEWED_DATE_INVERSION,
    _listed_expiry,
    _recover_applicant_names,
    _sections,
    _strict_identifiers,
)


def test_padova_source_denominators_and_statuses_are_frozen() -> None:
    assert _EXPECTED_LISTED_RECORDS == 831
    assert _EXPECTED_APPLICANT_RECORDS == 174
    assert _EXPECTED_LISTED_STATUS_COUNTS == {
        "listed": 581,
        "renewal_update_in_progress": 250,
    }
    assert _EXPECTED_APPLICANT_STATUS_COUNTS == {"pending": 174}
    assert len(_LISTED_NONCALENDAR_EXPIRY) == 2
    assert len(_LISTED_REVIEWED_DATE_INVERSION) == 1
    assert set(_APPLICANT_NAME_RECOVERY) == {113}
    assert _APPLICANT_REVIEWED_DUPLICATE == (38, 39)


def test_padova_identifiers_only_accept_positive_source_components() -> None:
    assert _strict_identifiers("02038910283") == ["02038910283"]
    assert _strict_identifiers("MRLCRL77H12F904 M/05700010282") == [
        "MRLCRL77H12F904M",
        "05700010282",
    ]
    assert _strict_identifiers("CRGMRC68C07G224W /05377750285") == [
        "CRGMRC68C07G224W",
        "05377750285",
    ]
    assert _strict_identifiers("not-a-positive-identifier") == []


def test_padova_sections_are_bound_to_physical_numbered_columns() -> None:
    cells = ["COMPANY", "OFFICE", "", "01234567890"] + ["", "", "3", "4", "", "", "", "", "", ""] + ["01/01/2026", "123/2026", ""]
    assert _sections(cells, ordinal=1, population="applicants") == ["Sezione 3", "Sezione 4"]
    cells[6] = "4"
    with pytest.raises(RuntimeError, match="section-cell drift"):
        _sections(cells, ordinal=1, population="applicants")


def test_padova_noncalendar_expiry_is_preserved_but_not_inferred() -> None:
    assert (
        _listed_expiry(
            "46581,00",
            ordinal=108,
            company="BIOPROGRAMM BIOTECNOLOGIE AVANZATE E TECNICHE AMBIENTALI SRL",
            identifier_raw="02038910283",
            listing_raw="14/07/2026",
        )
        == ""
    )
    assert (
        _listed_expiry(
            "8807/2026",
            ordinal=479,
            company="LA PERLA TRASPORTI E LOGISTICA DI MORELLO CARLO",
            identifier_raw="MRLCRL77H12F904 M/05700010282",
            listing_raw="24/06/2026",
        )
        == ""
    )
    with pytest.raises(RuntimeError, match="reviewed non-calendar expiry drift"):
        _listed_expiry(
            "46581,00",
            ordinal=108,
            company="DIFFERENT COMPANY",
            identifier_raw="02038910283",
            listing_raw="14/07/2026",
        )


def test_padova_applicant_name_recovery_is_exactly_source_bound() -> None:
    expected, recovered = _APPLICANT_NAME_RECOVERY[113]
    rows = [{"page": 1, "row": 1, "cells": ["DUMMY"] + [""] * 16} for _ in range(174)]
    for ordinal, row in enumerate(rows, start=1):
        row["cells"][0] = f"COMPANY {ordinal}"
    rows[112]["cells"] = list(expected)
    _recover_applicant_names(rows)
    assert rows[112]["cells"][0] == recovered == "NON SOLO ZANZARE SRL"

    rows[112]["cells"] = list(expected)
    rows[112]["cells"][1] = "SELVAZZANO DENTRO, VIA DRIFT 2"
    with pytest.raises(RuntimeError, match="reviewed name-recovery drift"):
        _recover_applicant_names(rows)
