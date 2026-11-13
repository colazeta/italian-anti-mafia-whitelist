from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
REFERENCE_DATE = "2026-09-24"
LISTED_PARSER_NAME = "reggio_calabria_listed"
APPLICANT_PARSER_NAME = "reggio_calabria_applicants"

_LISTED_PAGES = 65
_APPLICANT_PAGES = 79
_LISTED_PAGE_ROWS = [3,11,9,11,9,6,8,7,9,9,6,5,10,8,11,6,6,6,10,6,6,7,7,8,8,9,7,8,8,10,9,7,9,8,6,12,9,10,8,5,11,8,7,11,7,10,12,9,8,8,11,8,9,8,10,8,5,9,10,11,8,6,12,6,4]
_APPLICANT_PAGE_ROWS = [3,9,13,11,8,8,10,10,13,8,10,11,10,10,12,11,5,11,8,4,6,8,6,9,8,6,10,13,10,6,8,13,12,9,7,10,6,10,9,9,10,10,8,8,10,11,9,9,12,6,11,9,10,10,15,9,8,10,14,9,9,11,8,9,9,11,6,11,13,7,10,13,11,6,11,8,10,5,6]

_EXPECTED_LISTED_SOURCE_NUMBERS = set(range(1, 534))
_EXPECTED_LISTED_BLANK_NUMBERED_ROWS = {533}
_EXPECTED_LISTED_RECORDS = 532
_EXPECTED_LISTED_STATUSES = {
    "listed": 252,
    "renewal_update_in_progress": 250,
    "other_or_unknown": 30,
}
_EXPECTED_LISTED_IDENTIFIER_COVERAGE = 517
_EXPECTED_LISTED_BLANK_NAME_ROWS = {34}
_EXPECTED_LISTED_BLANK_OFFICE_ROWS = {8}
_EXPECTED_LISTED_BLANK_ACTIVITY_ROWS = {178, 265}
_EXPECTED_LISTED_BLANK_EXPIRY_ROWS = {139,157,187,270,288,316,336,356,427,461,471,509,530}
_EXPECTED_LISTED_UNPARSED_EXPIRY_ROWS = {473}
_EXPECTED_LISTED_OTHER_NOTE_ROWS = {
    49,88,90,125,135,139,153,157,162,187,205,217,227,245,264,
    270,310,316,336,339,346,355,356,374,427,461,471,485,509,530,
}

_EXPECTED_APPLICANT_NUMBERS = set(range(1, 733))
_EXPECTED_APPLICANT_RECORDS = 732
_EXPECTED_APPLICANT_STATUSES = {"pending": 730, "other_or_unknown": 2}
_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE = 697
_EXPECTED_APPLICANT_BLANK_OFFICE_ROWS = {451, 652}
_EXPECTED_APPLICANT_UNPARSED_DATE_ROWS = {168}
_REVIEWED_APPLICANT_TYPOS = Counter({"Istrutoria": 1, "Istruttorria": 1})
_REVIEWED_APPLICANT_UNKNOWN_OUTCOMES = Counter({"": 1, "L.M.": 1})

_MONTHS = {
    "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6,
    "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12,
}
_STRICT_IDENTIFIER = re.compile(r"^(?:\d{11}|[A-Za-z0-9]{16})$")
_DASH_MONTH = re.compile(r"^(\d{1,2})-([A-Za-zÀ-ÿ]{3})-(\d{2}|\d{4})$")
_DMY = re.compile(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$")
_DMY_PREFIX = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+\(.+\))$")


def _is_header(cells: list[str]) -> bool:
    folded = " | ".join(cells).casefold()
    return "ragione sociale" in folded and ("codice fiscale" in folded or "partita iva" in folded)


def _iso(day: int, month: int, year: int) -> str:
    if year < 100:
        year += 2000
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def _source_date(raw_value: str) -> str:
    """Normalise only source-explicit, unambiguous Reggio Calabria date typography."""
    raw = _clean(raw_value)
    if not raw:
        return ""
    compact = re.sub(r"\s*-\s*", "-", raw)
    match = _DASH_MONTH.fullmatch(compact)
    if match:
        day, month_name, year = match.groups()
        month = _MONTHS.get(month_name.casefold())
        return _iso(int(day), month, int(year)) if month else ""
    match = _DMY.fullmatch(raw)
    if match:
        day, month, year = map(int, match.groups())
        return _iso(day, month, year)
    match = _DMY_PREFIX.fullmatch(raw)
    if match:
        day, month, year = map(int, match.groups())
        return _iso(day, month, year)
    return ""


