from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_LISTED_SOURCE_KEY = "frosinone-listed"
_APPLICANT_SOURCE_KEY = "frosinone-applicants"
_REFERENCE_DATE = "2026-09-02"
_LISTED_PAGES = 91
_APPLICANT_PAGES = 37
_EXPECTED_LISTED_RECORDS = 761
_EXPECTED_LISTED_STATUS_COUNTS = {"listed": 529, "renewal_update_in_progress": 232}
_EXPECTED_LISTED_ADMIN_ROWS = 5
_EXPECTED_LISTED_FRAGMENT_ROWS = 44
_EXPECTED_LISTED_IDENTIFIER_COVERAGE = 737
_EXPECTED_LISTED_RAW_IDENTIFIER_ONLY = 24
_EXPECTED_LISTED_BLANK_SECTIONS = 3
_EXPECTED_APPLICANT_RECORDS = 475
_EXPECTED_APPLICANT_STATUS_COUNTS = {"pending": 475}
_EXPECTED_APPLICANT_FRAGMENT_ROWS = 5
_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE = 473
_EXPECTED_APPLICANT_RAW_IDENTIFIER_ONLY = 2
_EXPECTED_APPLICANT_BLANK_SECTIONS = 0

_STRICT_IDENTIFIER = re.compile(r"(?<![A-Za-z0-9])(?:\d{11}|[A-Za-z]{6}[0-9A-Za-z]{10})(?![A-Za-z0-9])")
_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_YEAR = re.compile(r"20\d{2}")
_ADMIN_ONLY = re.compile(r"^(?:n\.?\s*)?\d+$", re.I)

_REVIEWED_LISTED_NOTES = {
    "Con atto notarile in data 21/12/2022 le quote sociali della Soc.ta’ Mitas Endustri Sanayi Ticaret Anonimi Sirketi son state cedute alla soc.ta’ S.r.l. c. f. 03192460602; la Mitas ecc… in data 01/03/2023 e’ stata cancellata dal registro imprese di Frosinone",
    "LA SOCIETA’ HA TRASFERITO LA SEDE LEGALE A ROMA IL 12/01/2024",
    "Aggiornamento in corso per richiesta a",
    "permanere del 11/02/2026",
}

_REVIEWED_LISTED_MALFORMED_DATES = {
    "30/07/*2026",
    "27/0/2024",
    "224/02/2027",
    "24/02/20270",
    "12/15/2025",
    "11/15/2026",
    "14/02/2025CO S.MO",
    "1 6 / 1 0/2025",
}

_REVIEWED_APPLICANT_OUTCOMES = {
    "ISTRUTTORIA IN CORSO",
    "ISTRUTTORIA PIN CORSO",
    "ISTRUITTORIA IN CORSO",
    "ISTRUZIONI IN CORSO",
    "ISTRUTTORIA IN CORSA",
    "ISTRUTTORIA IN CORSO.",
    "",
}
_REVIEWED_APPLICANT_OUTCOME_COUNTS = {
    "ISTRUTTORIA IN CORSO": 466,
    "ISTRUTTORIA PIN CORSO": 1,
    "ISTRUITTORIA IN CORSO": 1,
    "ISTRUZIONI IN CORSO": 1,
    "ISTRUTTORIA IN CORSA": 1,
    "ISTRUTTORIA IN CORSO.": 1,
    "": 4,
}
_REVIEWED_APPLICANT_MALFORMED_DATES = {"06/08/2025s", "13/05/206"}
_REVIEWED_APPLICANT_ID_CONTINUATION = (29, 1, 1)
_REVIEWED_APPLICANT_ID_CONTINUATION_NAME = "PAGLIAROLI LORENZO – IMPRESA INDIVIDUALE"


def _validate_cfg(cfg: dict[str, Any], *, source_key: str) -> None:
    if cfg.get("source_key") != source_key:
        raise RuntimeError(f"Frosinone parser/source mismatch: {cfg.get('source_key')!r} != {source_key!r}")
    if cfg.get("authority_key") != "frosinone":
        raise RuntimeError("Frosinone parser bound to a non-Frosinone authority")
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"Frosinone reference-date drift: {cfg.get('reference_date')!r} != {_REFERENCE_DATE!r}")


def _strict_identifiers(value: str) -> list[str]:
    return list(dict.fromkeys(match.group(0).upper() for match in _STRICT_IDENTIFIER.finditer(_clean(value))))


