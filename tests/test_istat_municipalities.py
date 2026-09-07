from __future__ import annotations

import html
import zipfile
from pathlib import Path

import pytest

from white_list_archive.acquisition.istat_municipalities import (
    HEADER_TO_FIELD,
    OUTPUT_FIELDS,
    _header,
    iter_municipalities,
    parse_workbook,
    write_crosswalk_csv,
)


def _column_name(index: int) -> str:
    result = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _sheet_xml(rows: list[list[str]]) -> str:
    xml_rows = []
    for row_number, values in enumerate(rows, start=1):
        cells = []
        for index, value in enumerate(values):
            ref = f"{_column_name(index)}{row_number}"
            cells.append(
                f'<c r="{ref}" t="inlineStr"><is><t>{html.escape(value)}</t></is></c>'
            )
        xml_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
    )


def _record(**overrides: str) -> dict[str, str]:
    record = {field: "" for field in OUTPUT_FIELDS}
    record.update(
        {
            "region_code": "18",
            "supra_unit_code": "078",
            "historical_province_code": "078",
            "municipality_progressive": "045",
            "municipality_code": "078045",
            "municipality_name": "Cosenza",
            "municipality_name_it": "Cosenza",
            "geographic_division_code": "4",
            "geographic_division_name": "Sud",
            "region_name": "Calabria",
            "supra_unit_name": "Cosenza",
            "supra_unit_type_code": "1",
            "capital_flag": "1",
            "province_plate": "CS",
            "municipality_code_numeric": "78045",
            "municipality_code_numeric_2017_2025": "78045",
            "municipality_code_numeric_2010_2016": "78045",
            "municipality_code_numeric_2006_2009": "78045",
            "municipality_code_numeric_1995_2005": "78045",
            "cadastral_code": "D086",
            "nuts1_2021": "ITF",
            "nuts2_2021": "ITF6",
            "nuts3_2021": "ITF61",
            "nuts1_2024": "ITF",
            "nuts2_2024": "ITF6",
            "nuts3_2024": "ITF61",
        }
    )
    record.update(overrides)
    return record


def _write_workbook(
    path: Path,
    records: list[dict[str, str]],
    *,
    sheet_name: str = "CODICI al 21_02_2026",
    headers: list[str] | None = None,
) -> None:
    headers = headers or list(HEADER_TO_FIELD)
    rows = [headers]
    for record in records:
        rows.append([record.get(HEADER_TO_FIELD.get(_header(header), ""), "") for header in headers])

    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{html.escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets>'
        '</workbook>'
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet1.xml", _sheet_xml(rows))


def test_parse_current_istat_crosswalk_and_preserve_versioned_geography(tmp_path: Path):
    workbook = tmp_path / "municipalities.xlsx"
    _write_workbook(
        workbook,
        [
            _record(),
            _record(
                municipality_progressive="102",
                municipality_code="078102",
                municipality_name="Rende",
                municipality_name_it="Rende",
                capital_flag="0",
                cadastral_code="H235",
            ),
        ],
    )

    parsed = parse_workbook(workbook)
    assert parsed["provider_version"] == "2026-02-21"
    assert parsed["source_sheet"] == "CODICI al 21_02_2026"
    assert len(parsed["records"]) == 2
    cosenza, rende = parsed["records"]
    assert cosenza["municipality_code"] == "078045"
    assert cosenza["cadastral_code"] == "D086"
    assert cosenza["nuts3_2024"] == "ITF61"
    assert rende["municipality_code"] == "078102"
    assert rende["cadastral_code"] == "H235"


def test_header_normalisation_tolerates_official_line_breaks_and_spacing(tmp_path: Path):
    workbook = tmp_path / "municipalities.xlsx"
    headers = list(HEADER_TO_FIELD)
    target = "Codice dell'Unità territoriale sovracomunale (valida a fini statistici)"
    index = headers.index(target)
    headers[index] = "Codice dell'Unità territoriale sovracomunale \n  (valida a fini statistici)"
    _write_workbook(workbook, [_record()], headers=headers)
    parsed = parse_workbook(workbook)
    assert parsed["records"][0]["supra_unit_code"] == "078"


def test_missing_required_header_is_a_schema_failure(tmp_path: Path):
    workbook = tmp_path / "municipalities.xlsx"
    headers = [header for header in HEADER_TO_FIELD if header != "Codice Catastale del Comune"]
    _write_workbook(workbook, [_record()], headers=headers)
    with pytest.raises(ValueError, match="missing required fields"):
        parse_workbook(workbook)


def test_duplicate_official_identifiers_are_rejected(tmp_path: Path):
    workbook = tmp_path / "municipalities.xlsx"
    _write_workbook(workbook, [_record(), _record()])
    with pytest.raises(ValueError, match="Duplicate Istat municipality code"):
        parse_workbook(workbook)


def test_normalised_csv_has_stable_schema_and_is_streamable(tmp_path: Path):
    destination = tmp_path / "crosswalk.csv"
    records = [_record(), _record(municipality_code="078102", cadastral_code="H235", municipality_name="Rende", municipality_name_it="Rende")]
    digest = write_crosswalk_csv(records, destination)
    assert len(digest) == 64
    loaded = list(iter_municipalities(destination))
    assert tuple(loaded[0]) == OUTPUT_FIELDS
    assert [row["municipality_name"] for row in loaded] == ["Cosenza", "Rende"]
