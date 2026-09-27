from __future__ import annotations

from pathlib import Path

import pytest

from white_list_archive.parsers.enna_combined import (
    PARSERS,
    _applicant_sections,
    _applicant_status,
    _listed_status,
    parse_enna_combined,
)


def test_enna_parser_registered() -> None:
    assert set(PARSERS) == {"enna_combined"}


def test_enna_source_key_fails_closed_before_io() -> None:
    cfg = {
        "source_key": "wrong",
        "population_scope": "listed_and_applicant",
        "reference_date": "2026-09-18",
    }
    with pytest.raises(RuntimeError, match="source-key drift"):
        parse_enna_combined(Path("does-not-exist.pdf"), cfg)


def test_enna_population_scope_fails_closed_before_io() -> None:
    cfg = {
        "source_key": "enna-combined",
        "population_scope": "listed",
        "reference_date": "2026-09-18",
    }
    with pytest.raises(RuntimeError, match="population-scope drift"):
        parse_enna_combined(Path("does-not-exist.pdf"), cfg)


def test_enna_reference_date_fails_closed_before_io() -> None:
    cfg = {
        "source_key": "enna-combined",
        "population_scope": "listed_and_applicant",
        "reference_date": "2026-09-17",
    }
    with pytest.raises(RuntimeError, match="reference-date drift"):
        parse_enna_combined(Path("does-not-exist.pdf"), cfg)


def test_enna_statuses_are_only_source_explicit_vocabularies() -> None:
    assert _listed_status("") == "listed"
    assert _listed_status("[ 2 ]") == "renewal_update_in_progress"
    assert _applicant_status("IN ISTRUTTORIA") == "pending"
    with pytest.raises(RuntimeError, match="note vocabulary drift"):
        _listed_status("RINNOVO")
    with pytest.raises(RuntimeError, match="outcome vocabulary drift"):
        _applicant_status("")


def test_enna_applicant_section_codes_are_conservative() -> None:
    assert _applicant_sections("1-3-5") == ["Sezione 01", "Sezione 03", "Sezione 05"]
    assert _applicant_sections("10") == ["Sezione 10"]
    with pytest.raises(RuntimeError, match="activity-code drift"):
        _applicant_sections("1-1")
    with pytest.raises(RuntimeError, match="activity-code drift"):
        _applicant_sections("11")
    with pytest.raises(RuntimeError, match="activity-code drift"):
        _applicant_sections("NOLI A CALDO")
