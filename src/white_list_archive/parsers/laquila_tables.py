from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-09-11"
_LISTED_PAGES = 24
_APPLICANT_PAGES = 46
_EXPECTED_LISTED_PAGE_COUNTS = (
    2, 19, 18, 19, 15, 17, 18, 18, 16, 18, 16, 17,
    20, 20, 18, 22, 20, 20, 21, 22, 20, 17, 21, 5,
)
_EXPECTED_APPLICANT_PAGE_COUNTS = (
    4, 5, 11, 10, 9, 6, 6, 6, 7, 3, 6, 3, 7, 12, 3, 5, 3, 2, 4, 5, 5, 3, 3,
    8, 9, 11, 11, 6, 7, 9, 7, 5, 3, 7, 6, 4, 4, 3, 8, 3, 8, 9, 4, 5, 7, 4,
)
_EXPECTED_LISTED_RECORDS = 419
_EXPECTED_APPLICANTS = 276
_EXPECTED_LISTED_STATUS_COUNTS = Counter({"renewal_update_in_progress": 210, "listed": 209})
_EXPECTED_APPLICANT_OUTCOMES = Counter({
    "IN ISTRUTTORIA": 273,
    "IN STRUTTORIA": 1,
    "N ISTRUTTORIA": 1,
    "IN ISTRTUTTORIA": 1,
})
_EXPECTED_LISTED_MALFORMED_IDENTIFIERS = {"1373501007", "0205612666"}
_EXPECTED_APPLICANT_MALFORMED_IDENTIFIERS = {
    "CNMMLC85T69A 345P",
    "0010745660",
    "CNGVCN66H20L 379D",
}
_EXPECTED_LISTED_DUPLICATE_IDENTIFIERS = {
    "01550930661", "01965080664", "02018220661", "02156880664",
    "01998660664", "02080550664", "02109140661", "01787220662",
}
_EXPECTED_APPLICANT_DUPLICATE_IDENTIFIERS = {"01698860663"}
_REVIEWED_BAD_EXPIRY = "28/06/207"
_REVIEWED_LISTED_NOTE = "Misura di prevenzione collaborativa con nomina di esperto ex art.94 bis D.Lgs.159/11"
_DATE_LIKE = re.compile(r"^\d{1,2}/\d{1,2}/\d{3,4}$")
_STRICT_IDENTIFIER = re.compile(r"^\d{11}$")


def _parse_source_date(raw: str, *, source_key: str, field: str, allow_reviewed_bad: bool = False) -> str:
    value = _clean(raw)
    if allow_reviewed_bad and value == _REVIEWED_BAD_EXPIRY:
        return ""
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if match is None:
        raise RuntimeError(f"{source_key}: unreviewed {field} date typography: {raw!r}")
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError as exc:
        raise RuntimeError(f"{source_key}: invalid {field} calendar date: {raw!r}") from exc


def _table_rows(path: Path, source_key: str, *, pages: int, listed: bool) -> tuple[list[dict[str, Any]], tuple[int, ...]]:
    output: list[dict[str, Any]] = []
    page_counts: list[int] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != pages:
            raise RuntimeError(f"{source_key}: page-count drift; expected {pages}, got {len(pdf.pages)}")
        if not 840.0 <= float(pdf.pages[0].width) <= 843.0:
            raise RuntimeError(f"{source_key}: page-width drift: {pdf.pages[0].width}")
        for page_number, page in enumerate(pdf.pages, 1):
            if not 840.0 <= float(page.width) <= 843.0:
                raise RuntimeError(f"{source_key}: page-width drift at page {page_number}: {page.width}")
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(f"{source_key}: expected one source table on page {page_number}, got {len(tables)}")
            page_rows: list[dict[str, Any]] = []
            for row_number, raw in enumerate(tables[0].extract() or [], 1):
                values = [_clean(cell) for cell in raw]
                expected_columns = 8 if listed else 7
                if len(values) != expected_columns:
                    raise RuntimeError(
                        f"{source_key}: column-count drift at page {page_number} row {row_number}: {len(values)}"
                    )
                if values[0].casefold() == "ragione sociale":
                    continue
                date_index = 5
                if not values[0] or not values[1] or not values[3] or not _DATE_LIKE.fullmatch(values[date_index]):
                    continue
                page_rows.append({
                    "page": page_number,
                    "row": row_number,
                    "name": values[0],
                    "office": values[1],
                    "secondary": values[2],
                    "identifier_raw": values[3],
                    "activity_raw": values[4],
                    "primary_date_raw": values[5],
                    "expiry_raw": values[6] if listed else "",
                    "note_raw": values[7] if listed else values[6],
                })
            page_counts.append(len(page_rows))
            output.extend(page_rows)
    return output, tuple(page_counts)


