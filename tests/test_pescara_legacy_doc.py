from __future__ import annotations

from pathlib import Path

import pytest

from white_list_archive.parsers.pescara_legacy_doc import PARSERS, parse_pescara_listed


def test_pescara_parsers_registered() -> None:
    assert set(PARSERS) == {"pescara_legacy_listed", "pescara_legacy_applicants"}


def test_pescara_listed_reference_date_fails_closed_before_io() -> None:
    cfg = {"source_key": "pescara-listed", "authority_key": "pescara", "reference_date": "2026-09-15"}
    with pytest.raises(RuntimeError, match="reference-date drift"):
        parse_pescara_listed(Path("does-not-exist.doc"), cfg)
