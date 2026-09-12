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
_LISTED_PAGES = 89
_APPLICANT_PAGES = 68
_EXPECTED_LISTED_RECORDS = 950
_EXPECTED_APPLICANT_RECORDS = 1208
_EXPECTED_LISTED_STATUS_COUNTS = {
    "listed": 395,
    "renewal_update_in_progress": 548,
    "other_or_unknown": 7,
}
_EXPECTED_APPLICANT_STATUS_COUNTS = {"pending": 1208}
_EXPECTED_LISTED_ID_TOKEN_DISTRIBUTION = {0: 46, 1: 804, 2: 100}
_EXPECTED_APPLICANT_ID_TOKEN_DISTRIBUTION = {0: 125, 1: 1012, 2: 71}
_EXPECTED_LISTED_BLANK_REGISTRATION_DATES = 2
_EXPECTED_APPLICANT_BLANK_APPLICATION_DATES = 39

_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_DATE_PREFIX = re.compile(r"^(\d{2})/(\d{2})/(\d{4})(?:\s+(.*))?$")
_STRICT_IDENTIFIER_TOKEN = re.compile(r"(?<![A-Za-z0-9])(?:\d{11}|[A-Za-z0-9]{16})(?![A-Za-z0-9])", re.I)

# One source row puts an otherwise strict 11-digit identifier in the
# secondary-office column while leaving the P.IVA/C.F. column empty. This is
# reviewed and frozen by row index; no generic column-shift fallback exists.
_REVIEWED_LISTED_IDENTIFIER_SHIFT = {7: "03430130611"}

_REVIEWED_LISTED_NONCANONICAL_REGISTRATION = {
    488: "0/04/2024",
    537: "06/10/025",
    549: "21/0172026",
}
_REVIEWED_LISTED_NONCANONICAL_EXPIRY = {
    130: "28.102.025",
    187: "SCADENZA TERMINE MISURA ART. 94 BIS 14/05/2026",
    277: "14/072026",
    520: "27/0/2027 data di scadenza del Controllo Giudiziario di cui art/34 bis D/L/159/11",
    917: "0/06/2027",
}
_REVIEWED_LISTED_INVALID_SECTIONS = {
    190: "45721",
    444: "45818",
    488: "GIA COSTRUZIONI SRL",
}
_REVIEWED_APPLICANT_NONCANONICAL_DATES = {
    21: "'23/10/2025",
    56: "'12/06/2026",
    69: "06022026",
    112: "17/04/025",
    188: "28/25/2025",
    361: "26052025",
    479: "'04/02/2026",
    486: "'25/03/2026",
    509: "'22/02/2026",
    1060: "'03/06/2026",
    1131: "'08/04/2026",
    1203: "'06/02/2026",
}
_REVIEWED_APPLICANT_INVALID_SECTIONS = {536: ""}

_EXPECTED_LISTED_UPDATE_VALUES = {
    "in aggiornamento": 548,
    "": 395,
    "16/09/2026": 2,
    "prevenzione collaborativa ex art 94 bis per anni 1": 1,
    "società sottoposta a misura di prevenzione collaborativa ex art 94 bis": 1,
    "societa'sottoposta a controllo giud ex art 34 bis per anni tre": 1,
    "ordinanza cds 4595/2025 accoglie la cautelare ed annulla tar e provv.ti impugnati": 1,
    "soc. in liquidazione giudiziale disposta da trib smcv": 1,
}
_EXPECTED_APPLICANT_OUTCOME_VALUES = {
    "in istruttoria": 1184,
    "": 21,
    "in isruttoria": 2,
    "in aggiornamento": 1,
}


def _iso_date(day: str, month: str, year: str, *, raw: str) -> str:
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError as exc:
        raise RuntimeError(f"Caserta invalid calendar date: {raw!r}") from exc


def _parse_strict_date(raw: str) -> str:
    value = _clean(raw)
    match = _DATE.fullmatch(value)
    if not match:
        raise RuntimeError(f"Caserta unreviewed date typography: {value!r}")
    return _iso_date(*match.groups(), raw=value)


def _parse_expiry(raw: str) -> tuple[str, str]:
    value = _clean(raw)
    match = _DATE_PREFIX.fullmatch(value)
    if not match:
        raise RuntimeError(f"Caserta unreviewed expiry typography: {value!r}")
    day, month, year, tail = match.groups()
    return _iso_date(day, month, year, raw=value), _clean(tail)


def _identifier_tokens(raw: str) -> list[str]:
    value = _clean(raw).upper()
    return [match.group(0).upper() for match in _STRICT_IDENTIFIER_TOKEN.finditer(value)]


