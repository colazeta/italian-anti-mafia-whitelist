from __future__ import annotations

from pathlib import Path

import pytest

from white_list_archive.parsers.piacenza_legacy_xls import (
    PARSERS,
    _activities,
    parse_piacenza_applicants,
    parse_piacenza_listed,
)


def test_piacenza_parsers_registered() -> None:
    assert set(PARSERS) == {"piacenza_legacy_listed", "piacenza_legacy_applicants"}


def test_piacenza_reference_date_fails_closed_before_io() -> None:
    cfg = {
        "source_key": "piacenza-listed",
        "population_scope": "listed",
        "reference_date": "2026-09-20",
    }
    with pytest.raises(RuntimeError, match="reference-date drift"):
        parse_piacenza_listed(Path("does-not-exist.zip"), cfg)


def test_piacenza_source_key_and_population_fail_closed_before_io() -> None:
    cfg = {
        "source_key": "wrong",
        "population_scope": "applicant",
        "reference_date": "2026-09-21",
    }
    with pytest.raises(RuntimeError, match="source-key drift"):
        parse_piacenza_applicants(Path("does-not-exist.zip"), cfg)


def test_piacenza_activity_vocabulary_is_conservative() -> None:
    assert _activities("I, III,V,VI,X") == ["Sezione I", "Sezione III", "Sezione V", "Sezione VI", "Sezione X"]
    assert _activities("I,II,III.V") == ["Sezione I", "Sezione II", "III.V"]
    with pytest.raises(ValueError, match="vocabulary drift"):
        _activities("I, XI")
