from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _record

PARSER_VERSION = "1"
_LISTED_PAGES = 114
_APPLICANT_PAGES = 20
_EXPECTED_LISTED_RECORDS = 652
_EXPECTED_APPLICANT_RECORDS = 110
_EXPECTED_LISTED_STATUS = {"listed": 528, "renewal_update_in_progress": 124}
_EXPECTED_SECTIONS = {str(i) for i in range(1, 11)}
_RENEWAL = "RICHIESTO RINNOVO"

_REVIEWED_LISTED_PAGE47 = (
    "FISIA ITALIMPIANTI SPA",
    "02340830997",
    "VIA DE MARINI 1",
    "GENOVA",
    "IX",
    "06/09/2024",
    "05/09/2026",
    _RENEWAL,
)
_REVIEWED_APPLICANT_PAGE7 = (
    ("CRESTA & DELFINO SRL", "01345600991", "VIA RUSPOLI 39/7", "GENOVA", "VI - X", "08/09/2025", "IN ISTRUTTORIA"),
    ("CUNEO LUIGI", "01014720990", "VIA COLOMBO 2", "CARASCO", "VII", "05/09/2025", "IN ISTRUTTORIA"),
    ("CURZI LUIGI - AUTOTRASPORTI C/TERZI", "01206650995", "VIA DEI GIUSTINIANI 6/4", "GENOVA", "VI", "25/03/2026", "IN ISTRUTTORIA"),
    ("DAMA SRL", "01643320995", "VIA TORTOSA 56 R", "GENOVA", "III - IV", "26/03/2026", "IN ISTRUTTORIA"),
    ("DASSORI SRL", "01373850997", "VIA ADAMOLI 491", "GENOVA", "IX", "31/03/2026", "IN ISTRUTTORIA"),
    ("DE BREEZE SRL", "02795530992", "VIA FIESCHI 15/5", "GENOVA", "IV", "1 9 / 0 5 / 2 0 2 6", "IN ISTRUTTORIA"),
)
_REVIEWED_APPLICANT_PAGE9 = (
    "EDILQUADRIFOGLIO SRL",
    "01660680990",
    "VIA CESAREA, 11/6",
    "GENOVA",
    "III - IV",
    "03/07/2026",
    "IN ISTRUTTORIA",
)
_REVIEWED_SECTION_FIELDS = {
    ("listed", "CEMENBIT SRL", ""): ["5"],
    ("listed", "ECO ERIDANIA SPA", "Se. V"): ["5"],
    ("listed", "F.LLI BOVO SRL", "Sex. IX"): ["9"],
    ("listed", "LA PORTOFINESE SRL", "Sez.. IV"): ["4"],
    ("listed", "FISIA ITALIMPIANTI SPA", ""): ["9"],
    ("applicant", "CRESTA & DELFINO SRL", ""): ["6", "10"],
    ("applicant", "CUNEO LUIGI", ""): ["7"],
    ("applicant", "CURZI LUIGI - AUTOTRASPORTI C/TERZI", ""): ["6"],
    ("applicant", "DAMA SRL", ""): ["3", "4"],
    ("applicant", "DASSORI SRL", ""): ["9"],
    ("applicant", "DE BREEZE SRL", ""): ["4"],
    ("applicant", "EDILQUADRIFOGLIO SRL", ""): ["3", "4"],
}

_REVIEWED_INVALID_DATE_FIELDS = {
    ("listed", "GENOVARENT SRL", "listing", "26//09/2023"),
    ("applicant", "LO SCACCIA PENSIERI SRL", "application", "16/072026"),
}


def _compact(value: Any) -> str:
    return re.sub(r"\s+", "", _clean(value)).casefold()


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _parse_date(value: str) -> str:
    raw = _clean(value)
    if not raw:
        return ""
    compact = re.sub(r"\s+", "", raw)
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", compact):
        raise RuntimeError(f"Genova date drift: {raw!r}")
    try:
        return datetime.strptime(compact, "%d/%m/%Y").date().isoformat()
    except ValueError as exc:
        raise RuntimeError(f"Genova invalid calendar date: {raw!r}") from exc


def _parse_observed_date(value: str, *, scope: str, name: str, field: str) -> str:
    raw = _clean(value)
    if (scope, name, field, raw) in _REVIEWED_INVALID_DATE_FIELDS:
        return ""
    return _parse_date(raw)


def _sections(value: str, *, scope: str, name: str) -> list[str]:
    raw = _clean(value)
    reviewed = _REVIEWED_SECTION_FIELDS.get((scope, name, raw))
    if reviewed is not None:
        return reviewed
    numbers = re.findall(r"(?<!\d)(10|[1-9])(?!\d)", raw)
    out: list[str] = []
    for number in numbers:
        if number not in _EXPECTED_SECTIONS:
            raise RuntimeError(f"Genova unexpected section {number!r}")
        if number not in out:
            out.append(number)
    if raw and not out:
        raise RuntimeError(f"Genova section drift: {raw!r}")
    return out