def _sections(raw: str, *, index: int, population: str) -> list[str]:
    value = _clean(raw)
    reviewed = (
        _REVIEWED_LISTED_INVALID_SECTIONS
        if population == "listed"
        else _REVIEWED_APPLICANT_INVALID_SECTIONS
    )
    if index in reviewed:
        if value != reviewed[index]:
            raise RuntimeError(
                f"Caserta {population} reviewed section drift at index {index}: {value!r} != {reviewed[index]!r}"
            )
        return []

    tokens = [int(token) for token in re.findall(r"\d+", value)]
    if not tokens or any(token < 1 or token > 10 for token in tokens):
        raise RuntimeError(f"Caserta {population} unreviewed section value at index {index}: {value!r}")
    if len(tokens) != len(set(tokens)):
        raise RuntimeError(f"Caserta {population} duplicate section token at index {index}: {value!r}")
    return [f"Sezione {token}" for token in tokens]


def _listed_status(raw: str) -> str:
    folded = _clean(raw).casefold()
    if not folded:
        return "listed"
    if folded == "in aggiornamento":
        return "renewal_update_in_progress"
    return "other_or_unknown"


def _validate_cfg(cfg: dict[str, Any], expected_source_key: str) -> None:
    if cfg.get("source_key") != expected_source_key:
        raise RuntimeError(f"Caserta parser/source mismatch: {cfg.get('source_key')!r} != {expected_source_key!r}")
    if cfg.get("authority_key") != "caserta":
        raise RuntimeError("Caserta parser bound to a non-Caserta authority")
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"Caserta reference date drift: {cfg.get('reference_date')!r}")


def _data_rows(path: Path, *, pages: int, width: int, population: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    header_rows = 0
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != pages:
            raise RuntimeError(f"Caserta {population} page-count drift: {len(pdf.pages)} != {pages}")
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            if len(tables) != 1:
                raise RuntimeError(f"Caserta {population} table-count drift on page {page_number}: {len(tables)} != 1")
            for table_number, table in enumerate(tables, start=1):
                for row_number, row in enumerate(table or [], start=1):
                    cells = [_clean(cell) for cell in row]
                    if not any(cells):
                        continue
                    if len(cells) != width:
                        raise RuntimeError(
                            f"Caserta {population} unreviewed table width p{page_number} r{row_number}: {len(cells)} != {width}"
                        )
                    if not cells[0].isdigit():
                        header_rows += 1
                        continue
                    rows.append(
                        {
                            "index": int(cells[0]),
                            "page": page_number,
                            "table": table_number,
                            "row": row_number,
                            "cells": cells,
                        }
                    )
    if header_rows != pages:
        raise RuntimeError(f"Caserta {population} header-row drift: {header_rows} != {pages}")
    expected = list(range(1, len(rows) + 1))
    indices = [row["index"] for row in rows]
    if indices != expected:
        raise RuntimeError(f"Caserta {population} source-index sequence drift")
    return rows


def parse_caserta_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, "caserta-listed")
    rows = _data_rows(path, pages=_LISTED_PAGES, width=9, population="listed")
    if len(rows) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(f"Caserta listed row drift: {len(rows)} != {_EXPECTED_LISTED_RECORDS}")

    update_values: Counter[str] = Counter()
    id_token_distribution: Counter[int] = Counter()
    blank_registration_dates = 0
    records: list[dict[str, Any]] = []

    for row in rows:
        index = row["index"]
        _, name, office, secondary, identifier_raw, registration_raw, expiry_raw, update_raw, section_raw = row["cells"]
        if not name:
            raise RuntimeError(f"Caserta listed blank name at index {index}")

        if index in _REVIEWED_LISTED_IDENTIFIER_SHIFT:
            expected_shift = _REVIEWED_LISTED_IDENTIFIER_SHIFT[index]
            if identifier_raw or secondary != expected_shift:
                raise RuntimeError(
                    f"Caserta listed reviewed identifier shift drift at index {index}: secondary={secondary!r}, id={identifier_raw!r}"
                )
            effective_identifier_raw = secondary
            secondary_for_record = ""
        else:
            effective_identifier_raw = identifier_raw
            secondary_for_record = secondary

        identifiers = _identifier_tokens(effective_identifier_raw)
        id_token_distribution[len(identifiers)] += 1

        if registration_raw:
            if index in _REVIEWED_LISTED_NONCANONICAL_REGISTRATION:
                expected_raw = _REVIEWED_LISTED_NONCANONICAL_REGISTRATION[index]
                if registration_raw != expected_raw:
                    raise RuntimeError(f"Caserta listed reviewed registration drift at index {index}")
                listing_date = ""
            else:
                listing_date = _parse_strict_date(registration_raw)
        else:
            blank_registration_dates += 1
            listing_date = ""

        if index in _REVIEWED_LISTED_NONCANONICAL_EXPIRY:
            expected_raw = _REVIEWED_LISTED_NONCANONICAL_EXPIRY[index]
            if expiry_raw != expected_raw:
                raise RuntimeError(f"Caserta listed reviewed expiry drift at index {index}")
            expiry_date, expiry_tail = "", ""
        else:
            expiry_date, expiry_tail = _parse_expiry(expiry_raw)

        sections = _sections(section_raw, index=index, population="listed")
        update_values[_clean(update_raw).casefold()] += 1
        status = _listed_status(update_raw)
        outcome_parts = [value for value in (_clean(update_raw), expiry_tail) if value]

        record = _record(
            cfg,
            len(records) + 1,
            name=name,
            office=office,
            secondary=secondary_for_record,
            identifier_raw=effective_identifier_raw,
            activities=sections,
            status=status,
            outcome_raw=" · ".join(outcome_parts),
            listing_date=listing_date,
            expiry_date=expiry_date,
            primary_date_label="Data iscrizione",
            source_fields={
                "sections": sections,
                "listing_date_raw_variants": [registration_raw] if registration_raw else [],
                "expiry_date_raw_variants": [expiry_raw] if expiry_raw else [],
                "in_aggiornamento": _clean(update_raw) if status == "renewal_update_in_progress" else "",
            },
        )
        record["identifiers"] = identifiers
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(f"Caserta listed status drift: {status_counts!r}")
    if dict(id_token_distribution) != _EXPECTED_LISTED_ID_TOKEN_DISTRIBUTION:
        raise RuntimeError(f"Caserta listed identifier-token drift: {dict(id_token_distribution)!r}")
    if blank_registration_dates != _EXPECTED_LISTED_BLANK_REGISTRATION_DATES:
        raise RuntimeError(
            f"Caserta listed blank-registration drift: {blank_registration_dates} != {_EXPECTED_LISTED_BLANK_REGISTRATION_DATES}"
        )
    if dict(update_values) != _EXPECTED_LISTED_UPDATE_VALUES:
        raise RuntimeError(f"Caserta listed update-field drift: {dict(update_values)!r}")

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "caserta_listed",
            "parser_version": PARSER_VERSION,
            "source_pages": _LISTED_PAGES,
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_token_distribution": dict(id_token_distribution),
            "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
            "blank_registration_dates": blank_registration_dates,
        },
    )


