from __future__ import annotations

import re
import zipfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import xlrd

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record


_REFERENCE_DATE = "2026-09-21"
_LISTED_MEMBER = "Ditte white list - Copia.xls"
_APPLICANTS_MEMBER = (
    "ELENCO_IMPRESE_RICHIEDENTI_L'ISCRIZIONE_NELL'ELENCO_DEI_FORNITORI,_"
    "PRESTATORI_DI_SERVIZI_ED_ESECUTORI_DI_LAVORI_NON_SOGGETTI_A_TENTATIVI_"
    "DI_INFILTRAZIONE_MAFIOSA - Copia.xls"
)
_LISTED_SHEETS = ("Foglio1", "Foglio2", "Foglio3", "Rapporto compatibilità")
_APPLICANT_SHEETS = ("Foglio1", "Foglio2", "Foglio3")
_LISTED_HEADER = (
    "Numero Ordine",
    "Numero Iscrizione",
    "Ragione sociale",
    "Sede legale",
    "Attività per cui è richiesta l'iscrizione",
    "Codice fiscale/Partita IVA",
    "Data iscrizione",
    "Data scadenza iscrizione",
    "Note",
)
_APPLICANT_TITLE = (
    "ELENCO DELLE IMPRESE RICHIEDENTI L'ISCRIZIONE NELL'ELENCO DEI FORNITORI, "
    "PRESTATORI DI SERVIZI ED ESECUTORI DI LAVORI NON SOGGETTI A TENTATIVI DI "
    "INFILTRAZIONE MAFIOSA"
)
_ROMAN = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}
_REVIEWED_ACTIVITY_ANOMALIES = {"III.V"}


def _require_cfg(cfg: dict[str, Any], source_key: str, population_scope: str) -> None:
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(
            f"Piacenza reference-date drift: expected {_REFERENCE_DATE}, got {cfg.get('reference_date')!r}"
        )
    if cfg.get("source_key") != source_key:
        raise RuntimeError(f"Piacenza source-key drift: expected {source_key!r}, got {cfg.get('source_key')!r}")
    if cfg.get("population_scope") != population_scope:
        raise RuntimeError(
            f"Piacenza population-scope drift: expected {population_scope!r}, got {cfg.get('population_scope')!r}"
        )


def _open_zip_workbook(path: Path, expected_member: str, expected_sheets: tuple[str, ...]) -> xlrd.book.Book:
    if not zipfile.is_zipfile(path):
        raise ValueError("Piacenza source must be the byte-pinned official ZIP resource")
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if not name.endswith("/")]
        if members != [expected_member]:
            raise ValueError(f"Piacenza ZIP member drift: expected {[expected_member]!r}, got {members!r}")
        payload = archive.read(expected_member)
    book = xlrd.open_workbook(file_contents=payload, formatting_info=True)
    if tuple(book.sheet_names()) != expected_sheets:
        raise ValueError(f"Piacenza workbook sheet drift: expected {expected_sheets!r}, got {tuple(book.sheet_names())!r}")
    return book


def _cell_text(book: xlrd.book.Book, sheet: xlrd.sheet.Sheet, row: int, col: int) -> str:
    cell = sheet.cell(row, col)
    if cell.ctype == xlrd.XL_CELL_EMPTY:
        return ""
    if cell.ctype == xlrd.XL_CELL_NUMBER and float(cell.value).is_integer():
        value = int(cell.value)
        try:
            xf = book.xf_list[cell.xf_index]
            fmt = book.format_map[xf.format_key].format_str
        except (IndexError, KeyError, AttributeError):
            fmt = ""
        if re.fullmatch(r"0{2,16}", fmt or ""):
            return f"{value:0{len(fmt)}d}"
        return str(value)
    return _clean(cell.value)


def _source_date(book: xlrd.book.Book, sheet: xlrd.sheet.Sheet, row: int, col: int) -> tuple[str, str]:
    cell = sheet.cell(row, col)
    raw = _cell_text(book, sheet, row, col)
    if cell.ctype == xlrd.XL_CELL_DATE:
        try:
            parsed = xlrd.xldate_as_datetime(cell.value, book.datemode).date()
            return parsed.isoformat(), raw
        except (ValueError, OverflowError):
            return "", raw
    if isinstance(cell.value, (datetime, date)):
        parsed = cell.value.date() if isinstance(cell.value, datetime) else cell.value
        return parsed.isoformat(), raw
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if not match:
        return "", raw
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat(), raw
    except ValueError:
        return "", raw