def _strict_identifiers(raw_value: str) -> list[str]:
    raw = _clean(raw_value).upper()
    return [raw] if _STRICT_IDENTIFIER.fullmatch(raw) else []


def _activities(raw_value: str) -> list[str]:
    raw = _clean(raw_value)
    return [raw] if raw else []


def _listed_status(note: str) -> str:
    folded = _clean(note).casefold()
    if not folded:
        return "listed"
    if (
        ("istruttoria" in folded and any(token in folded for token in ("rinnovo", "aggiornamento", "permanenza")))
        or "aggiornamento in corso" in folded
    ):
        return "renewal_update_in_progress"
    return "other_or_unknown"


def _applicant_status(outcome: str) -> str:
    raw = _clean(outcome)
    folded = raw.casefold()
    if "istruttoria" in folded or folded in {"istrutoria", "istruttorria"}:
        return "pending"
    return "other_or_unknown"


def _validate_cfg(cfg: dict[str, Any], source_key: str, population_scope: str) -> None:
    if cfg.get("source_key") != source_key:
        raise RuntimeError(f"Reggio Calabria parser/source mismatch: {cfg.get('source_key')!r}")
    if cfg.get("authority_key") != "reggio-calabria":
        raise RuntimeError("Reggio Calabria parser bound to another authority")
    if cfg.get("population_scope") != population_scope:
        raise RuntimeError("Reggio Calabria population-scope mismatch")
    if cfg.get("reference_date") != REFERENCE_DATE:
        raise RuntimeError(f"Reggio Calabria reference-date drift: {cfg.get('reference_date')!r}")


def _extract_rows(path: Path, *, pages: int, expected_page_rows: list[int], header_pages: set[int]) -> list[tuple[int, int, list[str]]]:
    extracted: list[tuple[int, int, list[str]]] = []
    observed_page_rows: list[int] = []
    observed_headers: set[int] = set()
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != pages:
            raise RuntimeError(f"Reggio Calabria page-count drift: {len(pdf.pages)} != {pages}")
        for page_number, page in enumerate(pdf.pages, 1):
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(f"Reggio Calabria table-count drift page={page_number}: {len(tables)}")
            table = tables[0].extract()
            page_rows = 0
            for table_row, raw_row in enumerate(table, 1):
                cells = [_clean(value) for value in raw_row]
                if not any(cells):
                    continue
                if _is_header(cells):
                    observed_headers.add(page_number)
                    continue
                extracted.append((page_number, table_row, cells))
                page_rows += 1
            observed_page_rows.append(page_rows)
    if observed_headers != header_pages:
        raise RuntimeError(f"Reggio Calabria header-page drift: {sorted(observed_headers)!r}")
    if observed_page_rows != expected_page_rows:
        raise RuntimeError(
            f"Reggio Calabria page-row boundary drift: expected {expected_page_rows!r}, got {observed_page_rows!r}"
        )
    return extracted


