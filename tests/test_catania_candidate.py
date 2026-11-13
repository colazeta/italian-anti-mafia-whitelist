"""Synthetic XLSX tests: Catania provisional parser never alters approved parsers."""
from datetime import datetime
from pathlib import Path

import openpyxl
import pytest

from white_list_archive.parsers.catania_candidate import (
    _source_date, parse_candidate_xlsx,
)


def _config(population):
    return {
        "source_key": "catania-" + ("listed" if population == "listed" else "applicants"),
        "authority_key": "catania",
        "authority_name": "Prefettura di Catania",
        "register_key": "catania-ordinary",
        "register_name": "White List ordinaria",
        "population_scope": population,
        "reference_date": "",
        "parser": ("catania_candidate_listed" if population == "listed"
                   else "catania_candidate_applicants"),
        "source_page_url": "https://prefettura.interno.gov.it/it/prefetture/catania/white-list",
        "resource_url": "https://prefettura.interno.gov.it/sites/default/files/18/candidate.xlsx",
        "sha256": "a" * 64,
    }


def _make_sheet(path, population):
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Foglio1"
    if population == "listed":
        header = [
            "RAGIONE SOCIALE", "SEDE LEGALE",
            "SEDE SECONDARIA CON RAPPRESENTANZA IN ITALIA",
            "ATTIVITA'", "CODICE FISCALE/PARTITA IVA",
            "DATA DI ISCRIZIONE", "SCADENZA ISCRIZIONE",
            "AGGIORNAMENTO IN CORSO",
        ]
        for col, value in enumerate(header, 1):
            sheet.cell(2, col, value)
        first = [
            "Fixture Alfa", "Catania", "", "1;3", "12345678901",
            datetime(2026, 11, 13), datetime(2027, 11, 13), "Rinnovo",
        ]
        second = [
            "Fixture Beta", "Catania", "", "5;bad", "unparsed-identifier",
            "32/11/2026", "=DATE(2027,11,13)", "Other note",
        ]
        for rowno, row in [(3, first), (4, second)]:
            for col, value in enumerate(row, 1):
                sheet.cell(rowno, col, value)
    else:
        header = [
            "RAGIONE SOCIALE", "SEDE LEGALE",
            "SEDE SECONDARIA CON RAPPRESENTANZA IN ITALIA",
            "ATTIVITA' RICHIESTA", "CODICE FISCALE/PARTITA IVA",
            "DATA PRESENTAZIONE ISTANZA", "ESITO",
        ]
        for col, value in enumerate(header, 1):
            sheet.cell(4, col, value)
        first = ["", "Catania", "", "2", "12345678901", "13/11/2026", ""]
        second = ["Fixture Delta", "Catania", "", "7", "12345678902",
                  "14/11/2026", "Esito non interpretabile"]
        for rowno, row in [(5, first), (6, second)]:
            for col, value in enumerate(row, 1):
                sheet.cell(rowno, col, value)
    sheet.cell(12, 1, "Nota di chiusura: testo non aziendale")
    book.save(path)
    book.close()


def test_variable_length_listed_xlsx_keeps_raw_anomalies_and_no_edition_date(tmp_path):
    path = tmp_path / "listed.xlsx"
    _make_sheet(path, "listed")
    result = parse_candidate_xlsx(path, _config("listed"))
    assert len(result.records) == 2
    first, second = result.records
    assert first["source_status"] == "renewal_update_in_progress"
    assert first["requested_activities"] == ["Sezione 1", "Sezione 3"]
    assert first["observed_listing_date"] == "2026-11-13"
    assert first["reference_date"] == ""
    assert first["parser_name"] == "catania_candidate_listed"
    assert second["requested_activities"] == ["Sezione 5"]
    assert second["source_fields"]["requested_activities_source"] == "5;bad"
    assert second["observed_listing_date"] == ""
    assert second["source_fields"]["listing_date_raw"] == "32/11/2026"
    assert second["observed_expiry_date"] == ""
    assert second["source_fields"]["expiry_date_raw"] == "=DATE(2027,11,13)"
    assert second["identifiers"] == []
    assert {"sector_anomalies", "unparsed_source_dates",
            "formula_without_cached_date", "unrecognised_identifiers"
            } <= set(result.diagnostics["candidate_quality_flags"])
    assert result.diagnostics["source_rows_represented"] == 2
    assert not result.diagnostics["publication_approved"]
    assert not result.diagnostics["source_date_assigned"]


def test_applicant_xlsx_keeps_blank_names_and_unknown_outcomes(tmp_path):
    path = tmp_path / "applicants.xlsx"
    _make_sheet(path, "applicant")
    result = parse_candidate_xlsx(path, _config("applicant"))
    assert len(result.records) == 2
    assert result.records[0]["name"] == ""
    assert result.records[0]["source_status"] == "pending"
    assert result.records[0]["application_date"] == "2026-11-13"
    assert result.records[1]["source_status"] == "other_or_unknown"
    assert result.records[1]["outcome_raw"] == "Esito non interpretabile"
    assert "unclassified_source_outcomes" in result.diagnostics["candidate_quality_flags"]


def test_provisional_parser_requires_blank_reference_date_and_explicit_schema(tmp_path):
    path = tmp_path / "listed.xlsx"
    _make_sheet(path, "listed")
    config = _config("listed")
    config["reference_date"] = "2026-11-13"
    with pytest.raises(ValueError, match="unapproved, undated"):
        parse_candidate_xlsx(path, config)
    config["reference_date"] = ""
    config["parser"] = "catania_listed_2026_11"
    with pytest.raises(ValueError, match="population/parser"):
        parse_candidate_xlsx(path, config)


def test_candidate_requires_known_headers_and_never_guesses_columns(tmp_path):
    path = tmp_path / "listed.xlsx"
    _make_sheet(path, "listed")
    book = openpyxl.load_workbook(path)
    book.active.cell(2, 5, "INCERTO")
    book.save(path)
    book.close()
    with pytest.raises(ValueError, match="header identity"):
        parse_candidate_xlsx(path, _config("listed"))


def test_strict_source_dates_do_not_repair_invalid_inputs():
    assert _source_date("13/11/2026") == ("2026-11-13", False)
    assert _source_date("2026-11-13") == ("2026-11-13", False)
    assert _source_date("32/11/2026") == ("", True)
    assert _source_date("November 2026") == ("", True)
    assert _source_date("") == ("", False)



def test_data_like_row_without_sector_and_identifier_is_not_silently_dropped(tmp_path):
    path = tmp_path / "listed.xlsx"
    _make_sheet(path, "listed")
    book = openpyxl.load_workbook(path)
    sheet = book.active
    sheet.cell(7, 1, "Fixture incomplete enterprise")
    sheet.cell(7, 2, "Catania")
    sheet.cell(7, 6, "13/11/2026")
    book.save(path)
    book.close()
    with pytest.raises(ValueError, match="Unclassified candidate row"):
        parse_candidate_xlsx(path, _config("listed"))
