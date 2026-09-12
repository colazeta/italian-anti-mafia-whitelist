from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-09-10"
_LISTED_PAGES = 114
_APPLICANT_PAGES = 20
_EXPECTED_LISTED_RECORDS = 652
_EXPECTED_LISTED_STATUS_COUNTS = {"listed": 528, "renewal_update_in_progress": 124}
_EXPECTED_APPLICANT_RECORDS = 110
_EXPECTED_APPLICANT_SPLIT_ROWS = 6

_SECTION = re.compile(r"SEZ\.\s*(X|IX|VIII|VII|VI|V|IV|III|II|I)\b", re.I)
_STRICT_IDENTIFIER = re.compile(r"^(?:\d{11}|[A-Z0-9]{16})$", re.I)
_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")

# The 10 September 2026 PDFs contain three extraction artefacts that are
# deterministic on the byte-pinned source. These are reviewed source-layout
# exceptions, not inferred repairs of the underlying official data.
_REVIEWED_LISTED_PAGE47 = {
    "prefix": ["FISIA ITALIMPIANTI SPA", "GENOVA VIA DE MARINI, 1", "", "02340830997", "Sez. X"],
    "listing_raw": "06/09/2024",
    "expiry_raw": "05/09/2026",
    "outcome_raw": "IN FASE DI RINNOVO",
}
_REVIEWED_APPLICANT_PAGE7_IDS = {
    "CRESTA & DELFINO SRL": "01345600991",
    "CUNEO LUIGI": "01067080992",
    "CURZI LUIGI - AUTOTRASPORTI C/TERZI": "03185270109",
    "DAMA SRL": "02830520991",
    "DASSORI SRL": "02665830994",
    "DE BREEZE SRL": "03047520998",
}
_REVIEWED_APPLICANT_PAGE9 = [
    "EDILQUADRIFOGLIO SRL",
    "GENOVA VIA CESAREA, 11/6",
    "",
    "01660680990",
]


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", _clean(value)).casefold()


def _strict_identifiers(value: str) -> list[str]:
    identifiers: list[str] = []
    for token in re.split(r"\s+", _clean(value).upper()):
        if _STRICT_IDENTIFIER.fullmatch(token) and token not in identifiers:
            identifiers.append(token)
    return identifiers


def _parse_date(value: str, *, allow_blank: bool = True) -> str:
    raw = _clean(value)
    if not raw and allow_blank:
        return ""
    compact = re.sub(r"\s+", "", raw)
    match = _DATE.fullmatch(compact)
    if not match:
        raise RuntimeError(f"Genova unreviewed date typography: {raw!r}")
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError as exc:
        raise RuntimeError(f"Genova invalid calendar date: {raw!r}") from exc


def _sections(value: str) -> list[str]:
    matches = _SECTION.findall(_clean(value))
    roman_to_int = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
    sections: list[str] = []
    for match in matches:
        label = f"Sezione {roman_to_int[match.upper()]}"
        if label not in sections:
            sections.append(label)
    if not sections:
        raise RuntimeError(f"Genova row without a recognised White List section: {value!r}")
    return sections


def _listed_status(raw: str) -> str:
    compact = _compact(raw)
    if not compact:
        return "listed"
    if compact == "infasedirinnovo":
        return "renewal_update_in_progress"
    raise RuntimeError(f"Genova unreviewed listed status: {raw!r}")


def _applicant_outcome(raw: str) -> str:
    compact = _compact(raw)
    if compact in {"", "inistruttoria"}:
        return _clean(raw)
    raise RuntimeError(f"Genova unreviewed applicant outcome: {raw!r}")


def _validate_cfg(cfg: dict[str, Any], expected_source_key: str) -> None:
    if cfg.get("source_key") != expected_source_key:
        raise RuntimeError(f"Genova parser/source mismatch: {cfg.get('source_key')!r} != {expected_source_key!r}")
    if cfg.get("authority_key") != "genova":
        raise RuntimeError("Genova parser bound to a non-Genova authority")
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"Genova reference date drift: {cfg.get('reference_date')!r}")


def _is_header(cells: list[str]) -> bool:
    folded = " | ".join(cells).casefold()
    return any(token in folded for token in ("ragione sociale", "codice fiscale", "partita iva", "data iscrizione", "data di presentazione"))