def _strict_identifier_coverage(rows: list[dict[str, Any]]) -> tuple[int, set[str], set[str]]:
    raw = [item["identifier_raw"] for item in rows]
    strict = [value for value in raw if _STRICT_IDENTIFIER.fullmatch(value)]
    malformed = {value for value in raw if not _STRICT_IDENTIFIER.fullmatch(value)}
    duplicates = {value for value, count in Counter(strict).items() if count > 1}
    return len(strict), malformed, duplicates


def parse_laquila_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"{cfg['source_key']}: unexpected reference date {cfg.get('reference_date')!r}")
    rows, page_counts = _table_rows(path, cfg["source_key"], pages=_LISTED_PAGES, listed=True)
    if page_counts != _EXPECTED_LISTED_PAGE_COUNTS:
        raise RuntimeError(f"{cfg['source_key']}: listed page denominators drift: {page_counts!r}")
    if len(rows) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(f"{cfg['source_key']}: listed denominator drift; expected {_EXPECTED_LISTED_RECORDS}, got {len(rows)}")
    if any(item["secondary"] for item in rows):
        raise RuntimeError(f"{cfg['source_key']}: unexpected listed secondary-office values")

    coverage, malformed, duplicates = _strict_identifier_coverage(rows)
    if coverage != 417 or malformed != _EXPECTED_LISTED_MALFORMED_IDENTIFIERS:
        raise RuntimeError(
            f"{cfg['source_key']}: listed identifier boundary drift: coverage={coverage}, malformed={sorted(malformed)!r}"
        )
    if duplicates != _EXPECTED_LISTED_DUPLICATE_IDENTIFIERS:
        raise RuntimeError(f"{cfg['source_key']}: listed duplicate-identifier boundary drift: {sorted(duplicates)!r}")

    records: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    reviewed_bad_expiry = 0
    collaborative_measure_notes = 0
    for ordinal, item in enumerate(rows, 1):
        listing_date = _parse_source_date(
            item["primary_date_raw"], source_key=cfg["source_key"], field="listing"
        )
        expiry_date = _parse_source_date(
            item["expiry_raw"], source_key=cfg["source_key"], field="expiry", allow_reviewed_bad=True
        )
        if item["expiry_raw"] == _REVIEWED_BAD_EXPIRY:
            reviewed_bad_expiry += 1
        note = item["note_raw"]
        if note.casefold() == "aggiornamento in corso":
            status = "renewal_update_in_progress"
        elif not note:
            status = "listed"
        elif note == _REVIEWED_LISTED_NOTE:
            status = "listed"
            collaborative_measure_notes += 1
        else:
            raise RuntimeError(f"{cfg['source_key']}: unreviewed listed note: {note!r}")
        status_counts[status] += 1
        activities = [item["activity_raw"]] if item["activity_raw"] else []
        record = _record(
            cfg,
            ordinal,
            name=item["name"],
            office=item["office"],
            secondary=item["secondary"],
            identifier_raw=item["identifier_raw"],
            activities=activities,
            status=status,
            outcome_raw=note,
            listing_date=listing_date,
            expiry_date=expiry_date,
            primary_date_label="Data iscrizione",
            source_fields={
                "sections": activities,
                "listing_date_raw_variants": [item["primary_date_raw"]],
                "expiry_date_raw_variants": [item["expiry_raw"]],
                "in_aggiornamento": note if status == "renewal_update_in_progress" else "",
                "notes": [note] if note and status == "listed" else [],
            },
        )
        records.append(record)

    if status_counts != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(f"{cfg['source_key']}: listed status drift: {dict(status_counts)!r}")
    if reviewed_bad_expiry != 1 or collaborative_measure_notes != 3:
        raise RuntimeError(
            f"{cfg['source_key']}: reviewed listed-exception boundary drift: "
            f"bad_expiry={reviewed_bad_expiry}, collaborative_notes={collaborative_measure_notes}"
        )
    return ParsedBatch(records, {
        "parser": "laquila_listed",
        "public_records": len(records),
        "page_counts": list(page_counts),
        "status_counts": dict(status_counts),
        "identifier_coverage": coverage,
        "raw_only_identifier_records": len(malformed),
        "duplicate_strict_identifier_values": len(duplicates),
        "reviewed_malformed_expiry_dates": reviewed_bad_expiry,
        "collaborative_measure_notes": collaborative_measure_notes,
        "dropped_date_rows": 0,
    })


