from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _iso_date, _record

PARSER_NAME = "pesaro_urbino_combined"
PARSER_VERSION = "1"
_EXPECTED_PAGES = 21
_EXPECTED_ROWS = 484
_DATE_SLASH_OR_DOT = re.compile(r"^\d{2}[./]\d{2}[./]\d{4}$")


def _sections(value: str) -> list[str]:
    out: list[str] = []
    for number in re.findall(r"\d{1,2}", _clean(value)):
        label = f"Sezione {int(number)}"
        if label not in out:
            out.append(label)
    return out


def _source_date(value: str, *, field: str, ordinal: int) -> str:
    raw = _clean(value)
    if not raw:
        return ""
    if not _DATE_SLASH_OR_DOT.fullmatch(raw):
        raise RuntimeError(f"Pesaro-Urbino row {ordinal}: unsupported {field} source date {raw!r}")
    parsed = _iso_date(raw)
    if not parsed:
        raise RuntimeError(f"Pesaro-Urbino row {ordinal}: invalid {field} source date {raw!r}")
    return parsed


def _record_from_cells(row: list[Any], cfg: dict[str, Any], ordinal: int) -> dict[str, Any]:
    if len(row) < 9:
        raise RuntimeError(f"Pesaro-Urbino row {ordinal}: expected at least 9 table cells, got {len(row)}")

    name = _clean(row[0])
    office = _clean(row[1])
    identifier = _clean(row[2])
    listing_raw = _clean(row[3])
    expiry_raw = _clean(row[4])
    sections_raw = _clean(row[7])
    update_raw = _clean(row[8])

    if not name or not office or not identifier:
        raise RuntimeError(
            f"Pesaro-Urbino row {ordinal}: incomplete source identity fields "
            f"name={bool(name)} office={bool(office)} identifier={bool(identifier)}"
        )
    if update_raw and update_raw.casefold() != "x":
        raise RuntimeError(f"Pesaro-Urbino row {ordinal}: unexpected update marker {update_raw!r}")
    if bool(listing_raw) != bool(expiry_raw):
        raise RuntimeError(
            f"Pesaro-Urbino row {ordinal}: listing/expiry date pair is structurally incomplete"
        )
    if not listing_raw and not update_raw:
        raise RuntimeError(
            f"Pesaro-Urbino row {ordinal}: row has neither an explicit listing date pair nor an update-in-progress marker"
        )

    listing_date = _source_date(listing_raw, field="listing", ordinal=ordinal)
    expiry_date = _source_date(expiry_raw, field="expiry", ordinal=ordinal)
    in_update = update_raw.casefold() == "x"
    status = "renewal_update_in_progress" if in_update else "listed"

    source_fields: dict[str, Any] = {"sections": _sections(sections_raw)}
    if in_update:
        source_fields["in_aggiornamento"] = update_raw
    if listing_raw:
        source_fields["listing_date_raw_variants"] = [listing_raw]
        source_fields["expiry_date_raw_variants"] = [expiry_raw]

    record = _record(
        cfg,
        ordinal,
        name=name,
        office=office,
        identifier_raw=identifier,
        activities=_sections(sections_raw),
        status=status,
        outcome_raw=update_raw,
        listing_date=listing_date,
        expiry_date=expiry_date,
        primary_date_label="Data iscrizione" if listing_date else "",
        source_fields=source_fields,
    )
    return record


def _company_table(page: pdfplumber.page.Page, page_number: int) -> list[list[Any]]:
    matches: list[list[list[Any]]] = []
    for table in page.extract_tables():
        if table and table[0] and _clean(table[0][0]).casefold() == "ragione sociale":
            matches.append(table)
    if len(matches) != 1:
        raise RuntimeError(
            f"Pesaro-Urbino page {page_number}: expected exactly one company table, got {len(matches)}"
        )
    table = matches[0]
    if len(table) < 4 or len(table[0]) < 9:
        raise RuntimeError(f"Pesaro-Urbino page {page_number}: company table is structurally incomplete")
    header = [_clean(value).casefold() for value in table[0][:9]]
    if header[0] != "ragione sociale" or header[1] != "sede legale" or "codice fiscale" not in header[2]:
        raise RuntimeError(f"Pesaro-Urbino page {page_number}: unexpected primary table header")
    if "data iscrizione" not in header[3] or "sezioni" not in header[7] or "aggiornamento" not in header[8]:
        raise RuntimeError(f"Pesaro-Urbino page {page_number}: unexpected date/section/update columns")
    return table


def parse_combined(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    records: list[dict[str, Any]] = []
    page_rows: list[int] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _EXPECTED_PAGES:
            raise RuntimeError(
                f"Pesaro-Urbino source layout changed: expected {_EXPECTED_PAGES} pages, got {len(pdf.pages)}"
            )
        ordinal = 0
        for page_number, page in enumerate(pdf.pages, 1):
            table = _company_table(page, page_number)
            rows = table[3:]
            page_rows.append(len(rows))
            for row in rows:
                ordinal += 1
                records.append(_record_from_cells(row, cfg, ordinal))

    if len(records) != _EXPECTED_ROWS:
        raise RuntimeError(
            f"Pesaro-Urbino source layout changed: expected {_EXPECTED_ROWS} rows, got {len(records)}"
        )

    diagnostics = {
        "parser": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "pages": _EXPECTED_PAGES,
        "page_rows": page_rows,
        "public_records": len(records),
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "section_coverage": sum(bool(record["requested_activities"]) for record in records),
        "missing_sections": sum(not record["requested_activities"] for record in records),
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records, diagnostics)


PARSERS = {"pesaro_urbino_combined": parse_combined}