def _parse_date(value: str) -> str:
    raw = _clean(value)
    match = _DATE.fullmatch(raw)
    if not match:
        return ""
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def _is_header(row: list[str]) -> bool:
    folded = " | ".join(row).casefold()
    return (
        ("denominaz" in folded and "codice fiscale" in folded)
        or ("ragione sociale" in folded and "codice fiscale" in folded)
    )


def _listed_semantic_row(row: list[str]) -> list[str]:
    if len(row) < 7:
        raise RuntimeError(f"Frosinone listed row-width below seven columns: {len(row)}")
    return row[:6] + [_clean(" ".join(value for value in row[6:] if value))]


def _merge_fragment(record: dict[str, Any], cells: list[str], locator: str) -> None:
    before = list(record["cells"])
    for index, value in enumerate(cells):
        if value:
            record["cells"][index] = _clean(f"{record['cells'][index]} {value}")
    record["fragments"].append({"source_locator": locator, "cells": cells, "before": before})


def _reviewed_date(raw: str, *, allowed_malformed: set[str], label: str) -> str:
    value = _clean(raw)
    if not value:
        return ""
    parsed = _parse_date(value)
    if parsed:
        return parsed
    if value in allowed_malformed:
        return ""
    raise RuntimeError(f"Frosinone unreviewed malformed {label}: {value!r}")


def _listed_status(note: str) -> str:
    value = _clean(note)
    if not value:
        return "listed"
    folded = value.casefold()
    if "aggiornamento in corso" in folded and "permanere" in folded:
        return "renewal_update_in_progress"
    if value in _REVIEWED_LISTED_NOTES:
        return "listed"
    raise RuntimeError(f"Frosinone unreviewed listed note/status: {value!r}")


def _activity_parts(value: str) -> list[str]:
    raw = _clean(value)
    return [raw] if raw else []


def parse_frosinone_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key=_LISTED_SOURCE_KEY)
    assembled: list[dict[str, Any]] = []
    administrative_rows = 0
    fragment_rows = 0

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGES:
            raise RuntimeError(f"Frosinone listed page-count drift: {len(pdf.pages)} != {_LISTED_PAGES}")
        current: dict[str, Any] | None = None
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            if len(tables) != 1:
                raise RuntimeError(f"Frosinone listed page {page_number} table-count drift: {len(tables)} != 1")
            for row_number, raw_row in enumerate(tables[0] or [], start=1):
                row = [_clean(cell) for cell in (raw_row or [])]
                if not any(row) or _is_header(row):
                    continue
                cells = _listed_semantic_row(row)
                nonblank = [value for value in cells if value]
                locator = f"p{page_number}:r{row_number}"
                if not cells[0] and len(nonblank) == 1 and _ADMIN_ONLY.fullmatch(nonblank[0]):
                    administrative_rows += 1
                    continue
                independent_evidence = bool(
                    _strict_identifiers(cells[2]) or _YEAR.search(cells[3]) or _YEAR.search(cells[4])
                )
                if cells[0] and independent_evidence:
                    current = {"cells": cells, "source_locator": locator, "fragments": []}
                    assembled.append(current)
                    continue
                if not cells[0] and independent_evidence:
                    raise RuntimeError(f"Frosinone listed identity/date row without company name at {locator}: {cells!r}")
                if current is None:
                    raise RuntimeError(f"Frosinone orphan listed continuation at {locator}: {cells!r}")
                _merge_fragment(current, cells, locator)
                fragment_rows += 1

    if len(assembled) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(f"Frosinone listed record-count drift: {len(assembled)} != {_EXPECTED_LISTED_RECORDS}")
    if administrative_rows != _EXPECTED_LISTED_ADMIN_ROWS:
        raise RuntimeError(
            f"Frosinone listed administrative-row drift: {administrative_rows} != {_EXPECTED_LISTED_ADMIN_ROWS}"
        )
    if fragment_rows != _EXPECTED_LISTED_FRAGMENT_ROWS:
        raise RuntimeError(f"Frosinone listed fragment-row drift: {fragment_rows} != {_EXPECTED_LISTED_FRAGMENT_ROWS}")

    records: list[dict[str, Any]] = []
    reviewed_notes = Counter()
    malformed_dates = Counter()
    blank_sections = 0
    for item in assembled:
        cells = item["cells"]
        note = _clean(cells[6])
        status = _listed_status(note)
        if note in _REVIEWED_LISTED_NOTES:
            reviewed_notes[note] += 1
        listing_date = _reviewed_date(
            cells[3], allowed_malformed=_REVIEWED_LISTED_MALFORMED_DATES, label="listed listing date"
        )
        expiry_date = _reviewed_date(
            cells[4], allowed_malformed=_REVIEWED_LISTED_MALFORMED_DATES, label="listed expiry date"
        )
        for raw_date in (cells[3], cells[4]):
            value = _clean(raw_date)
            if value and not _parse_date(value):
                malformed_dates[value] += 1
        if not cells[5]:
            blank_sections += 1
        record = _record(
            cfg,
            len(records) + 1,
            name=cells[0],
            office=cells[1],
            identifier_raw=cells[2],
            activities=_activity_parts(cells[5]),
            status=status,
            outcome_raw=note,
            listing_date=listing_date,
            expiry_date=expiry_date,
            primary_date_label="Data iscrizione",
            source_fields={
                "source_locator": item["source_locator"],
                "continuation_fragments": item["fragments"],
                "identifier_raw": cells[2],
                "listing_date_raw": cells[3],
                "expiry_date_raw": cells[4],
                "sections_raw": cells[5],
                "note_raw": note,
            },
        )
        record["identifiers"] = _strict_identifiers(cells[2])
        records.append(record)

    expected_note_counts = Counter({note: 1 for note in _REVIEWED_LISTED_NOTES})
    if reviewed_notes != expected_note_counts:
        raise RuntimeError(f"Frosinone reviewed listed-note drift: {dict(reviewed_notes)!r}")
    expected_malformed_counts = Counter({value: 1 for value in _REVIEWED_LISTED_MALFORMED_DATES})
    if malformed_dates != expected_malformed_counts:
        raise RuntimeError(f"Frosinone listed malformed-date drift: {dict(malformed_dates)!r}")
    if blank_sections != _EXPECTED_LISTED_BLANK_SECTIONS:
        raise RuntimeError(f"Frosinone listed blank-section drift: {blank_sections} != {_EXPECTED_LISTED_BLANK_SECTIONS}")

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(
            f"Frosinone listed status-count drift: {status_counts!r} != {_EXPECTED_LISTED_STATUS_COUNTS!r}"
        )
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    raw_identifier_only = sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records)
    if identifier_coverage != _EXPECTED_LISTED_IDENTIFIER_COVERAGE or raw_identifier_only != _EXPECTED_LISTED_RAW_IDENTIFIER_ONLY:
        raise RuntimeError(
            "Frosinone listed identifier-coverage drift: "
            f"strict={identifier_coverage}, raw_only={raw_identifier_only}"
        )

    return ParsedBatch(
        records,
        {
            "parser": "frosinone_listed",
            "parser_version": PARSER_VERSION,
            "source_rows": len(records),
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_coverage": identifier_coverage,
            "raw_identifier_only": raw_identifier_only,
            "administrative_rows_excluded": administrative_rows,
            "continuation_fragments_joined": fragment_rows,
            "reviewed_malformed_dates": sum(malformed_dates.values()),
            "blank_sections": blank_sections,
        },
    )


