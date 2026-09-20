from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-09-03"
_LISTED_PAGES = 81
_APPLICANT_PAGES = 27
_EXPECTED_LISTED_RAW_ROWS = 317
_EXPECTED_LISTED_RECORDS = 315
_EXPECTED_APPLICANT_RECORDS = 104
_EXPECTED_LISTED_STATUS_COUNTS = {
    "listed": 246,
    "renewal_update_in_progress": 67,
    "other_or_unknown": 2,
}
_EXPECTED_APPLICANT_STATUS_COUNTS = {"pending": 104}
_EXPECTED_LISTED_IDENTIFIER_COVERAGE = 312
_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE = 102
_EXPECTED_LISTED_EXPIRY_COVERAGE = 315
_EXPECTED_APPLICANT_DATE_COVERAGE = 103

_STRICT_IDENTIFIER = re.compile(r"^(?:\d{11}|[A-Za-z0-9]{16})$", re.I)
_DOTTED_DATE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
_DOTTED_DATE_PREFIX = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})(?:\s+.+)$")

_REVIEWED_LISTED_DATE_VARIANTS = {
    "13.8.2026": "2026-08-13",
    "18.6.2024": "2024-06-18",
}
_REVIEWED_LISTED_CONTINUATIONS = {
    "29.11.2022 Variazione assetto societario 16.01.2023 Istanza di rinnovo 13.09.2023 Istanza di rinnovo 09.09.2024 Istanza di rinnovo 09.10.2025",
    "Istanza di rinnovo 04.10.2023",
}
_REVIEWED_APPLICANT_ANNOTATED_DATES = {
    "07.01.2026 Precedente denominazione sociale: “GERVASI PAOLO S.R.L.”",
    "14.05.2025 Perfezionata in data 03.10.2025",
    "24.10.2023 E 11.07.2025",
    "06.02.2023 E 30.04.2024",
    "17.12.2025 Perfezionata il 24.04.2026",
    "11.07.2025 E 25.03.2026",
    "19.06.2024 E 14.04.2026",
    "30.09.2025 Integrata il 02.12.2025",
}
_REVIEWED_MALFORMED_APPLICATION_DATES = {"17.01/2024"}


def _strict_identifiers(value: str) -> list[str]:
    raw = _clean(value).upper()
    return [raw] if _STRICT_IDENTIFIER.fullmatch(raw) else []


def _date_from_parts(day: str, month: str, year: str, *, raw: str) -> str:
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError as exc:
        raise RuntimeError(f"Siracusa invalid calendar date: {raw!r}") from exc


def _parse_dotted_date(raw_value: str) -> str:
    raw = _clean(raw_value)
    match = _DOTTED_DATE.fullmatch(raw)
    if match:
        day, month, year = match.groups()
        return _date_from_parts(day, month, year, raw=raw)
    reviewed = _REVIEWED_LISTED_DATE_VARIANTS.get(raw)
    if reviewed:
        return reviewed
    raise RuntimeError(f"Siracusa unreviewed listed expiry typography: {raw!r}")


def _parse_application_date(raw_value: str) -> str:
    """Normalise only reviewed, source-explicit application-date typography.

    A leading clean date may coexist with an audited annotation or a second date;
    only the first source-explicit date is typed as the application date and the
    complete source cell remains in provenance. The one reviewed malformed value
    is retained raw and deliberately has no normalised application date.
    """
    raw = _clean(raw_value)
    if raw in _REVIEWED_MALFORMED_APPLICATION_DATES:
        return ""
    match = _DOTTED_DATE.fullmatch(raw)
    if match:
        day, month, year = match.groups()
        return _date_from_parts(day, month, year, raw=raw)
    if raw not in _REVIEWED_APPLICANT_ANNOTATED_DATES:
        raise RuntimeError(f"Siracusa unreviewed application-date typography: {raw!r}")
    match = _DOTTED_DATE_PREFIX.fullmatch(raw)
    if not match:
        raise RuntimeError(f"Siracusa reviewed application annotation lost leading date: {raw!r}")
    day, month, year = match.groups()
    return _date_from_parts(day, month, year, raw=raw)


def _listed_status(note: str) -> str:
    folded = _clean(note).casefold()
    if not folded:
        return "listed"
    if any(token in folded for token in ("rinnovo", "rinovo", "variazione assetto", "modifica assetto", "integrazione")):
        return "renewal_update_in_progress"
    # A bare date or a source statement that an application for cancellation was
    # filed is not reinterpreted as a legal outcome.
    return "other_or_unknown"


def _activities(raw: str) -> list[str]:
    value = _clean(raw)
    return [value] if value else []


def _validate_cfg(cfg: dict[str, Any], expected_source_key: str) -> None:
    if cfg.get("source_key") != expected_source_key:
        raise RuntimeError(
            f"Siracusa parser/source mismatch: {cfg.get('source_key')!r} != {expected_source_key!r}"
        )
    if cfg.get("authority_key") != "siracusa":
        raise RuntimeError("Siracusa parser bound to a non-Siracusa authority")
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"Siracusa reference-date drift: {cfg.get('reference_date')!r}")


