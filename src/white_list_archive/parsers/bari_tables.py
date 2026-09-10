from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-08-31"
_LISTED_PAGE_COUNTS = [41, 36, 31, 35, 38, 32, 37, 36, 42, 38, 38, 38, 36, 39, 40, 34, 34, 36, 37, 41, 40, 41, 37, 41, 32, 39, 39, 38, 19]
_APPLICANT_PAGE_COUNTS = [40, 44, 42, 46, 45, 44, 42, 46, 46, 46, 48, 49, 44, 23]
_BAD_LISTED_DATES = {"06/'3/2025", "02/07/024", "1607/2025", "19+/06/2027", "28/01/207"}
_BAD_APPLICANT_DATES = {"18/07/18 - 11/05/23"}
_VALID_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_VALID_IDENTIFIER = re.compile(r"(?<![A-Za-z0-9])(?:\d{11}|[A-Za-z0-9]{16})(?![A-Za-z0-9])")

# pdfplumber splits a small number of visually complete Bari source rows. These
# repairs are keyed to exact page/company positions in the byte-pinned edition;
# unexpected geometry still fails closed.
_LISTED_NAME_REPAIRS = {
    (7, 19): "D.R. COSTRUZIONI SRL",
    (27, 6): "TECNOELEVA SRL",
    (27, 32): "TRA.VAL SRL",
    (28, 9): "TRIGGIANI & C. SNC",
    (28, 14): "TUBI E SERVIZI S.R.L.",
    (28, 20): "V.L. COSTRUZIONI GENERALI DI BIANCO NUNZIA",
}
_APPLICANT_NAME_REPAIRS = {(13, 38): "THE WORLD S.R.L."}


def _strict_identifiers(raw: str) -> list[str]:
    values: list[str] = []
    for match in _VALID_IDENTIFIER.finditer(_clean(raw)):
        value = match.group(0).upper()
        if value not in values:
            values.append(value)
    return values


def _source_date(raw: str, *, allowlist: set[str], source_key: str, page: int, row: int) -> str:
    value = _clean(raw)
    if not value:
        return ""
    match = _VALID_DATE.fullmatch(value)
    if match:
        day, month, year = map(int, match.groups())
        try:
            return date(year, month, day).isoformat()
        except ValueError as exc:
            raise RuntimeError(f"{source_key}: invalid calendar date at page {page} row {row}: {raw!r}") from exc
    if value in allowlist:
        return ""
    raise RuntimeError(f"{source_key}: unreviewed date typography at page {page} row {row}: {raw!r}")


def _sections(row: list[str], *, source_key: str, page: int, row_number: int) -> tuple[list[str], list[str]]:
    markers = row[6:16]
    if len(markers) != 10:
        raise RuntimeError(f"{source_key}: sector geometry drift at page {page} row {row_number}")
    sections: list[str] = []
    for index, marker in enumerate(markers, 1):
        value = _clean(marker)
        if not value:
            continue
        if value.casefold() != "x":
            raise RuntimeError(
                f"{source_key}: unreviewed sector marker at page {page} row {row_number}, section {index}: {value!r}"
            )
        sections.append(f"Sezione {index}")
    if not sections:
        raise RuntimeError(f"{source_key}: no source-backed sector at page {page} row {row_number}")
    return sections, markers


