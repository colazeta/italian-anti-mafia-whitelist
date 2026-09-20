from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

from white_list_archive.parsers.matera_openxml import parse_applicants, parse_listed


def _cfg(source_key: str, sha: str = "a" * 64) -> dict[str, str]:
    return {
        "source_key": source_key,
        "authority_key": "matera",
        "authority_name": "Prefettura - Ufficio Territoriale del Governo di Matera",
        "register_key": "matera-ordinary",
        "register_name": "White List",
        "population_scope": "listed" if source_key.endswith("listed") else "applicants",
        "reference_date": "2026-07-31",
        "source_page_url": "https://prefettura.interno.gov.it/it/prefetture/matera/evidenza/white-list",
        "resource_url": f"https://example.invalid/{source_key}.xlsx",
        "sha256": sha,
    }


def _formula(value: str) -> str:
    return f'=\"{value}\"'


def _write_listed(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "DPP1059056-20260722-WLIscrizion"
    worksheet.append([
        "Prefettura Competente", "Codice fiscale", "Ragione sociale", "Stato iscrizione",
        "Data inizo iscrizione", "Data scadenza", "Note", "", "", "",
    ])
    for index in range(1, 249):
        identifier = f"{index:011d}"
        note = "Art. 34 bis d.lgs 159/2011 - Controllo giudiziario" if index == 3 else ""
        note_period = f"{note}." if note else ""
        worksheet.append([
            "MT", _formula(identifier), f"IMPRESA {index}", "ISCRITTA",
            _formula("01/07/2026"), _formula("01/07/2027"), note, note, note, note_period,
        ])
    workbook.save(path)


def _write_applicants(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "DPP1059056-20260731-WLIscrizion"
    worksheet.append([
        "Prefettura Competente", "Data presentazione istanza", "Codice fiscale", "Ragione sociale",
        "Settori di iscrizione", "Stato iscrizione", "Protocollo richiesta",
    ])
    for index in range(1, 91):
        status = "RICHIEDENTE_ISCRIZIONE" if index <= 41 else "IN_AGGIORNAMENTO"
        date_cell: object = datetime(2026, 6, 12) if index == 88 else _formula("24/07/2026")
        sections = "SEZ_I, SEZ_III" if index == 1 else ""
        worksheet.append([
            "MT", date_cell, _formula(f"{index + 500:011d}"), f"RICHIEDENTE {index}", sections, status, "",
        ])
    workbook.save(path)


def test_matera_listed_exact_boundary_and_preserved_note_variants(tmp_path: Path) -> None:
    path = tmp_path / "listed.xlsx"
    _write_listed(path)
    batch = parse_listed(path, _cfg("matera-listed"))

    assert len(batch.records) == 248
    assert batch.diagnostics["source_status_counts"] == {"ISCRITTA": 248}
    assert batch.diagnostics["status_counts"] == {"listed": 248}
    assert batch.diagnostics["identifier_coverage"] == 248
    assert batch.diagnostics["listing_date_coverage"] == 248
    assert batch.diagnostics["expiry_date_coverage"] == 248
    assert batch.diagnostics["rows_with_judicial_control_note"] == 1
    assert batch.diagnostics["rows_with_reviewed_note_variant"] == 1
    assert batch.records[0]["identifier_field_raw"] == "00000000001"
    assert batch.records[0]["observed_listing_date"] == "2026-07-01"
    assert batch.records[0]["observed_expiry_date"] == "2027-07-01"
    judicial = batch.records[2]["source_fields"]
    assert judicial["notes"] == ["Art. 34 bis d.lgs 159/2011 - Controllo giudiziario"]
    assert judicial["note_variants"] == [
        "Art. 34 bis d.lgs 159/2011 - Controllo giudiziario",
        "Art. 34 bis d.lgs 159/2011 - Controllo giudiziario.",
    ]
    assert judicial["note_cells_raw"] == [
        "Art. 34 bis d.lgs 159/2011 - Controllo giudiziario",
        "Art. 34 bis d.lgs 159/2011 - Controllo giudiziario",
        "Art. 34 bis d.lgs 159/2011 - Controllo giudiziario",
        "Art. 34 bis d.lgs 159/2011 - Controllo giudiziario.",
    ]
    assert len({record["record_locator"] for record in batch.records}) == 248


def test_matera_applicants_maps_source_status_and_excel_dates(tmp_path: Path) -> None:
    path = tmp_path / "applicants.xlsx"
    _write_applicants(path)
    batch = parse_applicants(path, _cfg("matera-applicants"))

    assert len(batch.records) == 90
    assert batch.diagnostics["source_status_counts"] == {"RICHIEDENTE_ISCRIZIONE": 41, "IN_AGGIORNAMENTO": 49}
    assert batch.diagnostics["status_counts"] == {"pending": 41, "renewal_update_in_progress": 49}
    assert batch.diagnostics["identifier_coverage"] == 90
    assert batch.diagnostics["application_date_coverage"] == 90
    assert batch.diagnostics["true_excel_date_cells"] == 1
    assert batch.records[0]["requested_activities"] == ["SEZ_I", "SEZ_III"]
    assert batch.records[0]["application_date"] == "2026-07-24"
    assert batch.records[87]["application_date"] == "2026-06-12"
    assert batch.records[87]["source_fields"]["application_date_cell_type"] == "excel_date"
    assert len({record["record_locator"] for record in batch.records}) == 90