def _validate_header(cells: list[str], *, population: str) -> None:
    folded = [value.casefold() for value in cells]
    if population == "listed":
        if len(cells) != 7 or not (
            "ragione sociale" in folded[0]
            and "sede legale" in folded[1]
            and "sede secondaria" in folded[2]
            and "codice fiscale" in folded[3]
            and "attivita" in folded[4].replace("’", "'").replace("à", "a")
            and "scadenza" in folded[5]
            and folded[6] == "note"
        ):
            raise RuntimeError(f"Siracusa listed header drift: {cells!r}")
    elif population == "applicant":
        if len(cells) != 6 or not (
            "ragione sociale" in folded[0]
            and "sede legale" in folded[1]
            and "sede secondaria" in folded[2]
            and "codice fiscale" in folded[3]
            and "sezioni" in folded[4]
            and "presentazione istanza" in folded[5]
        ):
            raise RuntimeError(f"Siracusa applicant header drift: {cells!r}")
    else:  # pragma: no cover - internal caller guard
        raise RuntimeError(f"Unknown Siracusa population: {population!r}")


def parse_siracusa_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, "siracusa-listed")
    rows: list[dict[str, Any]] = []
    raw_rows = 0
    continuation_values: list[str] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGES:
            raise RuntimeError(f"Siracusa listed page-count drift: {len(pdf.pages)} != {_LISTED_PAGES}")
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            if len(tables) != 1:
                raise RuntimeError(f"Siracusa listed table-count drift on page {page_number}: {len(tables)}")
            table = tables[0] or []
            if not table:
                raise RuntimeError(f"Siracusa listed empty table on page {page_number}")
            header = [_clean(cell) for cell in table[0]]
            _validate_header(header, population="listed")
            for row_number, row in enumerate(table[1:], start=2):
                cells = [_clean(cell) for cell in row]
                if len(cells) != 7:
                    raise RuntimeError(
                        f"Siracusa listed column-count drift page={page_number} row={row_number}: {len(cells)}"
                    )
                if not any(cells):
                    continue
                raw_rows += 1
                name, office, secondary, identifier_raw, activities_raw, expiry_raw, note = cells
                if not any((name, office, secondary, identifier_raw, activities_raw, expiry_raw)) and note:
                    if not rows:
                        raise RuntimeError("Siracusa orphan listed continuation row")
                    continuation_values.append(note)
                    rows[-1]["note"] = _clean(f"{rows[-1]['note']} {note}")
                    rows[-1]["physical_locators"].append(f"page {page_number} row {row_number}")
                    continue
                if not all((name, office, identifier_raw, activities_raw, expiry_raw)):
                    raise RuntimeError(
                        f"Siracusa incomplete listed source row page={page_number} row={row_number}: {cells!r}"
                    )
                rows.append(
                    {
                        "name": name,
                        "office": office,
                        "secondary": secondary,
                        "identifier_raw": identifier_raw,
                        "activities_raw": activities_raw,
                        "expiry_raw": expiry_raw,
                        "note": note,
                        "physical_locators": [f"page {page_number} row {row_number}"],
                    }
                )

    if raw_rows != _EXPECTED_LISTED_RAW_ROWS:
        raise RuntimeError(f"Siracusa listed raw-row drift: {raw_rows} != {_EXPECTED_LISTED_RAW_ROWS}")
    if set(continuation_values) != _REVIEWED_LISTED_CONTINUATIONS or len(continuation_values) != len(_REVIEWED_LISTED_CONTINUATIONS):
        raise RuntimeError(f"Siracusa listed continuation drift: {continuation_values!r}")
    if len(rows) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(f"Siracusa listed observation drift: {len(rows)} != {_EXPECTED_LISTED_RECORDS}")

    identity = {
        (
            row["name"].casefold(), row["office"].casefold(), row["secondary"].casefold(),
            row["identifier_raw"].casefold(), row["activities_raw"].casefold(),
            row["expiry_raw"], row["note"].casefold(),
        )
        for row in rows
    }
    if len(identity) != len(rows):
        raise RuntimeError("Siracusa listed duplicate reviewed source observation")

    records: list[dict[str, Any]] = []
    for row in rows:
        expiry = _parse_dotted_date(row["expiry_raw"])
        status = _listed_status(row["note"])
        record = _record(
            cfg,
            len(records) + 1,
            name=row["name"],
            office=row["office"],
            secondary=row["secondary"],
            identifier_raw=row["identifier_raw"],
            activities=_activities(row["activities_raw"]),
            status=status,
            outcome_raw=row["note"],
            expiry_date=expiry,
            primary_date_label="",
            source_fields={
                "requested_activities_source": row["activities_raw"],
                "expiry_date_raw_variants": [row["expiry_raw"]],
                "notes": [row["note"]] if row["note"] else [],
                "physical_locators": list(row["physical_locators"]),
            },
        )
        record["identifiers"] = _strict_identifiers(row["identifier_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(f"Siracusa listed status drift: {status_counts!r}")
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != _EXPECTED_LISTED_IDENTIFIER_COVERAGE:
        raise RuntimeError(
            f"Siracusa listed identifier-coverage drift: {identifier_coverage} != {_EXPECTED_LISTED_IDENTIFIER_COVERAGE}"
        )
    expiry_coverage = sum(bool(record["observed_expiry_date"]) for record in records)
    if expiry_coverage != _EXPECTED_LISTED_EXPIRY_COVERAGE:
        raise RuntimeError(
            f"Siracusa listed expiry-coverage drift: {expiry_coverage} != {_EXPECTED_LISTED_EXPIRY_COVERAGE}"
        )

    diagnostics = {
        "parser": "siracusa_listed",
        "parser_version": PARSER_VERSION,
        "source_pages": _LISTED_PAGES,
        "raw_rows": raw_rows,
        "continuation_rows": len(continuation_values),
        "public_records": len(records),
        "status_counts": status_counts,
        "identifier_coverage": identifier_coverage,
        "expiry_coverage": expiry_coverage,
    }
    return ParsedBatch(records=records, diagnostics=diagnostics)


def parse_siracusa_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, "siracusa-applicants")
    rows: list[dict[str, str]] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGES:
            raise RuntimeError(f"Siracusa applicant page-count drift: {len(pdf.pages)} != {_APPLICANT_PAGES}")
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            if len(tables) != 1:
                raise RuntimeError(f"Siracusa applicant table-count drift on page {page_number}: {len(tables)}")
            table = tables[0] or []
            if not table:
                raise RuntimeError(f"Siracusa applicant empty table on page {page_number}")
            header = [_clean(cell) for cell in table[0]]
            _validate_header(header, population="applicant")
            for row_number, row in enumerate(table[1:], start=2):
                cells = [_clean(cell) for cell in row]
                if len(cells) != 6:
                    raise RuntimeError(
                        f"Siracusa applicant column-count drift page={page_number} row={row_number}: {len(cells)}"
                    )
                if not any(cells):
                    continue
                name, office, secondary, identifier_raw, activities_raw, application_raw = cells
                if not all((name, office, identifier_raw, activities_raw, application_raw)):
                    raise RuntimeError(
                        f"Siracusa incomplete applicant source row page={page_number} row={row_number}: {cells!r}"
                    )
                rows.append(
                    {
                        "name": name,
                        "office": office,
                        "secondary": secondary,
                        "identifier_raw": identifier_raw,
                        "activities_raw": activities_raw,
                        "application_raw": application_raw,
                        "physical_locator": f"page {page_number} row {row_number}",
                    }
                )

    if len(rows) != _EXPECTED_APPLICANT_RECORDS:
        raise RuntimeError(f"Siracusa applicant observation drift: {len(rows)} != {_EXPECTED_APPLICANT_RECORDS}")
    identity = {
        (
            row["name"].casefold(), row["office"].casefold(), row["secondary"].casefold(),
            row["identifier_raw"].casefold(), row["activities_raw"].casefold(), row["application_raw"],
        )
        for row in rows
    }
    if len(identity) != len(rows):
        raise RuntimeError("Siracusa applicant duplicate reviewed source observation")

    records: list[dict[str, Any]] = []
    for row in rows:
        application_date = _parse_application_date(row["application_raw"])
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
            primary_date_label="Data presentazione istanza" if application_date else "",
            source_fields={
                "requested_activities_source": row["activities_raw"],
                "application_date_raw_variants": [row["application_raw"]],
                "physical_locator": row["physical_locator"],
            },
        )
        record["identifiers"] = _strict_identifiers(row["identifier_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_APPLICANT_STATUS_COUNTS:
        raise RuntimeError(f"Siracusa applicant status drift: {status_counts!r}")
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE:
        raise RuntimeError(
            f"Siracusa applicant identifier-coverage drift: {identifier_coverage} != {_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE}"
        )
    application_date_coverage = sum(bool(record["application_date"]) for record in records)
    if application_date_coverage != _EXPECTED_APPLICANT_DATE_COVERAGE:
        raise RuntimeError(
            f"Siracusa applicant date-coverage drift: {application_date_coverage} != {_EXPECTED_APPLICANT_DATE_COVERAGE}"
        )

    diagnostics = {
        "parser": "siracusa_applicants",
        "parser_version": PARSER_VERSION,
        "source_pages": _APPLICANT_PAGES,
        "public_records": len(records),
        "status_counts": status_counts,
        "identifier_coverage": identifier_coverage,
        "application_date_coverage": application_date_coverage,
        "reviewed_malformed_application_dates": len(_REVIEWED_MALFORMED_APPLICATION_DATES),
    }
    return ParsedBatch(records=records, diagnostics=diagnostics)


PARSERS = {
    "siracusa_listed": parse_siracusa_listed,
    "siracusa_applicants": parse_siracusa_applicants,
}