def _normalise_listed_row(cells: list[str], *, page_number: int, table_number: int, row_number: int) -> list[str] | None:
    if _is_header(cells):
        return None
    if cells and cells[0].casefold().startswith("legenda sez."):
        return None
    if len(cells) == 9:
        if cells[0]:
            raise RuntimeError(f"Genova unreviewed 9-column listed row p{page_number}:t{table_number}:r{row_number}: {cells!r}")
        cells = cells[1:]
    if len(cells) == 5:
        if page_number != 47 or table_number != 1 or row_number != 1 or cells != _REVIEWED_LISTED_PAGE47["prefix"]:
            raise RuntimeError(f"Genova unreviewed 5-column listed row p{page_number}:t{table_number}:r{row_number}: {cells!r}")
        return cells + [
            _REVIEWED_LISTED_PAGE47["listing_raw"],
            _REVIEWED_LISTED_PAGE47["expiry_raw"],
            _REVIEWED_LISTED_PAGE47["outcome_raw"],
        ]
    if len(cells) != 8:
        raise RuntimeError(f"Genova unreviewed listed width p{page_number}:t{table_number}:r{row_number}: {len(cells)}")
    return cells


def parse_genova_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, "genova-listed")
    rows: list[dict[str, Any]] = []
    repaired_page47 = 0
    shifted_leading_blank = 0

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGES:
            raise RuntimeError(f"Genova listed page-count drift: {len(pdf.pages)} != {_LISTED_PAGES}")
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = _clean(page.extract_text() or "")
            for table_number, table in enumerate(page.extract_tables() or [], start=1):
                for row_number, row in enumerate(table or [], start=1):
                    original = [_clean(cell) for cell in row]
                    if not any(original):
                        continue
                    was_nine = len(original) == 9
                    cells = _normalise_listed_row(original, page_number=page_number, table_number=table_number, row_number=row_number)
                    if cells is None:
                        continue
                    if was_nine:
                        shifted_leading_blank += 1
                    if page_number == 47 and table_number == 1 and row_number == 1:
                        required = (
                            _REVIEWED_LISTED_PAGE47["prefix"][0],
                            _REVIEWED_LISTED_PAGE47["listing_raw"],
                            _REVIEWED_LISTED_PAGE47["expiry_raw"],
                            _REVIEWED_LISTED_PAGE47["outcome_raw"],
                        )
                        if not all(token in page_text for token in required):
                            raise RuntimeError("Genova reviewed page-47 reconstruction no longer supported by page text")
                        repaired_page47 += 1
                    if not cells[0]:
                        raise RuntimeError(f"Genova listed row without company name p{page_number}:t{table_number}:r{row_number}")
                    sections = _sections(cells[4])
                    listing_date = _parse_date(cells[5])
                    expiry_date = _parse_date(cells[6])
                    status = _listed_status(cells[7])
                    rows.append(
                        {
                            "name": cells[0],
                            "office": cells[1],
                            "secondary": cells[2],
                            "identifier_raw": cells[3],
                            "sections": sections,
                            "listing_raw": cells[5],
                            "listing_date": listing_date,
                            "expiry_raw": cells[6],
                            "expiry_date": expiry_date,
                            "outcome_raw": cells[7],
                            "status": status,
                            "locator": f"p{page_number}:t{table_number}:r{row_number}",
                        }
                    )

    if repaired_page47 != 1:
        raise RuntimeError(f"Genova page-47 reviewed reconstruction drift: {repaired_page47} != 1")
    if shifted_leading_blank != 25:
        raise RuntimeError(f"Genova leading-blank structural drift: {shifted_leading_blank} != 25")
    if len(rows) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(f"Genova listed record drift: {len(rows)} != {_EXPECTED_LISTED_RECORDS}")

    records: list[dict[str, Any]] = []
    for row in rows:
        record = _record(
            cfg,
            len(records) + 1,
            name=row["name"],
            office=row["office"],
            identifier_raw=row["identifier_raw"],
            activities=row["sections"],
            status=row["status"],
            outcome_raw=row["outcome_raw"],
            listing_date=row["listing_date"],
            expiry_date=row["expiry_date"],
            primary_date_label="Data iscrizione",
            source_fields={
                "sections": row["sections"],
                "secondary_office_raw": row["secondary"],
                "listing_date_raw": row["listing_raw"],
                "expiry_date_raw": row["expiry_raw"],
                "in_aggiornamento": row["outcome_raw"] if row["status"] == "renewal_update_in_progress" else "",
                "source_locator": row["locator"],
            },
        )
        record["identifiers"] = _strict_identifiers(row["identifier_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_LISTED_STATUS_COUNTS:
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
            "reviewed_page47_reconstructions": repaired_page47,
            "shifted_leading_blank_rows": shifted_leading_blank,
        },
    )


