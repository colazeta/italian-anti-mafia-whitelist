from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record


LISTED_PARSER_NAME = "messina_listed"
APPLICANT_PARSER_NAME = "messina_applicants"
PARSER_VERSION = "1"

_EXPECTED_LISTED_PAGES = 9
_EXPECTED_LISTED_PAGE_ROWS = [88, 101, 102, 102, 102, 102, 101, 102, 80]
_EXPECTED_LISTED_RECORDS = 880
_EXPECTED_LISTED_STATUS = {"listed": 663, "renewal_update_in_progress": 217}
_EXPECTED_LISTED_IDENTIFIER_RECORDS = 880
_EXPECTED_LISTED_IDENTIFIER_VALUES = 880
_LISTED_SOURCE_UPDATE_MARKER = "ULTIMO AGGIORNAMENTO 10/09/2026"

_EXPECTED_APPLICANT_PAGES = 3
_EXPECTED_APPLICANT_PAGE_ROWS = [44, 69, 41]
_EXPECTED_APPLICANT_RECORDS = 154
_EXPECTED_APPLICANT_IDENTIFIER_RECORDS = 153
_EXPECTED_APPLICANT_IDENTIFIER_VALUES = 154
_EXPECTED_APPLICANT_BLANK_IDENTIFIER = 1
_EXPECTED_APPLICANT_MULTI_IDENTIFIER = 1
_REVIEWED_BLANK_APPLICANT = (2, 61, "SITEC S.R.L.", "TERME VIGLIATORE", "III-IV-V")
_REVIEWED_MULTI_IDENTIFIER = (
    "AVIOMARKETING S.P.A. UNIPERSONALE",
    "02578720837 03122600830",
    ("02578720837", "03122600830"),
)

_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_IDENTIFIER = re.compile(r"(?<![A-Za-z0-9])(?:\d{11}|[A-Za-z0-9]{16})(?![A-Za-z0-9])", re.I)
_APPLICANT_HEADER = [
    "Ragione Sociale",
    "Sede Legale",
    "Sede secondaria con rappresentan za stabile in Italia",
    "Codice fiscale/Partita IVA",
    "Attività per cui è richiesta l'iscrizione SEZIONI",
]
_LISTED_HEADER = [
    "Ragione Sociale",
    "Sede Legale",
    "Sede secondaria con rappresentanza stabile in Italia",
    "Codice fiscale/Partita IVA",
    "Data di iscrizione",
    "Data scadenza iscrizione",
    "Aggiorna mento in corso",
    "SEZIONI",
]