def parse_reggio_calabria_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, "reggio-calabria-listed", "listed")
    rows = _extract_rows(
        path, pages=_LISTED_PAGES, expected_page_rows=_LISTED_PAGE_ROWS, header_pages={1}
    )
    if any(len(cells) != 9 for _, _, cells in rows):
        raise RuntimeError("Reggio Calabria listed column-count drift")

    by_number: dict[int, tuple[int, int, list[str]]] = {}
    for page_number, table_row, cells in rows:
        if not re.fullmatch(r"\d+", cells[0]):
            raise RuntimeError(f"Reggio Calabria listed non-numeric source row: page={page_number} row={table_row}")
        number = int(cells[0])
        if number in by_number:
            raise RuntimeError(f"Reggio Calabria duplicate listed source number: {number}")
        by_number[number] = (page_number, table_row, cells)
    if set(by_number) != _EXPECTED_LISTED_SOURCE_NUMBERS:
        raise RuntimeError("Reggio Calabria listed source-number boundary drift")

    blank_numbered = {
        number for number, (_page, _row, cells) in by_number.items() if not any(cells[1:])
    }
    if blank_numbered != _EXPECTED_LISTED_BLANK_NUMBERED_ROWS:
        raise RuntimeError(f"Reggio Calabria blank numbered-row drift: {sorted(blank_numbered)!r}")

    public_rows = {number: item for number, item in by_number.items() if number not in blank_numbered}
    blank_names = {n for n, (_p, _r, c) in public_rows.items() if not c[1]}
    blank_offices = {n for n, (_p, _r, c) in public_rows.items() if not c[2]}
    blank_activities = {n for n, (_p, _r, c) in public_rows.items() if not c[7]}
    if blank_names != _EXPECTED_LISTED_BLANK_NAME_ROWS:
        raise RuntimeError(f"Reggio Calabria listed blank-name drift: {sorted(blank_names)!r}")
    if blank_offices != _EXPECTED_LISTED_BLANK_OFFICE_ROWS:
        raise RuntimeError(f"Reggio Calabria listed blank-office drift: {sorted(blank_offices)!r}")
    if blank_activities != _EXPECTED_LISTED_BLANK_ACTIVITY_ROWS:
        raise RuntimeError(f"Reggio Calabria listed blank-activity drift: {sorted(blank_activities)!r}")
    if any(not c[4] or not c[5] for _n, (_p, _r, c) in public_rows.items()):
        raise RuntimeError("Reggio Calabria listed lost identifier or registration source field")

    blank_expiry = {n for n, (_p, _r, c) in public_rows.items() if not c[6]}
    if blank_expiry != _EXPECTED_LISTED_BLANK_EXPIRY_ROWS:
        raise RuntimeError(f"Reggio Calabria listed blank-expiry drift: {sorted(blank_expiry)!r}")

    other_note_rows = {n for n, (_p, _r, c) in public_rows.items() if _listed_status(c[8]) == "other_or_unknown"}
    if other_note_rows != _EXPECTED_LISTED_OTHER_NOTE_ROWS:
        raise RuntimeError(f"Reggio Calabria listed nonstandard-note drift: {sorted(other_note_rows)!r}")

    records: list[dict[str, Any]] = []
    unparsed_expiry: set[int] = set()
    for number in sorted(public_rows):
        page_number, table_row, cells = public_rows[number]
        _, name, office, secondary, identifier_raw, listing_raw, expiry_raw, activities_raw, note = cells
        listing_date = _source_date(listing_raw)
        if not listing_date:
            raise RuntimeError(f"Reggio Calabria listed unreviewed registration date at source row {number}")
        expiry_date = _source_date(expiry_raw)
        if expiry_raw and not expiry_date:
            unparsed_expiry.add(number)
        record = _record(
            cfg,
            number,
            name=name,
            office=office,
            secondary=secondary,
            identifier_raw=identifier_raw,
            activities=_activities(activities_raw),
            status=_listed_status(note),
            outcome_raw=note,
            listing_date=listing_date,
            expiry_date=expiry_date,
            primary_date_label="Data iscrizione",
            source_fields={
                "requested_activities_source": activities_raw,
                "listing_date_raw_variants": [listing_raw],
                "expiry_date_raw_variants": [expiry_raw] if expiry_raw else [],
                "notes": [note] if note else [],
                "physical_locator": f"page {page_number} row {table_row}",
            },
        )
        record["identifiers"] = _strict_identifiers(identifier_raw)
        records.append(record)

    if unparsed_expiry != _EXPECTED_LISTED_UNPARSED_EXPIRY_ROWS:
        raise RuntimeError(f"Reggio Calabria listed malformed-expiry drift: {sorted(unparsed_expiry)!r}")
    statuses = Counter(record["source_status"] for record in records)
    if dict(statuses) != _EXPECTED_LISTED_STATUSES:
        raise RuntimeError(f"Reggio Calabria listed status drift: {dict(statuses)!r}")
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != _EXPECTED_LISTED_IDENTIFIER_COVERAGE:
        raise RuntimeError(f"Reggio Calabria listed identifier-coverage drift: {identifier_coverage}")
    if len(records) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(f"Reggio Calabria listed record denominator drift: {len(records)}")

    return ParsedBatch(records, {
        "parser": LISTED_PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "source_pages": _LISTED_PAGES,
        "numbered_source_rows": len(by_number),
        "blank_numbered_source_rows": sorted(blank_numbered),
        "public_records": len(records),
        "status_counts": dict(statuses),
        "identifier_coverage": identifier_coverage,
        "blank_name_rows": sorted(blank_names),
        "blank_office_rows": sorted(blank_offices),
        "blank_activity_rows": sorted(blank_activities),
        "blank_expiry_rows": sorted(blank_expiry),
        "unparsed_expiry_rows": sorted(unparsed_expiry),
    })


