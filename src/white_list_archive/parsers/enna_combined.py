from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_NAME = "enna_combined"
PARSER_VERSION = "1"
SOURCE_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/wl-enna_3.pdf"
EXPECTED_SHA256 = "1a5dc0bc8cd6eef69724c1afe767108abdecc325f7f01e8ef80620cca0d622c6"
EXPECTED_BYTES = 1_350_854
EXPECTED_REFERENCE_DATE = "2026-09-18"
EXPECTED_SOURCE_KEY = "enna-combined"
EXPECTED_POPULATION_SCOPE = "listed_and_applicant"

_APPLICANT_HEADER = (
    "ragione sociale",
    "sede legale",
    "codice fiscale / partita iva",
    "attività per … ( * )",
    "data di presentazione istanza",
    "esito",
)
_LISTED_HEADER = (
    "ragione sociale",
    "sede legale",
    "codice fiscale / partita iva",
    "data di iscrizione",
    "data scadenza iscrizione",
    "note",
)
_EXPECTED_PAGE_ROWS = {
    1: 41,
    2: 112,
    3: 48,
    4: 70,
    5: 112,
    6: 112,
    7: 32,
    8: 93,
    9: 112,
    10: 112,
    11: 11,
    12: 92,
    13: 3,
    14: 9,
    15: 34,
    16: 76,
}
_EXPECTED_PAGE_SECTION = {
    2: 1,
    3: 1,
    4: 2,
    5: 3,
    6: 3,
    7: 3,
    8: 4,
    9: 5,
    10: 5,
    11: 5,
    12: 6,
    13: 7,
    14: 8,
    15: 9,
    16: 10,
}
_EXPECTED_PHYSICAL_NOTES = Counter({"": 900, "[ 2 ]": 128})
_EXPECTED_PUBLIC_STATUSES = Counter({
    "listed": 417,
    "renewal_update_in_progress": 57,
    "pending": 41,
})
_EXPECTED_LISTED_LOGICAL = 474
_EXPECTED_APPLICANTS = 41
_EXPECTED_PUBLIC_RECORDS = 515
_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_IDENTIFIER = re.compile(r"^(?:\d{11}|[A-Z0-9]{16})$", re.I)
_SECTION_LINE = re.compile(r"^Sezione\s+(\d{2})$", re.I)
_ACTIVITY_CODES = re.compile(r"^\d{1,2}(?:-\d{1,2})*$")


def _guard_cfg(cfg: dict[str, Any]) -> None:
    if cfg.get("source_key") != EXPECTED_SOURCE_KEY:
        raise RuntimeError(f"Enna source-key drift: expected {EXPECTED_SOURCE_KEY!r}, got {cfg.get('source_key')!r}")
    if cfg.get("population_scope") != EXPECTED_POPULATION_SCOPE:
        raise RuntimeError(
            f"Enna population-scope drift: expected {EXPECTED_POPULATION_SCOPE!r}, got {cfg.get('population_scope')!r}"
        )
    if cfg.get("reference_date") != EXPECTED_REFERENCE_DATE:
        raise RuntimeError(
            f"Enna reference-date drift: expected {EXPECTED_REFERENCE_DATE!r}, got {cfg.get('reference_date')!r}"
        )


def _source_date(raw: str, *, field: str, locator: str) -> str:
    value = _clean(raw)
    match = _DATE.fullmatch(value)
    if not match:
        raise RuntimeError(f"Enna {locator}: unsupported {field} date typography {raw!r}")
    day, month, year = map(int, match.groups())
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError as exc:
        raise RuntimeError(f"Enna {locator}: invalid {field} date {raw!r}") from exc


def _identifier(raw: str, *, locator: str) -> str:
    value = _clean(raw).upper()
    if not _IDENTIFIER.fullmatch(value):
        raise RuntimeError(f"Enna {locator}: unsupported identifier {raw!r}")
    return value


def _applicant_sections(raw: str) -> list[str]:
    value = _clean(raw)
    if not _ACTIVITY_CODES.fullmatch(value):
        raise RuntimeError(f"Enna applicant activity-code drift: {raw!r}")
    codes = [int(part) for part in value.split("-")]
    if not codes or len(codes) != len(set(codes)) or any(code < 1 or code > 10 for code in codes):
        raise RuntimeError(f"Enna applicant activity-code drift: {raw!r}")
    return [f"Sezione {code:02d}" for code in codes]


def _listed_status(note: str) -> str:
    value = _clean(note)
    if value == "":
        return "listed"
    if value == "[ 2 ]":
        return "renewal_update_in_progress"
    raise RuntimeError(f"Enna listed note vocabulary drift: {note!r}")


def _applicant_status(outcome: str) -> str:
    value = _clean(outcome)
    if value == "IN ISTRUTTORIA":
        return "pending"
    raise RuntimeError(f"Enna applicant outcome vocabulary drift: {outcome!r}")