def _company_rows(path: Path, *, source_key: str, page_counts: list[int], width: int) -> list[tuple[int, int, list[str]]]:
    output: list[tuple[int, int, list[str]]] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != len(page_counts):
            raise RuntimeError(f"{source_key}: page-count drift; expected {len(page_counts)}, got {len(pdf.pages)}")
        for page_number, (page, expected_count) in enumerate(zip(pdf.pages, page_counts), 1):
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(f"{source_key}: page {page_number}: expected one table, got {len(tables)}")
            extracted = tables[0].extract()
            if not extracted:
                raise RuntimeError(f"{source_key}: page {page_number}: empty table")
            rows = [[_clean(cell) for cell in row] for row in extracted[1:] if any(_clean(cell) for cell in row)]
            if len(rows) < 2 or len(rows[0]) != width or len(rows[1]) != width:
                raise RuntimeError(f"{source_key}: page {page_number}: administrative-row geometry drift")
            if "ELENCO IMPRESE" not in rows[0][2] or rows[1][-1] != "Stato istruttoria":
                raise RuntimeError(f"{source_key}: page {page_number}: title/header drift")
            companies = rows[2:]
            if len(companies) != expected_count:
                raise RuntimeError(
                    f"{source_key}: page {page_number}: expected {expected_count} company rows, got {len(companies)}"
                )
            for row_number, row in enumerate(companies, 1):
                if len(row) != width:
                    raise RuntimeError(f"{source_key}: page {page_number} row {row_number}: width drift")
                output.append((page_number, row_number, row))
    return output


def _listed_row_repair(page: int, row_number: int, row: list[str]) -> list[str]:
    repaired = list(row)
    key = (page, row_number)
    if key in _LISTED_NAME_REPAIRS:
        repaired[0] = _LISTED_NAME_REPAIRS[key]
    if key == (19, 11):
        repaired = [
            "MEDITRANS SRL", "CORATO", "CONTRADA MACCARONE SNC", "-", "05945400728", "",
            "", "", "", "", "", "X", "", "", "", "", "14/05/2025", "14/05/2026", "SI", "richiesta PERMANENZA",
        ]
    elif key == (19, 12):
        repaired = [
            "MEIT MULTISERVICES SRL", "BARI", "Via Bottalico n. 43", "-", "05691520729", "",
            "X", "X", "X", "", "X", "X", "X", "X", "X", "X", "27/03/2026", "27/03/2027", "", "ISCRITTA",
        ]
    return repaired


def _applicant_row_repair(page: int, row_number: int, row: list[str]) -> list[str]:
    repaired = list(row)
    key = (page, row_number)
    if key in _APPLICANT_NAME_REPAIRS:
        repaired[0] = _APPLICANT_NAME_REPAIRS[key]
    if key == (14, 5):
        repaired = [
            "TRIDENTE DOMENICO", "MOLFETTA", "Via Leonardo Mezzina n. 11", "-", "07151350720", "",
            "", "", "", "", "X", "", "", "", "", "", "10/11/2023", "in istruttoria",
        ]
    elif key == (14, 6):
        repaired = [
            "TRIVEL PUGLIA SRL", "ALTAMURA", "Via Teramo n. 14", "-", "08435710721", "",
            "X", "", "", "", "", "", "", "", "", "", "22/04/2021", "in istruttoria",
        ]
    elif key == (14, 7):
        repaired = [
            "UNICA SRL", "BARI", "Via Gaetano Ferorelli n. 1", "-", "17130341005", "",
            "", "X", "", "", "", "", "", "", "", "", "06/02/2026", "in istruttoria",
        ]
    return repaired


def _listed_status(row: list[str], *, page: int, row_number: int) -> str:
    raw = _clean(row[19])
    folded = raw.casefold()
    if folded == "iscritta":
        return "listed"
    if folded in {"richiesta permanenza", "in aggiornamento"}:
        return "renewal_update_in_progress"
    if not raw and (page, row_number) == (23, 13) and _clean(row[18]).casefold() == "si":
        return "renewal_update_in_progress"
    if not raw and (page, row_number) == (24, 20):
        return "listed"
    raise RuntimeError(f"bari-listed: unreviewed source status at page {page} row {row_number}: {raw!r}")