def parse_caserta_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, "caserta-applicants")
    rows = _data_rows(path, pages=_APPLICANT_PAGES, width=8, population="applicants")
    if len(rows) != _EXPECTED_APPLICANT_RECORDS:
        raise RuntimeError(f"Caserta applicant row drift: {len(rows)} != {_EXPECTED_APPLICANT_RECORDS}")

    outcome_values: Counter[str] = Counter()
    id_token_distribution: Counter[int] = Counter()
    blank_application_dates = 0
    records: list[dict[str, Any]] = []

    for row in rows:
        index = row["index"]
        _, name, office, secondary, identifier_raw, section_raw, application_raw, outcome_raw = row["cells"]
        if not name:
            raise RuntimeError(f"Caserta applicant blank name at index {index}")
        identifiers = _identifier_tokens(identifier_raw)
        id_token_distribution[len(identifiers)] += 1
        sections = _sections(section_raw, index=index, population="applicants")

        if application_raw:
            if index in _REVIEWED_APPLICANT_NONCANONICAL_DATES:
                expected_raw = _REVIEWED_APPLICANT_NONCANONICAL_DATES[index]
                if application_raw != expected_raw:
                    raise RuntimeError(f"Caserta applicant reviewed application-date drift at index {index}")
                application_date = ""
            else:
                application_date = _parse_strict_date(application_raw)
        else:
            blank_application_dates += 1
            application_date = ""

        outcome_values[_clean(outcome_raw).casefold()] += 1
        record = _record(
            cfg,
            len(records) + 1,
            name=name,
            office=office,
            secondary=secondary,
            identifier_raw=identifier_raw,
            activities=sections,
            status="pending",
            outcome_raw=outcome_raw,
            application_date=application_date,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "sections": sections,
                "application_date_raw_variants": [application_raw] if application_raw else [],
            },
        )
        record["identifiers"] = identifiers
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_APPLICANT_STATUS_COUNTS:
        raise RuntimeError(f"Caserta applicant status drift: {status_counts!r}")
    if dict(id_token_distribution) != _EXPECTED_APPLICANT_ID_TOKEN_DISTRIBUTION:
        raise RuntimeError(f"Caserta applicant identifier-token drift: {dict(id_token_distribution)!r}")
    if blank_application_dates != _EXPECTED_APPLICANT_BLANK_APPLICATION_DATES:
        raise RuntimeError(
            f"Caserta applicant blank-application drift: {blank_application_dates} != {_EXPECTED_APPLICANT_BLANK_APPLICATION_DATES}"
        )
    if dict(outcome_values) != _EXPECTED_APPLICANT_OUTCOME_VALUES:
        raise RuntimeError(f"Caserta applicant outcome-field drift: {dict(outcome_values)!r}")

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "caserta_applicants",
            "parser_version": PARSER_VERSION,
            "source_pages": _APPLICANT_PAGES,
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_token_distribution": dict(id_token_distribution),
            "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
            "blank_application_dates": blank_application_dates,
        },
    )


PARSERS = {
    "caserta_listed": parse_caserta_listed,
    "caserta_applicants": parse_caserta_applicants,
}