def _exact_table(page: pdfplumber.page.Page, *, page_number: int) -> list[list[Any]]:
    tables = page.extract_tables()
    if len(tables) != 1 or not tables[0]:
        raise RuntimeError(f"Enna page {page_number}: expected exactly one table, found {len(tables)}")
    table = tables[0]
    header = tuple(_clean(value).casefold() for value in table[0])
    expected = _APPLICANT_HEADER if page_number == 1 else _LISTED_HEADER
    if header != expected:
        raise RuntimeError(f"Enna page {page_number}: header drift: expected {expected!r}, got {header!r}")
    return table


def _page_section(page: pdfplumber.page.Page, *, page_number: int) -> tuple[int, str, bool]:
    lines = [_clean(line) for line in (page.extract_text(x_tolerance=2, y_tolerance=3) or "").splitlines() if _clean(line)]
    matches = [(index, _SECTION_LINE.fullmatch(line)) for index, line in enumerate(lines)]
    matches = [(index, match) for index, match in matches if match]
    if len(matches) != 1:
        raise RuntimeError(f"Enna page {page_number}: expected one section marker, found {len(matches)}")
    index, match = matches[0]
    section = int(match.group(1))
    expected = _EXPECTED_PAGE_SECTION[page_number]
    if section != expected:
        raise RuntimeError(f"Enna page {page_number}: section drift: expected {expected}, got {section}")
    if index + 1 >= len(lines):
        raise RuntimeError(f"Enna page {page_number}: missing activity heading after section marker")
    heading = lines[index + 1]
    if section == 10 and index + 2 < len(lines) and lines[index + 2] == "GESTIONE DEI RIFIUTI":
        heading = _clean(f"{heading} {lines[index + 2]}")
    update_legend = "[ 2 ] AGGIORNAMENTO IN CORSO" in lines
    return section, heading, update_legend