def parse_frosinone_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key=_APPLICANT_SOURCE_KEY)
    assembled: list[dict[str, Any]] = []
    fragment_rows = 0
    reviewed_identity_continuations = 0

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGES:
            raise RuntimeError(f"Frosinone applicant page-count drift: {len(pdf.pages)} != {_APPLICANT_PAGES}")
        current: dict[str, Any] | None = None
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            if not tables:
                raise RuntimeError(f"Frosinone applicant page {page_number} has no extracted table")
            for table_number, table in enumerate(tables, start=1):
                for row_number, raw_row in enumerate(table or [], start=1):
                    cells = [_clean(cell) for cell in (raw_row or [])]
                    if not any(cells) or _is_header(cells):
                        continue
                    if len(cells) != 7:
                        raise RuntimeError(
                            f"Frosinone applicant row-width drift p{page_number}:t{table_number}:r{row_number}: {len(cells)}"
                        )
                    locator_tuple = (page_number, table_number, row_number)
                    locator = f"p{page_number}:t{table_number}:r{row_number}"
                    independent_evidence = bool(cells[3] or cells[5] or cells[6])
                    if cells[0] and independent_evidence:
                        current = {"cells": cells, "source_locator": locator, "fragments": []}
                        assembled.append(current)
                        continue
                    if not cells[0] and independent_evidence:
                        if locator_tuple != _REVIEWED_APPLICANT_ID_CONTINUATION:
                            raise RuntimeError(
                                f"Frosinone applicant identity/date/outcome row without company name at {locator}: {cells!r}"
                            )
                        if current is None or current["cells"][0] != _REVIEWED_APPLICANT_ID_CONTINUATION_NAME:
                            raise RuntimeError(
                                "Frosinone reviewed applicant identifier continuation drift: "
                                f"expected {_REVIEWED_APPLICANT_ID_CONTINUATION_NAME!r}, "
                                f"got {current and current['cells'][0]!r}"
                            )
                        _merge_fragment(current, cells, locator)
                        reviewed_identity_continuations += 1
                        fragment_rows += 1
                        continue
                    if current is None:
                        raise RuntimeError(f"Frosinone orphan applicant continuation at {locator}: {cells!r}")
                    _merge_fragment(current, cells, locator)
                    fragment_rows += 1

    if len(assembled) != _EXPECTED_APPLICANT_RECORDS:
        raise RuntimeError(f"Frosinone applicant record-count drift: {len(assembled)} != {_EXPECTED_APPLICANT_RECORDS}")
    if fragment_rows != _EXPECTED_APPLICANT_FRAGMENT_ROWS:
        raise RuntimeError(
            f"Frosinone applicant fragment-row drift: {fragment_rows} != {_EXPECTED_APPLICANT_FRAGMENT_ROWS}"
        )
    if reviewed_identity_continuations != 1:
        raise RuntimeError(
            f"Frosinone reviewed applicant identity-continuation drift: {reviewed_identity_continuations} != 1"
        )

    records: list[dict[str, Any]] = []
    outcome_counts = Counter()
    malformed_dates = Counter()
    blank_sections = 0
    for item in assembled:
        cells = item["cells"]
        outcome = _clean(cells[6])
        if outcome not in _REVIEWED_APPLICANT_OUTCOMES:
            raise RuntimeError(f"Frosinone unreviewed applicant outcome: {outcome!r}")
        outcome_counts[outcome] += 1
        application_date = _reviewed_date(
            cells[5], allowed_malformed=_REVIEWED_APPLICANT_MALFORMED_DATES, label="applicant application date"
        )
        raw_application_date = _clean(cells[5])
        if raw_application_date and not _parse_date(raw_application_date):
            malformed_dates[raw_application_date] += 1
        if not cells[4]:
            blank_sections += 1
        record = _record(
            cfg,
            len(records) + 1,
            name=cells[0],
            office=cells[1],
            secondary=cells[2],
            identifier_raw=cells[3],
            activities=_activity_parts(cells[4]),
            status="pending",
            outcome_raw=outcome,
            application_date=application_date,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "source_locator": item["source_locator"],
                "continuation_fragments": item["fragments"],
                "identifier_raw": cells[3],
                "sections_raw": cells[4],
                "application_date_raw": cells[5],
                "outcome_raw": outcome,
            },
        )
        record["identifiers"] = _strict_identifiers(cells[3])
        records.append(record)

    if dict(outcome_counts) != _REVIEWED_APPLICANT_OUTCOME_COUNTS:
        raise RuntimeError(
            f"Frosinone applicant outcome-count drift: {dict(outcome_counts)!r} != {_REVIEWED_APPLICANT_OUTCOME_COUNTS!r}"
        )
    expected_malformed_counts = Counter({value: 1 for value in _REVIEWED_APPLICANT_MALFORMED_DATES})
    if malformed_dates != expected_malformed_counts:
        raise RuntimeError(f"Frosinone applicant malformed-date drift: {dict(malformed_dates)!r}")
    if blank_sections != _EXPECTED_APPLICANT_BLANK_SECTIONS:
        raise RuntimeError(
            f"Frosinone applicant blank-section drift: {blank_sections} != {_EXPECTED_APPLICANT_BLANK_SECTIONS}"
        )

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_APPLICANT_STATUS_COUNTS:
        raise RuntimeError(
            f"Frosinone applicant status-count drift: {status_counts!r} != {_EXPECTED_APPLICANT_STATUS_COUNTS!r}"
        )
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    raw_identifier_only = sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records)
    if identifier_coverage != _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE or raw_identifier_only != _EXPECTED_APPLICANT_RAW_IDENTIFIER_ONLY:
        raise RuntimeError(
            "Frosinone applicant identifier-coverage drift: "
            f"strict={identifier_coverage}, raw_only={raw_identifier_only}"
        )

    return ParsedBatch(
        records,
        {
            "parser": "frosinone_applicants",
            "parser_version": PARSER_VERSION,
            "source_rows": len(records),
            "public_records": len(records),
            "status_counts": status_counts,
            "outcome_counts": dict(outcome_counts),
            "identifier_coverage": identifier_coverage,
            "raw_identifier_only": raw_identifier_only,
            "continuation_fragments_joined": fragment_rows,
            "reviewed_identity_continuations": reviewed_identity_continuations,
            "reviewed_malformed_dates": sum(malformed_dates.values()),
            "blank_sections": blank_sections,
        },
    )