def parse_bari_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    rows = _company_rows(path, source_key=cfg["source_key"], page_counts=_LISTED_PAGE_COUNTS, width=20)
    records: list[dict[str, Any]] = []
    for ordinal, (page, row_number, raw_row) in enumerate(rows, 1):
        row = _listed_row_repair(page, row_number, raw_row)
        name = _clean(row[0])
        if not name:
            raise RuntimeError(f"{cfg['source_key']}: unresolved legal name at page {page} row {row_number}")
        sections, sector_markers = _sections(row, source_key=cfg["source_key"], page=page, row_number=row_number)
        listing = _source_date(row[16], allowlist=_BAD_LISTED_DATES, source_key=cfg["source_key"], page=page, row=row_number)
        expiry = _source_date(row[17], allowlist=_BAD_LISTED_DATES, source_key=cfg["source_key"], page=page, row=row_number)
        status = _listed_status(row, page=page, row_number=row_number)
        record = _record(
            cfg,
            ordinal,
            name=name,
            office=row[2],
            identifier_raw=row[4],
            activities=sections,
            status=status,
            outcome_raw=row[19],
            listing_date=listing,
            expiry_date=expiry,
            primary_date_label="Data iscrizione",
            source_fields={
                "source_page": page,
                "source_page_row": row_number,
                "registered_office_municipality": row[1],
                "stable_representation_in_italy_raw": row[3],
                "sector_markers_raw": sector_markers,
                "listing_date_raw": row[16],
                "expiry_date_raw": row[17],
                "permanence_raw": row[18],
                "status_raw": row[19],
                "row_repaired_from_pdf_geometry": row != raw_row,
            },
        )
        record["identifiers"] = _strict_identifiers(row[4])
        records.append(record)
    statuses = Counter(record["source_status"] for record in records)
    expected = Counter({"listed": 754, "renewal_update_in_progress": 311})
    if statuses != expected:
        raise RuntimeError(f"{cfg['source_key']}: reviewed status denominator drift: {dict(statuses)}")
    return ParsedBatch(records, {
        "parser": "bari_listed",
        "public_records": len(records),
        "status_counts": dict(statuses),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "identifier_raw_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "dropped_date_rows": 0,
    })


def parse_bari_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    rows = _company_rows(path, source_key=cfg["source_key"], page_counts=_APPLICANT_PAGE_COUNTS, width=18)
    records: list[dict[str, Any]] = []
    for ordinal, (page, row_number, raw_row) in enumerate(rows, 1):
        row = _applicant_row_repair(page, row_number, raw_row)
        # One current source row (page 1 row 1, CF/P.IVA 07906600726) has no
        # recoverable legal-name text. Preserve the blank instead of inventing it.
        if not _clean(row[0]) and (page, row_number) != (1, 1):
            raise RuntimeError(f"{cfg['source_key']}: unresolved legal name at page {page} row {row_number}")
        if _clean(row[17]).casefold() != "in istruttoria":
            raise RuntimeError(f"{cfg['source_key']}: unreviewed applicant status at page {page} row {row_number}: {row[17]!r}")
        sections, sector_markers = _sections(row, source_key=cfg["source_key"], page=page, row_number=row_number)
        application = _source_date(row[16], allowlist=_BAD_APPLICANT_DATES, source_key=cfg["source_key"], page=page, row=row_number)
        record = _record(
            cfg,
            ordinal,
            name=row[0],
            office=row[2],
            identifier_raw=row[4],
            activities=sections,
            status="pending",
            outcome_raw=row[17],
            application_date=application,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "source_page": page,
                "source_page_row": row_number,
                "registered_office_municipality": row[1],
                "stable_representation_in_italy_raw": row[3],
                "sector_markers_raw": sector_markers,
                "application_date_raw": row[16],
                "status_raw": row[17],
                "row_repaired_from_pdf_geometry": row != raw_row,
                "legal_name_unrecoverable_in_source_extraction": (page, row_number) == (1, 1),
            },
        )
        record["identifiers"] = _strict_identifiers(row[4])
        records.append(record)
    statuses = Counter(record["source_status"] for record in records)
    if statuses != Counter({"pending": 605}):
        raise RuntimeError(f"{cfg['source_key']}: reviewed applicant denominator drift: {dict(statuses)}")
    return ParsedBatch(records, {
        "parser": "bari_applicants",
        "public_records": len(records),
        "status_counts": dict(statuses),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "identifier_raw_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "dropped_date_rows": 0,
    })


PARSERS = {"bari_listed": parse_bari_listed, "bari_applicants": parse_bari_applicants}