def parse_reggio_calabria_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, "reggio-calabria-applicants", "applicant")
    rows = _extract_rows(
        path,
        pages=_APPLICANT_PAGES,
        expected_page_rows=_APPLICANT_PAGE_ROWS,
        header_pages=set(range(1, _APPLICANT_PAGES + 1)),
    )
    if any(len(cells) != 8 for _, _, cells in rows):
        raise RuntimeError("Reggio Calabria applicant column-count drift")

    by_number: dict[int, tuple[int, int, list[str]]] = {}
    for page_number, table_row, cells in rows:
        if not re.fullmatch(r"\d+", cells[0]):
            raise RuntimeError(f"Reggio Calabria applicant non-numeric source row: page={page_number} row={table_row}")
        number = int(cells[0])
        if number in by_number:
            raise RuntimeError(f"Reggio Calabria duplicate applicant source number: {number}")
        by_number[number] = (page_number, table_row, cells)
    if set(by_number) != _EXPECTED_APPLICANT_NUMBERS:
        raise RuntimeError("Reggio Calabria applicant source-number boundary drift")
    if any(not c[1] or not c[4] or not c[5] or not c[6] for _n, (_p, _r, c) in by_number.items()):
        raise RuntimeError("Reggio Calabria applicant lost required source fields")
    blank_offices = {n for n, (_p, _r, c) in by_number.items() if not c[2]}
    if blank_offices != _EXPECTED_APPLICANT_BLANK_OFFICE_ROWS:
        raise RuntimeError(f"Reggio Calabria applicant blank-office drift: {sorted(blank_offices)!r}")

    typo_outcomes = Counter()
    unknown_outcomes = Counter()
    records: list[dict[str, Any]] = []
    unparsed_dates: set[int] = set()
    for number in sorted(by_number):
        page_number, table_row, cells = by_number[number]
        _, name, office, secondary, identifier_raw, activities_raw, application_raw, outcome = cells
        status = _applicant_status(outcome)
        if outcome in _REVIEWED_APPLICANT_TYPOS:
            typo_outcomes[outcome] += 1
        if status == "other_or_unknown":
            unknown_outcomes[outcome] += 1
        application_date = _source_date(application_raw)
        if not application_date:
            unparsed_dates.add(number)
        record = _record(
            cfg,
            number,
            name=name,
            office=office,
            secondary=secondary,
            identifier_raw=identifier_raw,
            activities=_activities(activities_raw),
            status=status,
            outcome_raw=outcome,
            application_date=application_date,
            primary_date_label="Data presentazione istanza" if application_date else "",
            source_fields={
                "requested_activities_source": activities_raw,
                "application_date_raw": application_raw,
                "physical_locator": f"page {page_number} row {table_row}",
            },
        )
        record["identifiers"] = _strict_identifiers(identifier_raw)
        records.append(record)

    if typo_outcomes != _REVIEWED_APPLICANT_TYPOS:
        raise RuntimeError(f"Reggio Calabria applicant reviewed-typo drift: {dict(typo_outcomes)!r}")
    if unknown_outcomes != _REVIEWED_APPLICANT_UNKNOWN_OUTCOMES:
        raise RuntimeError(f"Reggio Calabria applicant unknown-outcome drift: {dict(unknown_outcomes)!r}")
    if unparsed_dates != _EXPECTED_APPLICANT_UNPARSED_DATE_ROWS:
        raise RuntimeError(f"Reggio Calabria applicant malformed-date drift: {sorted(unparsed_dates)!r}")
    statuses = Counter(record["source_status"] for record in records)
    if dict(statuses) != _EXPECTED_APPLICANT_STATUSES:
        raise RuntimeError(f"Reggio Calabria applicant status drift: {dict(statuses)!r}")
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE:
        raise RuntimeError(f"Reggio Calabria applicant identifier-coverage drift: {identifier_coverage}")
    if len(records) != _EXPECTED_APPLICANT_RECORDS:
        raise RuntimeError(f"Reggio Calabria applicant denominator drift: {len(records)}")

    return ParsedBatch(records, {
        "parser": APPLICANT_PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "source_pages": _APPLICANT_PAGES,
        "public_records": len(records),
        "status_counts": dict(statuses),
        "identifier_coverage": identifier_coverage,
        "blank_office_rows": sorted(blank_offices),
        "unparsed_application_date_rows": sorted(unparsed_dates),
        "reviewed_outcome_typographies": dict(typo_outcomes),
        "unknown_outcomes": dict(unknown_outcomes),
    })


PARSERS = {
    LISTED_PARSER_NAME: parse_reggio_calabria_listed,
    APPLICANT_PARSER_NAME: parse_reggio_calabria_applicants,
}