def _iso_if_valid(raw: str) -> str:
    raw = _clean(raw)
    if not raw or not _DATE.fullmatch(raw):
        return ""
    try:
        return datetime.strptime(raw, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return ""


def _strict_identifiers(raw: str) -> list[str]:
    values: list[str] = []
    for match in _IDENTIFIER.finditer(_clean(raw)):
        value = match.group(0).upper()
        if value not in values:
            values.append(value)
    return values


def _sections(raw: str) -> list[str]:
    raw = _clean(raw)
    if not raw:
        return []
    # The official PDFs inconsistently add spaces around the same hyphen
    # separator. Strip only surrounding whitespace; do not reinterpret any
    # non-Roman source token or alternate separator.
    parts = [part.strip() for part in raw.split("-") if part.strip()]
    if not parts or any(not re.fullmatch(r"[IVX]+", part) for part in parts):
        raise RuntimeError(f"Messina unreviewed section encoding: {raw!r}")
    return [f"Sezione {part}" for part in parts]


def _listed_status(update_raw: str) -> str:
    value = _clean(update_raw)
    if value == "":
        return "listed"
    if value == "SI":
        return "renewal_update_in_progress"
    raise RuntimeError(f"Messina unreviewed listed update marker: {value!r}")


def parse_messina_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    extracted: list[tuple[int, int, list[str]]] = []
    page_counts: list[int] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _EXPECTED_LISTED_PAGES:
            raise RuntimeError(
                f"Messina listed page denominator drift: expected {_EXPECTED_LISTED_PAGES}, got {len(pdf.pages)}"
            )

        for page_number, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if _LISTED_SOURCE_UPDATE_MARKER not in text:
                raise RuntimeError(
                    f"Messina listed page {page_number}: approved source-update marker missing"
                )
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(
                    f"Messina listed page {page_number}: expected one reviewed table, got {len(tables)}"
                )
            table = tables[0].extract()
            page_rows = 0
            saw_header = False
            for table_row, raw_row in enumerate(table):
                cells = [_clean(value) for value in raw_row]
                if len(cells) != 8:
                    raise RuntimeError(
                        f"Messina listed page {page_number} row {table_row}: expected 8 cells, got {len(cells)}"
                    )
                if cells == _LISTED_HEADER:
                    saw_header = True
                    continue
                first = cells[0]
                if (
                    not any(cells)
                    or first.startswith("PREFETTURA")
                    or first.startswith("Sezione ")
                    or first == "**DATI NON ORDINATI**"
                ):
                    continue

                name, office, secondary, identifier_raw, listing_raw, expiry_raw, update_raw, sections_raw = cells
                identifiers = _strict_identifiers(identifier_raw)
                if not name or len(identifiers) != 1:
                    raise RuntimeError(
                        f"Messina listed page {page_number} row {table_row}: unreviewed company identity {cells!r}"
                    )
                if not _iso_if_valid(listing_raw) or not _iso_if_valid(expiry_raw):
                    raise RuntimeError(
                        f"Messina listed page {page_number} row {table_row}: unreviewed date {cells!r}"
                    )
                _listed_status(update_raw)
                _sections(sections_raw)
                extracted.append((page_number, table_row, cells))
                page_rows += 1

            if not saw_header:
                raise RuntimeError(f"Messina listed page {page_number}: reviewed header missing")
            page_counts.append(page_rows)

    if page_counts != _EXPECTED_LISTED_PAGE_ROWS:
        raise RuntimeError(
            f"Messina listed page-row boundary drift: expected {_EXPECTED_LISTED_PAGE_ROWS!r}, got {page_counts!r}"
        )
    if len(extracted) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(
            f"Messina listed denominator drift: expected {_EXPECTED_LISTED_RECORDS}, got {len(extracted)}"
        )

    records: list[dict[str, Any]] = []
    for ordinal, (_page_number, _table_row, cells) in enumerate(extracted, 1):
        name, office, secondary, identifier_raw, listing_raw, expiry_raw, update_raw, sections_raw = cells
        record = _record(
            cfg,
            ordinal,
            name=name,
            office=office,
            secondary=secondary,
            identifier_raw=identifier_raw,
            activities=_sections(sections_raw),
            status=_listed_status(update_raw),
            outcome_raw=update_raw,
            listing_date=listing_raw,
            expiry_date=expiry_raw,
            primary_date_label="Data iscrizione",
            source_fields={
                "sections_raw": sections_raw,
                "listing_date_raw": listing_raw,
                "expiry_date_raw": expiry_raw,
                "aggiornamento_in_corso": update_raw,
            },
        )
        record["identifiers"] = _strict_identifiers(identifier_raw)
        records.append(record)

    statuses = Counter(record["source_status"] for record in records)
    identifier_records = sum(bool(record["identifiers"]) for record in records)
    identifier_values = [value for record in records for value in record["identifiers"]]
    if dict(statuses) != _EXPECTED_LISTED_STATUS:
        raise RuntimeError(
            f"Messina listed status boundary drift: expected {_EXPECTED_LISTED_STATUS!r}, got {dict(statuses)!r}"
        )
    if identifier_records != _EXPECTED_LISTED_IDENTIFIER_RECORDS:
        raise RuntimeError(
            f"Messina listed identifier-record boundary drift: {identifier_records}"
        )
    if (
        len(identifier_values) != _EXPECTED_LISTED_IDENTIFIER_VALUES
        or len(set(identifier_values)) != len(identifier_values)
    ):
        raise RuntimeError(
            "Messina listed identifier-value boundary drift: "
            f"values={len(identifier_values)}, unique={len(set(identifier_values))}"
        )

    diagnostics = {
        "parser": LISTED_PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "pages": _EXPECTED_LISTED_PAGES,
        "page_rows": page_counts,
        "public_records": len(records),
        "status_counts": dict(statuses),
        "identifier_coverage": identifier_records,
        "identifier_values": len(identifier_values),
        "source_update_marker": "2026-09-10",
    }
    return ParsedBatch(records, diagnostics)


def _applicant_data_table(page: Any, page_number: int) -> Any:
    candidates = []
    for table in page.find_tables():
        rows = table.extract()
        if not rows:
            continue
        header = [_clean(value) for value in rows[0]]
        if header == _APPLICANT_HEADER:
            candidates.append(table)
    if len(candidates) != 1:
        raise RuntimeError(
            f"Messina applicant page {page_number}: expected one reviewed company table, got {len(candidates)}"
        )
    return candidates[0]


def _applicant_dates(page: Any, page_number: int) -> list[tuple[float, str]]:
    dates: list[tuple[float, str]] = []
    for word in page.extract_words():
        raw = _clean(word.get("text"))
        x0 = float(word.get("x0", 0.0))
        if _DATE.fullmatch(raw) and x0 >= 540.0:
            if not _iso_if_valid(raw):
                raise RuntimeError(
                    f"Messina applicant page {page_number}: invalid source date {raw!r}"
                )
            dates.append((float(word.get("top", 0.0)), raw))
    dates.sort(key=lambda item: item[0])
    return dates


def parse_messina_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    extracted: list[tuple[int, int, list[str], str]] = []
    page_counts: list[int] = []
    blank_reviewed: list[tuple[int, int, str, str, str]] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _EXPECTED_APPLICANT_PAGES:
            raise RuntimeError(
                f"Messina applicant page denominator drift: expected {_EXPECTED_APPLICANT_PAGES}, got {len(pdf.pages)}"
            )

        for page_number, page in enumerate(pdf.pages, 1):
            table_obj = _applicant_data_table(page, page_number)
            table = table_obj.extract()
            company_rows = [
                [_clean(value) for value in row]
                for row in table[1:]
                if any(_clean(value) for value in row)
            ]
            dates = _applicant_dates(page, page_number)
            if len(company_rows) != len(dates):
                raise RuntimeError(
                    f"Messina applicant page {page_number}: company/date alignment drift: "
                    f"rows={len(company_rows)}, dates={len(dates)}"
                )

            for table_row, (cells, (_date_top, application_raw)) in enumerate(
                zip(company_rows, dates), 1
            ):
                if len(cells) != 5:
                    raise RuntimeError(
                        f"Messina applicant page {page_number} row {table_row}: expected 5 cells, got {len(cells)}"
                    )
                name, office, secondary, identifier_raw, sections_raw = cells
                if not name or not office:
                    raise RuntimeError(
                        f"Messina applicant page {page_number} row {table_row}: blank company identity {cells!r}"
                    )
                identifiers = _strict_identifiers(identifier_raw)
                if not identifiers:
                    blank_reviewed.append(
                        (page_number, table_row, name, office, sections_raw)
                    )
                _sections(sections_raw)
                extracted.append(
                    (page_number, table_row, cells, application_raw)
                )
            page_counts.append(len(company_rows))

    if page_counts != _EXPECTED_APPLICANT_PAGE_ROWS:
        raise RuntimeError(
            f"Messina applicant page-row boundary drift: expected {_EXPECTED_APPLICANT_PAGE_ROWS!r}, got {page_counts!r}"
        )
    if len(extracted) != _EXPECTED_APPLICANT_RECORDS:
        raise RuntimeError(
            f"Messina applicant denominator drift: expected {_EXPECTED_APPLICANT_RECORDS}, got {len(extracted)}"
        )
    if blank_reviewed != [_REVIEWED_BLANK_APPLICANT]:
        raise RuntimeError(
            f"Messina reviewed blank-identifier boundary drift: expected {_REVIEWED_BLANK_APPLICANT!r}, got {blank_reviewed!r}"
        )

    records: list[dict[str, Any]] = []
    for ordinal, (_page_number, _table_row, cells, application_raw) in enumerate(
        extracted, 1
    ):
        name, office, secondary, identifier_raw, sections_raw = cells
        record = _record(
            cfg,
            ordinal,
            name=name,
            office=office,
            secondary=secondary,
            identifier_raw=identifier_raw,
            activities=_sections(sections_raw),
            status="pending",
            application_date=application_raw,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "sections_raw": sections_raw,
                "application_date_raw": application_raw,
            },
        )
        record["identifiers"] = _strict_identifiers(identifier_raw)
        records.append(record)

    statuses = Counter(record["source_status"] for record in records)
    identifier_records = sum(bool(record["identifiers"]) for record in records)
    identifier_values = [
        value for record in records for value in record["identifiers"]
    ]
    blank_identifier = sum(not record["identifier_field_raw"] for record in records)
    multiple_identifier_records = [
        (
            record["name"],
            record["identifier_field_raw"],
            tuple(record["identifiers"]),
        )
        for record in records
        if len(record["identifiers"]) > 1
    ]

    if statuses != Counter({"pending": _EXPECTED_APPLICANT_RECORDS}):
        raise RuntimeError(
            f"Messina applicant status boundary drift: {dict(statuses)!r}"
        )
    if identifier_records != _EXPECTED_APPLICANT_IDENTIFIER_RECORDS:
        raise RuntimeError(
            f"Messina applicant identifier-record boundary drift: {identifier_records}"
        )
    if (
        len(identifier_values) != _EXPECTED_APPLICANT_IDENTIFIER_VALUES
        or len(set(identifier_values)) != len(identifier_values)
    ):
        raise RuntimeError(
            "Messina applicant identifier-value boundary drift: "
            f"values={len(identifier_values)}, unique={len(set(identifier_values))}"
        )
    if blank_identifier != _EXPECTED_APPLICANT_BLANK_IDENTIFIER:
        raise RuntimeError(
            f"Messina applicant blank-identifier boundary drift: {blank_identifier}"
        )
    if multiple_identifier_records != [_REVIEWED_MULTI_IDENTIFIER]:
        raise RuntimeError(
            f"Messina applicant multi-identifier boundary drift: {multiple_identifier_records!r}"
        )

    diagnostics = {
        "parser": APPLICANT_PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "pages": _EXPECTED_APPLICANT_PAGES,
        "page_rows": page_counts,
        "public_records": len(records),
        "status_counts": dict(statuses),
        "identifier_coverage": identifier_records,
        "identifier_values": len(identifier_values),
        "blank_identifier": blank_identifier,
        "multiple_identifier_records": len(multiple_identifier_records),
    }
    return ParsedBatch(records, diagnostics)


PARSERS = {
    LISTED_PARSER_NAME: parse_messina_listed,
    APPLICANT_PARSER_NAME: parse_messina_applicants,
}