def _activities(raw: str) -> list[str]:
    source = _clean(raw)
    if not source:
        raise ValueError("Piacenza activity field is unexpectedly blank")
    values = [_clean(token) for token in source.split(",") if _clean(token)]
    if not values:
        raise ValueError(f"Piacenza activity field could not be tokenised: {source!r}")
    unknown = [token for token in values if token not in _ROMAN and token not in _REVIEWED_ACTIVITY_ANOMALIES]
    if unknown:
        raise ValueError(f"Piacenza activity vocabulary drift: {unknown!r} in {source!r}")
    return [f"Sezione {token}" if token in _ROMAN else token for token in values]


def _sheet_has_values(book: xlrd.book.Book, sheet: xlrd.sheet.Sheet) -> bool:
    return any(
        _cell_text(book, sheet, row, col)
        for row in range(sheet.nrows)
        for col in range(sheet.ncols)
    )


def _assert_empty_sheets(book: xlrd.book.Book, names: tuple[str, ...]) -> None:
    for name in names:
        sheet = book.sheet_by_name(name)
        if _sheet_has_values(book, sheet):
            raise ValueError(f"Piacenza workbook sheet {name!r} is no longer empty")


def _assert_no_values_outside(
    book: xlrd.book.Book,
    sheet: xlrd.sheet.Sheet,
    *,
    logical_rows: int,
    logical_cols: int,
) -> None:
    if sheet.nrows < logical_rows or sheet.ncols < logical_cols:
        raise ValueError(
            f"Piacenza logical table shrank: requires at least {logical_rows}x{logical_cols}, "
            f"got {sheet.nrows}x{sheet.ncols}"
        )
    for row in range(sheet.nrows):
        for col in range(sheet.ncols):
            if row < logical_rows and col < logical_cols:
                continue
            value = _cell_text(book, sheet, row, col)
            if value:
                raise ValueError(
                    f"Piacenza unexpected value outside audited logical table at "
                    f"row {row + 1}, column {col + 1}: {value!r}"
                )


def parse_piacenza_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _require_cfg(cfg, "piacenza-listed", "listed")
    book = _open_zip_workbook(path, _LISTED_MEMBER, _LISTED_SHEETS)
    sheet = book.sheet_by_name("Foglio1")
    _assert_no_values_outside(book, sheet, logical_rows=555, logical_cols=9)
    _assert_empty_sheets(book, ("Foglio2", "Foglio3"))
    header = tuple(_cell_text(book, sheet, 1, col) for col in range(9))
    if header != _LISTED_HEADER:
        raise ValueError(f"Piacenza listed header drift: {header!r}")
    if any(_cell_text(book, sheet, 2, col) for col in range(9)):
        raise ValueError("Piacenza listed spacer row changed")

    records: list[dict[str, Any]] = []
    malformed_listing = 0
    malformed_expiry = 0
    for row in range(3, 555):
        values = [_cell_text(book, sheet, row, col) for col in range(9)]
        if not any(values):
            raise ValueError(f"Piacenza listed unexpected blank row at source row {row + 1}")
        _order, registration, name, office, activity_raw, identifier_raw, _listing_text, _expiry_text, note = values
        if not registration or not name or not activity_raw or not identifier_raw:
            raise ValueError(f"Piacenza listed identity/layout drift at source row {row + 1}: {values!r}")
        if note not in {"", "IN FASE DI RINNOVO"}:
            raise ValueError(f"Piacenza listed status vocabulary drift at source row {row + 1}: {note!r}")
        listing_date, listing_raw = _source_date(book, sheet, row, 6)
        expiry_date, expiry_raw = _source_date(book, sheet, row, 7)
        if not listing_raw or not expiry_raw:
            raise ValueError(f"Piacenza listed source date unexpectedly blank at row {row + 1}")
        malformed_listing += not bool(listing_date)
        malformed_expiry += not bool(expiry_date)
        records.append(
            _record(
                cfg,
                len(records) + 1,
                name=name,
                office=office,
                identifier_raw=identifier_raw,
                activities=_activities(activity_raw),
                status="renewal_update_in_progress" if note else "listed",
                outcome_raw=note,
                listing_date=listing_date,
                expiry_date=expiry_date,
                primary_date_label="Data iscrizione",
                source_fields={
                    "registration_number": registration,
                    "requested_activities_source": activity_raw,
                    "listing_date_raw_variants": [listing_raw],
                    "expiry_date_raw_variants": [expiry_raw],
                    "malformed_date_pairs": [
                        value
                        for value in (
                            f"listing_date={listing_raw}" if not listing_date else "",
                            f"expiry_date={expiry_raw}" if not expiry_date else "",
                        )
                        if value
                    ],
                },
            )
        )

    diagnostics = {
        "parser": "piacenza_legacy_listed",
        "public_records": len(records),
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_only": sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records),
        "malformed_listing_dates_preserved": malformed_listing,
        "malformed_expiry_dates_preserved": malformed_expiry,
    }
    expected = {
        "public_records": 552,
        "status_counts": {"listed": 455, "renewal_update_in_progress": 97},
        "identifier_coverage": 540,
        "raw_identifier_only": 12,
        "malformed_listing_dates_preserved": 7,
        "malformed_expiry_dates_preserved": 7,
    }
    for key, value in expected.items():
        if diagnostics[key] != value:
            raise ValueError(f"Piacenza listed audited-boundary drift for {key}: {diagnostics[key]!r} != {value!r}")
    return ParsedBatch(records, diagnostics)


