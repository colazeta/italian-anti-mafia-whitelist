from pathlib import Path

import pytest

from white_list_archive.parsers import benevento_positioned as parser


def _word(text: str, x0: float, x1: float, top: float = 100.0, bottom: float = 106.0):
    return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": bottom}


def _cfg(population: str) -> dict[str, str]:
    return {
        "source_key": f"benevento-{population}",
        "authority_key": "benevento",
        "authority_name": "Prefettura di Benevento",
        "register_key": "benevento-ordinary",
        "register_name": "White List ordinaria",
        "population_scope": population,
        "reference_date": "2026-08-31",
        "source_page_url": "https://example.invalid/page",
        "resource_url": "https://example.invalid/resource.pdf",
        "sha256": "0" * 64,
    }


def test_date_spans_reassembles_split_date_without_changing_digits():
    words = [
        _word("31/", 724, 738),
        _word("08/", 739, 752),
        _word("2026", 753, 776),
        _word("nota", 790, 810),
    ]
    spans = parser._date_spans(words)
    assert len(spans) == 1
    assert spans[0]["value"] == "31/08/2026"
    assert spans[0]["x0"] == 724


def test_row_bounds_are_non_overlapping_and_respect_table_edges():
    anchors = [
        {"top": 100.0, "bottom": 106.0},
        {"top": 120.0, "bottom": 126.0},
        {"top": 140.0, "bottom": 146.0},
    ]
    bounds = parser._row_bounds(anchors, 90.0, 160.0)
    assert bounds[0][0] == 90.0
    assert bounds[-1][1] == 160.0
    assert bounds[0][1] == bounds[1][0]
    assert bounds[1][1] == bounds[2][0]


def test_source_empty_identifier_is_preserved_without_reconstruction():
    rows = [{"name": "Impresa", "office": "Benevento", "identifier": "", "application_date": "31/08/2026"}]
    parser._validate_identity(rows, parser._APPLICANTS)


def test_validate_identity_fails_closed_on_missing_name_or_office():
    with pytest.raises(RuntimeError, match="incomplete positioned source rows"):
        parser._validate_identity(
            [{"name": "", "office": "Benevento", "identifier": "123", "application_date": "31/08/2026"}],
            parser._APPLICANTS,
        )


def test_listed_population_is_not_reinterpreted_from_update_text(monkeypatch):
    rows = [
        {
            "name": "Impresa Alfa",
            "identifier": "12345678901",
            "office": "Benevento",
            "secondary": "",
            "activities": "I, II",
            "update": "testo fonte non interpretato",
            "listing_date": "31/08/2025",
            "expiry": "31/082026",
            "source_page": "1",
        }
    ]
    monkeypatch.setattr(parser, "_positioned_rows", lambda *_args: (rows, [1]))
    batch = parser.parse_listed(Path("ignored.pdf"), _cfg("listed"))
    record = batch.records[0]
    assert record["source_status"] == "listed"
    assert record["outcome_raw"] == "testo fonte non interpretato"
    assert record["observed_expiry_date"] == ""
    assert record["source_fields"]["expiry_date_raw_variants"] == ["31/082026"]
    assert batch.diagnostics["malformed_expiry_values"] == 1


def test_applicant_population_remains_pending(monkeypatch):
    rows = [
        {
            "name": "Impresa Beta",
            "identifier": "",
            "office": "Benevento",
            "activities": "Sezione III",
            "application_date": "31/08/2026",
            "source_page": "1",
        }
    ]
    monkeypatch.setattr(parser, "_positioned_rows", lambda *_args: (rows, [1]))
    batch = parser.parse_applicants(Path("ignored.pdf"), _cfg("applicant"))
    record = batch.records[0]
    assert record["source_status"] == "pending"
    assert record["application_date"] == "2026-08-31"
    assert record["primary_date"] == "2026-08-31"
    assert record["primary_date_label"] == "Data istanza"
    assert record["identifier_field_raw"] == ""
    assert record["identifiers"] == []
