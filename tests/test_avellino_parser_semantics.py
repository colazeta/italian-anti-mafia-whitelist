from pathlib import Path

import pytest

from white_list_archive.parsers import avellino_positioned as parser


def _word(text: str, x0: float, x1: float, top: float = 100.0, bottom: float = 106.0):
    return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": bottom}


def _cfg(population: str) -> dict[str, str]:
    return {
        "source_key": f"avellino-{population}",
        "authority_key": "avellino",
        "authority_name": "Prefettura di Avellino",
        "register_key": "avellino-ordinary",
        "register_name": "White List ordinaria",
        "population_scope": population,
        "reference_date": "2026-09-01",
        "source_page_url": "https://example.invalid/page",
        "resource_url": "https://example.invalid/resource.pdf",
        "sha256": "0" * 64,
    }


def test_date_spans_reassembles_split_date_without_merging_adjacent_text():
    words = [
        _word("01/", 620, 635),
        _word("09/", 636, 651),
        _word("2027", 652, 675),
        _word("nota", 690, 710),
    ]
    spans = parser._date_spans(words)
    assert len(spans) == 1
    assert spans[0]["value"] == "01/09/2027"
    assert spans[0]["x0"] == 620


def test_row_bounds_use_midpoints_and_do_not_overlap():
    anchors = [
        {"top": 100.0, "bottom": 106.0},
        {"top": 120.0, "bottom": 126.0},
        {"top": 140.0, "bottom": 146.0},
    ]
    bounds = parser._row_bounds(anchors, 800.0)
    assert bounds[0][1] == bounds[1][0]
    assert bounds[1][1] == bounds[2][0]
    assert all(bottom > top for top, bottom in bounds)


def test_validate_cells_fails_closed_on_missing_identity_field():
    rows = [{"name": "Impresa", "identifier": "", "office": "Avellino", "activities": "I", "date": "01/09/2026"}]
    with pytest.raises(RuntimeError, match="incomplete positioned source rows"):
        parser._validate_cells(rows, parser._APPLICANTS)


def test_listed_population_is_not_reinterpreted_from_free_text(monkeypatch):
    rows = [
        {
            "name": "Impresa Alfa",
            "identifier": "12345678901",
            "office": "Avellino",
            "activities": "Sezione I",
            "update": "testo fonte non interpretato",
            "date": "01/09/2027",
            "notes": "",
            "source_page": "1",
        }
    ]
    monkeypatch.setattr(parser, "_positioned_rows", lambda *_args: (rows, [1]))
    batch = parser.parse_listed(Path("ignored.pdf"), _cfg("listed"))
    assert batch.records[0]["source_status"] == "listed"
    assert batch.records[0]["observed_expiry_date"] == "2027-09-01"
    assert batch.records[0]["primary_date"] == "2027-09-01"
    assert batch.records[0]["primary_date_label"] == "Data scadenza"
    assert batch.records[0]["outcome_raw"] == "testo fonte non interpretato"
    assert batch.records[0]["source_fields"] == {}


def test_applicant_population_remains_pending(monkeypatch):
    rows = [
        {
            "name": "Impresa Beta",
            "identifier": "12345678901",
            "office": "Avellino",
            "activities": "Sezione II",
            "date": "01/09/2026",
            "source_page": "1",
        }
    ]
    monkeypatch.setattr(parser, "_positioned_rows", lambda *_args: (rows, [1]))
    batch = parser.parse_applicants(Path("ignored.pdf"), _cfg("applicant"))
    assert batch.records[0]["source_status"] == "pending"
    assert batch.records[0]["application_date"] == "2026-09-01"
    assert batch.records[0]["primary_date"] == "2026-09-01"
    assert batch.records[0]["primary_date_label"] == "Data presentazione istanza"