def parse_piacenza_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _require_cfg(cfg, "piacenza-applicants", "applicant")
    book = _open_zip_workbook(path, _APPLICANTS_MEMBER, _APPLICANT_SHEETS)
    sheet = book.sheet_by_name("Foglio1")
    _assert_no_values_outside(book, sheet, logical_rows=22, logical_cols=6)
    _assert_empty_sheets(book, ("Foglio2", "Foglio3"))
    if _cell_text(book, sheet, 0, 0) != _APPLICANT_TITLE:
        raise ValueError("Piacenza applicant title changed")
    for row in range(1, 4):
        if any(_cell_text(book, sheet, row, col) for col in range(6)):
            raise ValueError(f"Piacenza applicant spacer row {row + 1} changed")

    records: list[dict[str, Any]] = []
    for row in range(4, 22):
        values = [_cell_text(book, sheet, row, col) for col in range(6)]
        if not any(values):
            raise ValueError(f"Piacenza applicant unexpected blank row at source row {row + 1}")
        ordinal, name, office, identifier_raw, activity_raw, _date_text = values
        if ordinal:
            raise ValueError(f"Piacenza applicant first column is no longer blank at source row {row + 1}: {ordinal!r}")
        if not name or not office or not identifier_raw or not activity_raw:
            raise ValueError(f"Piacenza applicant identity/layout drift at source row {row + 1}: {values!r}")
        application_date, application_raw = _source_date(book, sheet, row, 5)
        if not application_date:
            raise ValueError(f"Piacenza applicant application-date drift at source row {row + 1}: {application_raw!r}")
        records.append(
            _record(
                cfg,
                len(records) + 1,
                name=name,
                office=office,
                identifier_raw=identifier_raw,
                activities=_activities(activity_raw),
                status="pending",
                application_date=application_date,
                primary_date_label="Data presentazione istanza",
                source_fields={
                    "requested_activities_source": activity_raw,
                    "application_date_raw": application_raw,
                },
            )
        )

    diagnostics = {
        "parser": "piacenza_legacy_applicants",
        "public_records": len(records),
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_only": sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records),
    }
    expected = {
        "public_records": 18,
        "status_counts": {"pending": 18},
        "identifier_coverage": 18,
        "raw_identifier_only": 0,
    }
    for key, value in expected.items():
        if diagnostics[key] != value:
            raise ValueError(f"Piacenza applicant audited-boundary drift for {key}: {diagnostics[key]!r} != {value!r}")
    return ParsedBatch(records, diagnostics)


PARSERS: dict[str, Callable[[Path, dict[str, Any]], ParsedBatch]] = {
    "piacenza_legacy_listed": parse_piacenza_listed,
    "piacenza_legacy_applicants": parse_piacenza_applicants,
}