def parse_laquila_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"{cfg['source_key']}: unexpected reference date {cfg.get('reference_date')!r}")
    rows, page_counts = _table_rows(path, cfg["source_key"], pages=_APPLICANT_PAGES, listed=False)
    if page_counts != _EXPECTED_APPLICANT_PAGE_COUNTS:
        raise RuntimeError(f"{cfg['source_key']}: applicant page denominators drift: {page_counts!r}")
    if len(rows) != _EXPECTED_APPLICANTS:
        raise RuntimeError(f"{cfg['source_key']}: applicant denominator drift; expected {_EXPECTED_APPLICANTS}, got {len(rows)}")
    if any(item["secondary"] for item in rows):
        raise RuntimeError(f"{cfg['source_key']}: unexpected applicant secondary-office values")

    coverage, malformed, duplicates = _strict_identifier_coverage(rows)
    if coverage != 273 or malformed != _EXPECTED_APPLICANT_MALFORMED_IDENTIFIERS:
        raise RuntimeError(
            f"{cfg['source_key']}: applicant identifier boundary drift: coverage={coverage}, malformed={sorted(malformed)!r}"
        )
    if duplicates != _EXPECTED_APPLICANT_DUPLICATE_IDENTIFIERS:
        raise RuntimeError(f"{cfg['source_key']}: applicant duplicate-identifier boundary drift: {sorted(duplicates)!r}")

    outcomes = Counter(item["note_raw"] for item in rows)
    if outcomes != _EXPECTED_APPLICANT_OUTCOMES:
        raise RuntimeError(f"{cfg['source_key']}: applicant outcome-text drift: {dict(outcomes)!r}")

    records: list[dict[str, Any]] = []
    for ordinal, item in enumerate(rows, 1):
        application_date = _parse_source_date(
            item["primary_date_raw"], source_key=cfg["source_key"], field="application"
        )
        activity = item["activity_raw"]
        record = _record(
            cfg,
            ordinal,
            name=item["name"],
            office=item["office"],
            secondary=item["secondary"],
            identifier_raw=item["identifier_raw"],
            activities=[activity] if activity else [],
            status="pending",
            outcome_raw=item["note_raw"],
            application_date=application_date,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "requested_activities_source": activity,
                "application_date_raw_variants": [item["primary_date_raw"]],
                "notes": [item["note_raw"]],
            },
        )
        records.append(record)

    return ParsedBatch(records, {
        "parser": "laquila_applicants",
        "public_records": len(records),
        "page_counts": list(page_counts),
        "status_counts": {"pending": len(records)},
        "outcome_counts": dict(outcomes),
        "identifier_coverage": coverage,
        "raw_only_identifier_records": len(malformed),
        "duplicate_strict_identifier_values": len(duplicates),
        "dropped_date_rows": 0,
    })


PARSERS = {
    "laquila_listed": parse_laquila_listed,
    "laquila_applicants": parse_laquila_applicants,
}