def _strict_identifiers(raw_value: str) -> list[str]:
    raw = _clean(raw_value)
    if not raw:
        return []
    tokens = re.findall(r"\d+", raw)
    if len(tokens) != 1:
        return []
    token = tokens[0]
    if len(token) != 11:
        return []
    if re.sub(r"\D", "", raw) != token:
        return []
    return [token]


def _listed_rows(path: Path) -> tuple[list[dict[str, Any]], int, int]:
    rows: list[dict[str, Any]] = []
    reviewed_page47 = 0
    shifted_leading_blank_rows = 0
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGES:
            raise RuntimeError(f"Genova listed page-count drift: {len(pdf.pages)}")
        ordinal = 0
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            for table_index, table in enumerate(tables, start=1):
                for table_row, source_row in enumerate(table or [], start=1):
                    cells = [_clean(cell) for cell in (source_row or [])]
                    if not any(cells):
                        continue
                    compact = [_compact(cell) for cell in cells]
                    if any("ragionesociale" in cell for cell in compact):
                        continue
                    if page_number == 47 and _compact(" ".join(cells)) == _compact(" ".join(_REVIEWED_LISTED_PAGE47)):
                        cells = list(_REVIEWED_LISTED_PAGE47)
                        reviewed_page47 += 1
                    if len(cells) == 9 and not cells[0] and cells[1]:
                        cells = cells[1:]
                        shifted_leading_blank_rows += 1
                    if len(cells) != 8:
                        raise RuntimeError(
                            f"Genova listed table geometry drift on page {page_number}, table {table_index}, row {table_row}: {cells!r}"
                        )
                    name = cells[0]
                    if not name:
                        raise RuntimeError(f"Genova listed blank name on page {page_number}, row {table_row}")
                    section_values = _sections(cells[4], scope="listed", name=name)
                    if not section_values:
                        raise RuntimeError(f"Genova listed missing section for {name!r}")
                    listing_date = _parse_observed_date(cells[5], scope="listed", name=name, field="listing")
                    expiry_date = _parse_observed_date(cells[6], scope="listed", name=name, field="expiry")
                    update_raw = cells[7]
                    update_compact = _compact(update_raw)
                    if update_raw and update_compact != _compact(_RENEWAL):
                        raise RuntimeError(f"Genova listed update-status drift for {name!r}: {update_raw!r}")
                    ordinal += 1
                    rows.append(
                        {
                            "ordinal": ordinal,
                            "name": name,
                            "identifier_raw": cells[1],
                            "address": cells[2],
                            "secondary": cells[3],
                            "sections": section_values,
                            "listing_raw": cells[5],
                            "listing_date": listing_date,
                            "expiry_raw": cells[6],
                            "expiry_date": expiry_date,
                            "update_raw": update_raw,
                            "source_status": "renewal_update_in_progress" if update_raw else "listed",
                            "locator": f"p{page_number}:t{table_index}:r{table_row}",
                        }
                    )
    return rows, reviewed_page47, shifted_leading_blank_rows