def parse_enna_combined(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _guard_cfg(cfg)
    source_bytes = path.read_bytes()
    digest = hashlib.sha256(source_bytes).hexdigest()
    if len(source_bytes) != EXPECTED_BYTES:
        raise RuntimeError(f"Enna source-size drift: expected {EXPECTED_BYTES}, got {len(source_bytes)}")
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"Enna parser v{PARSER_VERSION} source digest drift: expected {EXPECTED_SHA256}, got {digest}")
    if cfg.get("sha256") and cfg["sha256"] != digest:
        raise RuntimeError(f"Enna config/source digest mismatch: cfg={cfg['sha256']}, source={digest}")

    applicant_rows: list[dict[str, Any]] = []
    listed_rows: list[dict[str, Any]] = []
    page_rows: dict[int, int] = {}
    physical_notes: Counter[str] = Counter()
    update_sections: set[int] = set()
    note_sections: set[int] = set()

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != 16:
            raise RuntimeError(f"Enna source layout changed: expected 16 pages, got {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, 1):
            table = _exact_table(page, page_number=page_number)
            data_rows = [[_clean(cell) for cell in row] for row in table[1:] if any(_clean(cell) for cell in row)]
            page_rows[page_number] = len(data_rows)
            if len(data_rows) != _EXPECTED_PAGE_ROWS[page_number]:
                raise RuntimeError(
                    f"Enna page {page_number}: row denominator drift: expected {_EXPECTED_PAGE_ROWS[page_number]}, got {len(data_rows)}"
                )
            if page_number == 1:
                for row_number, row in enumerate(data_rows, 1):
                    if len(row) != 6:
                        raise RuntimeError(f"Enna page 1 row {row_number}: expected 6 cells, got {len(row)}")
                    name, office, identifier_raw, activity_raw, application_raw, outcome = row
                    locator = f"page-1:row-{row_number}"
                    if not name or not office:
                        raise RuntimeError(f"Enna {locator}: blank company identity field")
                    identifier = _identifier(identifier_raw, locator=locator)
                    application_date = _source_date(application_raw, field="application", locator=locator)
                    activities = _applicant_sections(activity_raw)
                    status = _applicant_status(outcome)
                    applicant_rows.append({
                        "name": name,
                        "office": office,
                        "identifier": identifier,
                        "activity_raw": activity_raw,
                        "activities": activities,
                        "application_raw": application_raw,
                        "application_date": application_date,
                        "outcome": outcome,
                        "status": status,
                        "locator": locator,
                    })
                continue

            section, heading, update_legend = _page_section(page, page_number=page_number)
            if update_legend:
                update_sections.add(section)
            for row_number, row in enumerate(data_rows, 1):
                if len(row) != 6:
                    raise RuntimeError(f"Enna page {page_number} row {row_number}: expected 6 cells, got {len(row)}")
                name, office, identifier_raw, listing_raw, expiry_raw, note = row
                locator = f"page-{page_number}:row-{row_number}"
                if not name or not office:
                    raise RuntimeError(f"Enna {locator}: blank company identity field")
                identifier = _identifier(identifier_raw, locator=locator)
                listing_date = _source_date(listing_raw, field="listing", locator=locator)
                expiry_date = _source_date(expiry_raw, field="expiry", locator=locator)
                status = _listed_status(note)
                physical_notes[note] += 1
                if note == "[ 2 ]":
                    note_sections.add(section)
                listed_rows.append({
                    "name": name,
                    "office": office,
                    "identifier": identifier,
                    "listing_raw": listing_raw,
                    "listing_date": listing_date,
                    "expiry_raw": expiry_raw,
                    "expiry_date": expiry_date,
                    "note": note,
                    "status": status,
                    "section": section,
                    "heading": heading,
                    "locator": locator,
                })

    if page_rows != _EXPECTED_PAGE_ROWS:
        raise RuntimeError(f"Enna page-row denominators changed: expected {_EXPECTED_PAGE_ROWS!r}, got {page_rows!r}")
    if Counter(row["outcome"] for row in applicant_rows) != Counter({"IN ISTRUTTORIA": 41}):
        raise RuntimeError("Enna reviewed applicant outcome denominator drift")
    if len({row["identifier"] for row in applicant_rows}) != _EXPECTED_APPLICANTS:
        raise RuntimeError("Enna reviewed applicant identifier uniqueness drift")
    if physical_notes != _EXPECTED_PHYSICAL_NOTES:
        raise RuntimeError(
            f"Enna reviewed physical note denominator drift: expected {dict(_EXPECTED_PHYSICAL_NOTES)}, got {dict(physical_notes)}"
        )
    if not note_sections <= update_sections:
        raise RuntimeError(
            f"Enna source uses [ 2 ] without source-explicit AGGIORNAMENTO IN CORSO legend in sections {sorted(note_sections - update_sections)}"
        )

    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in listed_rows:
        key = (
            row["name"].casefold(),
            row["office"].casefold(),
            row["identifier"],
            row["listing_raw"],
            row["expiry_raw"],
            row["note"],
        )
        group = grouped.setdefault(key, {"row": row, "sections": [], "headings": [], "locators": []})
        section_label = f"Sezione {row['section']:02d}"
        for target, value in (
            (group["sections"], section_label),
            (group["headings"], row["heading"]),
            (group["locators"], row["locator"]),
        ):
            if value not in target:
                target.append(value)

    if len(grouped) != _EXPECTED_LISTED_LOGICAL:
        raise RuntimeError(
            f"Enna reviewed logical listed denominator drift: expected {_EXPECTED_LISTED_LOGICAL}, got {len(grouped)}"
        )

    records: list[dict[str, Any]] = []
    ordinal = 0
    for group in grouped.values():
        ordinal += 1
        row = group["row"]
        records.append(
            _record(
                cfg,
                ordinal,
                name=row["name"],
                office=row["office"],
                identifier_raw=row["identifier"],
                activities=group["sections"],
                status=row["status"],
                outcome_raw=row["note"],
                listing_date=row["listing_date"],
                expiry_date=row["expiry_date"],
                primary_date_label="Data iscrizione",
                source_fields={
                    "listing_date_raw_variants": [row["listing_raw"]],
                    "expiry_date_raw_variants": [row["expiry_raw"]],
                    "notes": [row["note"]] if row["note"] else [],
                    "sections": group["sections"],
                    "physical_locators": group["locators"],
                },
            )
        )

    for row in applicant_rows:
        ordinal += 1
        records.append(
            _record(
                cfg,
                ordinal,
                name=row["name"],
                office=row["office"],
                identifier_raw=row["identifier"],
                activities=row["activities"],
                status=row["status"],
                outcome_raw=row["outcome"],
                application_date=row["application_date"],
                primary_date_label="Data presentazione istanza",
                source_fields={
                    "requested_activities_source": row["activity_raw"],
                    "application_date_raw": row["application_raw"],
                    "physical_locators": [row["locator"]],
                },
            )
        )

    statuses = Counter(record["source_status"] for record in records)
    if statuses != _EXPECTED_PUBLIC_STATUSES:
        raise RuntimeError(
            f"Enna reviewed public status denominator drift: expected {dict(_EXPECTED_PUBLIC_STATUSES)}, got {dict(statuses)}"
        )
    if len(records) != _EXPECTED_PUBLIC_RECORDS:
        raise RuntimeError(f"Enna reviewed public denominator drift: expected {_EXPECTED_PUBLIC_RECORDS}, got {len(records)}")
    if sum(bool(record["identifiers"]) for record in records) != len(records):
        raise RuntimeError("Enna reviewed identifier coverage drift")

    diagnostics = {
        "parser": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "pages": 16,
        "page_rows": page_rows,
        "physical_source_rows": len(applicant_rows) + len(listed_rows),
        "physical_listed_rows": len(listed_rows),
        "applicant_rows": len(applicant_rows),
        "logical_listed_records": len(grouped),
        "public_records": len(records),
        "listed_section_memberships": sum(len(group["sections"]) for group in grouped.values()),
        "status_counts": dict(statuses),
        "physical_note_counts": dict(physical_notes),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "dropped_rows": 0,
    }
    return ParsedBatch(records, diagnostics)


PARSERS = {PARSER_NAME: parse_enna_combined}
