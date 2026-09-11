from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-09-09"
_LISTED_PAGES = 55
_APPLICANT_PAGES = 67
_EXPECTED_LISTED_RECORDS = 518
_EXPECTED_LISTED_STATUS_COUNTS = {
    "listed": 281,
    "renewal_update_in_progress": 232,
    "other_or_unknown": 5,
}
_EXPECTED_APPLICANT_RECORDS = 288
_EXPECTED_APPLICANT_STATUS_COUNTS = {"pending": 288}
_EXPECTED_LISTED_IDENTIFIER_COVERAGE = 515
_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE = 285

_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_APPLICATION_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})(?:\s+(\(.*\)))?$")
_STRICT_IDENTIFIER = re.compile(r"^(?:\d{11}|[A-Za-z0-9]{16})$", re.I)


def _strict_identifiers(value: str) -> list[str]:
    raw = _clean(value).upper()
    return [raw] if _STRICT_IDENTIFIER.fullmatch(raw) else []


def _iso_date_parts(day: str, month: str, year: str, *, raw: str) -> str:
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError as exc:
        raise RuntimeError(f"Caltanissetta invalid calendar date: {raw!r}") from exc


def _parse_date(value: str) -> str:
    raw = _clean(value)
    match = _DATE.fullmatch(raw)
    if not match:
        raise RuntimeError(f"Caltanissetta unreviewed date typography: {raw!r}")
    day, month, year = match.groups()
    return _iso_date_parts(day, month, year, raw=raw)


def _parse_application_date(value: str) -> tuple[str, str]:
    raw = _clean(value)
    match = _APPLICATION_DATE.fullmatch(raw)
    if not match:
        raise RuntimeError(f"Caltanissetta unreviewed application date typography: {raw!r}")
    day, month, year, suffix = match.groups()
    return _iso_date_parts(day, month, year, raw=raw), _clean(suffix)


def _listed_status(note: str) -> str:
    folded = _clean(note).casefold()
    if not folded:
        return "listed"
    if "corso di aggiornamento" in folded or "rinnovo" in folded:
        return "renewal_update_in_progress"
    # Do not reinterpret source-explicit special conditions (including
    # collaborative preventive measures and suspension) as ordinary listing.
    return "other_or_unknown"


def _activities(raw: str) -> list[str]:
    value = _clean(raw)
    return [value] if value else []


def _validate_cfg(cfg: dict[str, Any], expected_source_key: str) -> None:
    if cfg.get("source_key") != expected_source_key:
        raise RuntimeError(
            f"Caltanissetta parser/source mismatch: {cfg.get('source_key')!r} != {expected_source_key!r}"
        )
    if cfg.get("authority_key") != "caltanissetta":
        raise RuntimeError("Caltanissetta parser bound to a non-Caltanissetta authority")
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"Caltanissetta reference date drift: {cfg.get('reference_date')!r}")