def _applicant_rows(path: Path) -> tuple[list[dict[str, Any]], int, int]:
    rows: list[dict[str, Any]] = []
    reviewed_page7 = 0
    reviewed_page9 = 0
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGES:
            raise RuntimeError(f"Genova applicant page-count drift: {len(pdf.pages)}")
        ordinal = 0
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            for table_index, table in enumerate(tables, start=1):
                for table_row, source_row in enumerate(table or [], start=1):
                    cells = [_clean(cell) for cell in (source_row or [])]
                    if not any(cells):
                        continue
                    compact = [_compact(cell) for cell in cells]
                    if any("ragionesociale" in cell for cell in compact):
                        continue
                    if page_number == 7 and table_index == 1 and table_row == 1:
                        if len(cells) != 7:
                            raise RuntimeError(f"Genova applicant page-7 geometry drift: {cells!r}")
                        page_compact = _compact(page.extract_text() or "")
                        expected_compact = _compact(" ".join(" ".join(row) for row in _REVIEWED_APPLICANT_PAGE7))
                        if expected_compact not in page_compact:
                            # The PDF text layer can interleave the six reviewed records. Preserve the
                            # exact evidence guard by requiring each reviewed row's key fields instead.
                            for reviewed in _REVIEWED_APPLICANT_PAGE7:
                                for token in (reviewed[0], reviewed[1], reviewed[5], reviewed[6]):
                                    if _compact(token) not in page_compact:
                                        raise RuntimeError("Genova applicant page-7 reconstruction no longer supported by page text")
                        for reviewed in _REVIEWED_APPLICANT_PAGE7:
                            ordinal += 1
                            row = list(reviewed)
                            rows.append(
                                {
                                    "ordinal": ordinal,
                                    "name": row[0],
                                    "identifier_raw": row[1],
                                    "address": row[2],
                                    "secondary": row[3],
                                    "sections": _sections(row[4], scope="applicant", name=row[0]),
                                    "application_raw": row[5],
                                    "application_date": _parse_observed_date(row[5], scope="applicant", name=row[0], field="application"),
                                    "outcome_raw": row[6],
                                    "locator": f"p7:reviewed:{ordinal}",
                                }
                            )
                            reviewed_page7 += 1
                        continue
                    if page_number == 9 and table_index == 1 and table_row == 1:
                        page_compact = _compact(page.extract_text() or "")
                        reviewed_support = "edilquadrifogliosrl0166068099003/07/2026inistruttoriaviacesarea,11/6"
                        if reviewed_support not in page_compact:
                            raise RuntimeError("Genova applicant page-9 reconstruction no longer supported by page text")
                        ordinal += 1
                        row = list(_REVIEWED_APPLICANT_PAGE9)
                        rows.append(
                            {
                                "ordinal": ordinal,
                                "name": row[0],
                                "identifier_raw": row[1],
                                "address": row[2],
                                "secondary": row[3],
                                "sections": _sections(row[4], scope="applicant", name=row[0]),
                                "application_raw": row[5],
                                "application_date": _parse_observed_date(row[5], scope="applicant", name=row[0], field="application"),
                                "outcome_raw": row[6],
                                "locator": f"p9:reviewed:{ordinal}",
                            }
                        )
                        reviewed_page9 += 1
                        continue
                    if len(cells) == 8 and not cells[0] and cells[1]:
                        cells = cells[1:]
                    if len(cells) != 7:
                        raise RuntimeError(
                            f"Genova applicant table geometry drift on page {page_number}, table {table_index}, row {table_row}: {cells!r}"
                        )
                    name = cells[0]
                    if not name:
                        raise RuntimeError(f"Genova applicant blank name on page {page_number}, row {table_row}")
                    outcome = _compact(cells[6])
                    if outcome != _compact("IN ISTRUTTORIA"):
                        raise RuntimeError(f"Genova applicant outcome drift for {name!r}: {cells[6]!r}")
                    ordinal += 1
                    rows.append(
                        {
                            "ordinal": ordinal,
                            "name": name,
                            "identifier_raw": cells[1],
                            "address": cells[2],
                            "secondary": cells[3],
                            "sections": _sections(cells[4], scope="applicant", name=name),
                            "application_raw": cells[5],
                            "application_date": _parse_observed_date(cells[5], scope="applicant", name=name, field="application"),
                            "outcome_raw": cells[6],
                            "locator": f"p{page_number}:t{table_index}:r{table_row}",
                        }
                    )
    return rows, reviewed_page7, reviewed_page9


def parse_genova_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    rows, reviewed_page47, shifted_leading_blank_rows = _listed_rows(path)
    if len(rows) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(f"Genova listed record-count drift: {len(rows)}")
    records: list[dict[str, Any]] = []
    for row in rows:
        record = _record(
            cfg=cfg,
            row_ordinal=row["ordinal"],
            name=row["name"],
            identifier_raw=row["identifier_raw"],
            office=row["address"],
            status=row["source_status"],
            listing_date=row["listing_date"],
            expiry_date=row["expiry_date"],
            application_date="",
            primary_date_label="Data iscrizione",
            source_fields={
                "sections": row["sections"],
                "secondary_office_raw": row["secondary"],
                "listing_date_raw": row["listing_raw"],
                "expiry_date_raw": row["expiry_raw"],
                "renewal_raw": row["update_raw"],
                "source_locator": row["locator"],
            },
        )
        record["identifiers"] = _strict_identifiers(row["identifier_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_LISTED_STATUS:
        raise RuntimeError(f"Genova listed status drift: {status_counts!r}")
    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "genova_listed",
            "parser_version": PARSER_VERSION,
            "source_pages": _LISTED_PAGES,
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
            "reviewed_page47_reconstructions": reviewed_page47,
            "shifted_leading_blank_rows": shifted_leading_blank_rows,
        },
    )


def parse_genova_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    rows, reviewed_page7, reviewed_page9 = _applicant_rows(path)
    if len(rows) != _EXPECTED_APPLICANT_RECORDS:
        raise RuntimeError(f"Genova applicant record-count drift: {len(rows)}")
    records: list[dict[str, Any]] = []
    for row in rows:
        record = _record(
            cfg=cfg,
            row_ordinal=row["ordinal"],
            name=row["name"],
            identifier_raw=row["identifier_raw"],
            office=row["address"],
            status="pending",
            listing_date="",
            expiry_date="",
            application_date=row["application_date"],
            primary_date_label="Data presentazione istanza",
            source_fields={
                "sections": row["sections"],
                "secondary_office_raw": row["secondary"],
                "application_date_raw": row["application_raw"],
                "source_locator": row["locator"],
            },
        )
        record["identifiers"] = _strict_identifiers(row["identifier_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != {"pending": _EXPECTED_APPLICANT_RECORDS}:
        raise RuntimeError(f"Genova applicant status drift: {status_counts!r}")
    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "genova_applicants",
            "parser_version": PARSER_VERSION,
            "source_pages": _APPLICANT_PAGES,
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
            "reviewed_page7_split_rows": reviewed_page7,
            "reviewed_page9_reconstructions": reviewed_page9,
        },
    )


PARSERS = {
    "genova_listed": parse_genova_listed,
    "genova_applicants": parse_genova_applicants,
}
