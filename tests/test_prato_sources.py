from __future__ import annotations

from pathlib import Path

import pytest

from white_list_archive.parsers.prato_sources import (
    PARSERS,
    _applicant_activities,
    _section_activity,
    parse_prato_applicants,
    parse_prato_listed,
)


def test_prato_parsers_registered() -> None:
    assert set(PARSERS) == {"prato_openxml_listed", "prato_legacy_applicants"}


def test_prato_listed_reference_date_fails_closed_before_io() -> None:
    cfg = {
        "source_key": "prato-listed",
        "population_scope": "listed",
        "reference_date": "2026-09-13",
    }
    with pytest.raises(RuntimeError, match="reference-date drift"):
        parse_prato_listed(Path("does-not-exist.xlsx"), cfg)


def test_prato_applicant_source_key_fails_closed_before_io() -> None:
    cfg = {
        "source_key": "wrong",
        "population_scope": "applicant",
        "reference_date": "2026-09-21",
    }
    with pytest.raises(RuntimeError, match="source-key drift"):
        parse_prato_applicants(Path("does-not-exist.doc"), cfg)


def test_prato_population_scope_fails_closed_before_io() -> None:
    cfg = {
        "source_key": "prato-listed",
        "population_scope": "applicant",
        "reference_date": "2026-09-21",
    }
    with pytest.raises(RuntimeError, match="population-scope drift"):
        parse_prato_listed(Path("does-not-exist.xlsx"), cfg)


def test_prato_section_heading_preserves_official_activity() -> None:
    assert _section_activity(
        "SEZIONE II – CONFEZIONAMENTO, FORNITURA E TRASPORTO DI CALCESTRUZZO E BITUME",
        "II",
    ) == "CONFEZIONAMENTO, FORNITURA E TRASPORTO DI CALCESTRUZZO E BITUME"
    with pytest.raises(ValueError, match="section-heading drift"):
        _section_activity("SEZIONE III NOLI A FREDDO DI MACCHINARI", "III")


def test_prato_applicant_activity_split_is_conservative() -> None:
    assert _applicant_activities("- Servizi ambientali") == ["Servizi ambientali"]
    assert _applicant_activities(
        "- Estrazione, fornitura e trasporto di terra e materiali inerti - Noli a caldo"
    ) == [
        "Estrazione, fornitura e trasporto di terra e materiali inerti",
        "Noli a caldo",
    ]
    with pytest.raises(ValueError, match="unexpectedly blank"):
        _applicant_activities("")