def _applicant_page7_rows(page: Any) -> list[list[str]]:
    tables = page.extract_tables() or []
    if len(tables) != 2:
        raise RuntimeError(f"Genova applicant page-7 table-count drift: {len(tables)} != 2")
    left = [[_clean(cell) for cell in row] for row in (tables[0] or []) if any(_clean(cell) for cell in row)]
    right = [[_clean(cell) for cell in row] for row in (tables[1] or []) if any(_clean(cell) for cell in row)]
    if len(left) != _EXPECTED_APPLICANT_SPLIT_ROWS or len(right) != _EXPECTED_APPLICANT_SPLIT_ROWS:
        raise RuntimeError(f"Genova applicant page-7 split-row drift: {len(left)}, {len(right)}")
    rows: list[list[str]] = []
    for left_row, right_row in zip(left, right):
        if len(left_row) != 3 or len(right_row) != 3:
            raise RuntimeError(f"Genova applicant page-7 split-width drift: {left_row!r}, {right_row!r}")
        name = left_row[0]
        if name not in _REVIEWED_APPLICANT_PAGE7_IDS:
            raise RuntimeError(f"Genova applicant page-7 unreviewed identity: {name!r}")
        rows.append(left_row + [_REVIEWED_APPLICANT_PAGE7_IDS[name]] + right_row)
    if set(_REVIEWED_APPLICANT_PAGE7_IDS) != {row[0] for row in left}:
        raise RuntimeError("Genova applicant page-7 reviewed identity set drift")
    return rows


def parse_genova_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, "genova-applicants")
    rows: list[dict[str, Any]] = []
    reviewed_page7 = 0
    reviewed_page9 = 0

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGES:
            raise RuntimeError(f"Genova applicant page-count drift: {len(pdf.pages)} != {_APPLICANT_PAGES}")
        for page_number, page in enumerate(pdf.pages, start=1):
            if page_number == 7:
                raw_rows = [(0, index, cells) for index, cells in enumerate(_applicant_page7_rows(page), start=1)]
                reviewed_page7 = len(raw_rows)
            else:
                raw_rows = []
                for table_number, table in enumerate(page.extract_tables() or [], start=1):
                    for row_number, row in enumerate(table or [], start=1):
                        cells = [_clean(cell) for cell in row]
                        if not any(cells) or _is_header(cells):
                            continue
                        if len(cells) != 7:
                            raise RuntimeError(f"Genova unreviewed applicant width p{page_number}:t{table_number}:r{row_number}: {len(cells)}")
                        raw_rows.append((table_number, row_number, cells))

            for table_number, row_number, cells in raw_rows:
                if page_number == 9 and table_number == 1 and row_number == 1:
                    if cells[:4] != ["", "", "", ""]:
                        raise RuntimeError(f"Genova applicant page-9 reviewed row drift: {cells!r}")
                    page_text = _clean(page.extract_text() or "")
                    if not all(token in page_text for token in (_REVIEWED_APPLICANT_PAGE9[0], _REVIEWED_APPLICANT_PAGE9[1], _REVIEWED_APPLICANT_PAGE9[3])):
                        raise RuntimeError("Genova applicant page-9 reconstruction no longer supported by page text")
                    cells = _REVIEWED_APPLICANT_PAGE9 + cells[4:]
                    reviewed_page9 += 1

                if not cells[0]:
                    raise RuntimeError(f"Genova applicant row without company name p{page_number}:t{table_number}:r{row_number}")
                sections = _sections(cells[4])
                application_date = _parse_date(cells[5])
                outcome_raw = _applicant_outcome(cells[6])
                rows.append(
                    {
                        "name": cells[0],
                        "office": cells[1],
                        "secondary": cells[2],
                        "identifier_raw": cells[3],
                        "sections": sections,
                        "application_raw": cells[5],
                        "application_date": application_date,
                        "outcome_raw": outcome_raw,
                        "locator": f"p{page_number}:t{table_number}:r{row_number}",
                    }
                )

    if reviewed_page7 != _EXPECTED_APPLICANT_SPLIT_ROWS:
        raise RuntimeError(f"Genova applicant reviewed page-7 rows drift: {reviewed_page7}")
    if reviewed_page9 != 1:
        raise RuntimeError(f"Genova applicant reviewed page-9 rows drift: {reviewed_page9}")
    if len(rows) != _EXPECTED_APPLICANT_RECORDS:
        raise RuntimeError(f"Genova applicant record drift: {len(rows)} != {_EXPECTED_APPLICANT_RECORDS}")

    records: list[dict[str, Any]] = []
    for row in rows:
        record = _record(
            cfg,
            len(records) + 1,
            name=row["name"],
            office=row["office"],
            identifier_raw=row["identifier_raw"],
            activities=row["sections"],
            status="pending",
            outcome_raw=row["outcome_raw"],
            primary_date=row["application_date"],
            primary_date_label="Data di presentazione dell'istanza",
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