def parse_caltanissetta_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, "caltanissetta-listed")
    rows: list[dict[str, Any]] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGES:
            raise RuntimeError(f"Caltanissetta listed page-count drift: {len(pdf.pages)} != {_LISTED_PAGES}")
        for page_number, page in enumerate(pdf.pages, start=1):
            for table_number, table in enumerate(page.extract_tables(), start=1):
                for row_number, row in enumerate(table or [], start=1):
                    cells = [_clean(cell) for cell in row]
                    if len(cells) != 8:
                        continue
                    name, office, secondary, identifier_raw, listing_raw, expiry_raw, activities_raw, note = cells
                    if "ragione sociale" in name.casefold():
                        continue
                    if not (_DATE.fullmatch(listing_raw) and _DATE.fullmatch(expiry_raw)):
                        continue
                    rows.append(
                        {
                            "page": page_number,
                            "table": table_number,
                            "row": row_number,
                            "name": name,
                            "office": office,
                            "secondary": secondary,
                            "identifier_raw": identifier_raw,
                            "listing_raw": listing_raw,
                            "expiry_raw": expiry_raw,
                            "activities_raw": activities_raw,
                            "note": note,
                            "status": _listed_status(note),
                        }
                    )

    if len(rows) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(f"Caltanissetta listed row drift: {len(rows)} != {_EXPECTED_LISTED_RECORDS}")
    if len(
        {
            (
                row["name"].casefold(),
                row["identifier_raw"].casefold(),
                row["office"].casefold(),
                row["secondary"].casefold(),
                row["listing_raw"],
                row["expiry_raw"],
                row["activities_raw"].casefold(),
                row["note"].casefold(),
            )
            for row in rows
        }
    ) != len(rows):
        raise RuntimeError("Caltanissetta listed duplicate reviewed source observation")

    records: list[dict[str, Any]] = []
    for row in rows:
        record = _record(
            cfg,
            len(records) + 1,
            name=row["name"],
            office=row["office"],
            secondary=row["secondary"],
            identifier_raw=row["identifier_raw"],
            activities=_activities(row["activities_raw"]),
            status=row["status"],
            outcome_raw=row["note"],
            listing_date=_parse_date(row["listing_raw"]),
            expiry_date=_parse_date(row["expiry_raw"]),
            primary_date_label="Data iscrizione",
            source_fields={
                "listing_date_raw_variants": [row["listing_raw"]],
                "expiry_date_raw_variants": [row["expiry_raw"]],
                "activities_source": row["activities_raw"],
                "status_source": row["note"],
                "source_locator": f"p{row['page']}:t{row['table']}:r{row['row']}",
            },
        )
        record["identifiers"] = _strict_identifiers(row["identifier_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(f"Caltanissetta listed status drift: {status_counts!r}")
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != _EXPECTED_LISTED_IDENTIFIER_COVERAGE:
        raise RuntimeError(
            f"Caltanissetta listed identifier-coverage drift: {identifier_coverage} != {_EXPECTED_LISTED_IDENTIFIER_COVERAGE}"
        )

    diagnostics = {
        "parser": "caltanissetta_listed",
        "parser_version": PARSER_VERSION,
        "source_pages": _LISTED_PAGES,
        "public_records": len(records),
        "status_counts": status_counts,
        "identifier_coverage": identifier_coverage,
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records=records, diagnostics=diagnostics)


def parse_caltanissetta_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, "caltanissetta-applicants")
    rows: list[dict[str, Any]] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGES:
            raise RuntimeError(f"Caltanissetta applicant page-count drift: {len(pdf.pages)} != {_APPLICANT_PAGES}")
        for page_number, page in enumerate(pdf.pages, start=1):
            for table_number, table in enumerate(page.extract_tables(), start=1):
                for row_number, row in enumerate(table or [], start=1):
                    cells = [_clean(cell) for cell in row]
                    if len(cells) != 6:
                        continue
                    name, office, secondary, identifier_raw, activities_raw, application_raw = cells
                    if "ragione sociale" in name.casefold():
                        continue
                    if not _APPLICATION_DATE.fullmatch(application_raw):
                        continue
                    rows.append(
                        {
                            "page": page_number,
                            "table": table_number,
                            "row": row_number,
                            "name": name,
                            "office": office,
                            "secondary": secondary,
                            "identifier_raw": identifier_raw,
                            "activities_raw": activities_raw,
                            "application_raw": application_raw,
                        }
                    )

    if len(rows) != _EXPECTED_APPLICANT_RECORDS:
        raise RuntimeError(f"Caltanissetta applicant row drift: {len(rows)} != {_EXPECTED_APPLICANT_RECORDS}")
    if len(
        {
            (
                row["name"].casefold(),
                row["identifier_raw"].casefold(),
                row["office"].casefold(),
                row["secondary"].casefold(),
                row["application_raw"],
                row["activities_raw"].casefold(),
            )
            for row in rows
        }
    ) != len(rows):
        raise RuntimeError("Caltanissetta applicant duplicate reviewed source observation")

    records: list[dict[str, Any]] = []
    for row in rows:
        application_date, application_note = _parse_application_date(row["application_raw"])
        record = _record(
            cfg,
            len(records) + 1,
            name=row["name"],
            office=row["office"],
            secondary=row["secondary"],
            identifier_raw=row["identifier_raw"],
            activities=_activities(row["activities_raw"]),
            status="pending",
            outcome_raw="",
            application_date=application_date,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "application_date_raw_variants": [row["application_raw"]],
                "application_date_note": application_note,
                "activities_source": row["activities_raw"],
                "source_locator": f"p{row['page']}:t{row['table']}:r{row['row']}",
            },
        )
        record["identifiers"] = _strict_identifiers(row["identifier_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_APPLICANT_STATUS_COUNTS:
        raise RuntimeError(f"Caltanissetta applicant status drift: {status_counts!r}")
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE:
        raise RuntimeError(
            f"Caltanissetta applicant identifier-coverage drift: {identifier_coverage} != {_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE}"
        )

    diagnostics = {
        "parser": "caltanissetta_applicants",
        "parser_version": PARSER_VERSION,
        "source_pages": _APPLICANT_PAGES,
        "public_records": len(records),
        "status_counts": status_counts,
        "identifier_coverage": identifier_coverage,
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records=records, diagnostics=diagnostics)


PARSERS = {
    "caltanissetta_listed": parse_caltanissetta_listed,
    "caltanissetta_applicants": parse_caltanissetta_applicants,
}
