from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_NAME = "ravenna_combined"
PARSER_VERSION = "1"
SOURCE_URL = "https://prefettura.interno.gov.it/sites/default/files/64/2026-09/nuova_tabella_unica_17-sett-2026.pdf"
EXPECTED_SHA256 = "8d249118ca1fc90cb744a5a630a3c991eee44a963576a031596c9209910ac555"
_EXPECTED_PAGES = 29
_EXPECTED_ROWS = 706
_EXPECTED_PAGE_ROWS = [
    22, 24, 26, 24, 24, 23, 23, 24, 25, 25,
    25, 25, 26, 26, 24, 24, 26, 25, 26, 25,
    26, 24, 24, 25, 26, 26, 25, 26, 12,
]
_HEADER = (
    "N. prog.",
    "Ragione sociale e p. iva / cf",
    "Indirizzo sede legale",
    "DATA PRIMA RICHIESTA",
    "DATA ISCRIZIONE/ RINNOVO",
    "NOTE",
    "sez. I",
    "sez.II",
    "sez. III",
    "sez. IV",
    "sez. V",
    "sez. VI",
    "sez. VII",
    "sez. VIII",
    "sez. IX",
    "sez. X",
)
_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_IDENTIFIER = re.compile(r"(?<![A-Z0-9])([A-Z0-9]{16}|\d{11})(?![A-Z0-9])", re.I)
_REVIEWED_MALFORMED_DATES = frozenset({"23/06/026"})
_RENEWAL_NOTES = frozenset({
    "Richiesto rinnovo - Aggiornamento in corso",
    "Richiesta rinnovo - aggiornamento in corso",
})
_EXPECTED_STATUSES = Counter({
    "listed": 430,
    "renewal_update_in_progress": 212,
    "pending": 63,
    "other_or_unknown": 1,
})
_EXPECTED_IDENTIFIER_COVERAGE = 692


def _source_date(raw: str, *, field: str, ordinal: int) -> str:
    value = _clean(raw)
    if not value:
        return ""
    if value in _REVIEWED_MALFORMED_DATES:
        # Preserve the exact source token but never repair an omitted year digit.
        return ""
    match = _DATE.fullmatch(value)
    if not match:
        raise RuntimeError(f"Ravenna row {ordinal}: unsupported {field} source date {raw!r}")
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError as exc:
        raise RuntimeError(f"Ravenna row {ordinal}: invalid {field} source date {raw!r}") from exc


def _identity(company_raw: str) -> tuple[str, str, list[str]]:
    """Separate only structurally valid VAT/CF tokens visibly present in the source cell."""
    raw = _clean(company_raw)
    identifiers: list[str] = []
    spans: list[tuple[int, int]] = []
    for match in _IDENTIFIER.finditer(raw.upper()):
        token = match.group(1).upper()
        if token not in identifiers:
            identifiers.append(token)
        spans.append(match.span(1))
    if not spans:
        return raw, "", []
    chars = list(raw)
    for start, end in spans:
        for index in range(start, end):
            chars[index] = " "
    name = _clean("".join(chars))
    return name, " ".join(identifiers), identifiers


def _sections(cells: list[str]) -> tuple[list[str], list[str]]:
    if len(cells) != 10:
        raise RuntimeError(f"Ravenna section vector must contain 10 cells, got {len(cells)}")
    activities: list[str] = []
    markers: list[str] = []
    roman = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")
    for code, raw in zip(roman, cells, strict=True):
        marker = _clean(raw)
        if marker not in ("", "X", "X*"):
            raise RuntimeError(f"Ravenna source contains unsupported section marker {marker!r} for section {code}")
        if marker:
            activities.append(f"Sezione {code}")
            markers.append(f"{code}:{marker}")
    return activities, markers


def _status(*, application_raw: str, listing_raw: str, note_raw: str) -> str:
    if note_raw in _RENEWAL_NOTES:
        return "renewal_update_in_progress"
    if note_raw:
        # Preserve all other explicit notes as source evidence without assigning
        # a legal effect that the publication does not encode in our vocabulary.
        return "other_or_unknown"
    if listing_raw:
        return "listed"
    if application_raw:
        # Ravenna's official single table explicitly contains DATA PRIMA RICHIESTA;
        # absence of a listing date is used only together with this positive field.
        return "pending"
    return "other_or_unknown"


def _company_table(page: pdfplumber.page.Page, page_number: int) -> list[list[Any]]:
    matches: list[list[list[Any]]] = []
    for table in page.extract_tables():
        if not table or not table[0]:
            continue
        header = tuple(_clean(value) for value in table[0])
        if header == _HEADER:
            matches.append(table)
    if len(matches) != 1:
        raise RuntimeError(f"Ravenna page {page_number}: expected one exact company table, found {len(matches)}")
    return matches[0]


def _repair_reviewed_extraction(page_number: int, rows: list[list[str]]) -> list[list[str]]:
    """Repair one byte-pinned table-boundary miss proven by the same page text."""
    out = [list(row) for row in rows]
    if page_number != 26:
        return out
    if len(out) != 26:
        raise RuntimeError(f"Ravenna reviewed page 26 repair expects 26 rows, got {len(out)}")
    row = out[25]
    expected = {
        0: "1199",
        1: "",
        2: "MAASKADE 1199 BG ROTTERDAM",
        3: "10/12/2025",
        4: "",
        5: "",
        13: "X",
    }
    for index, value in expected.items():
        if row[index] != value:
            raise RuntimeError(
                f"Ravenna reviewed extraction repair no longer matches page 26 row 26 cell {index}: "
                f"expected {value!r}, got {row[index]!r}"
            )
    if any(row[index] for index in (6, 7, 8, 9, 10, 11, 12, 14, 15)):
        raise RuntimeError("Ravenna reviewed extraction repair no longer matches page 26 row 26 section signature")
    row[1] = "LOGLI MASSIMO DELLA MAASKADE RECQUIN BV"
    return out


def _record_from_cells(row: list[Any], cfg: dict[str, Any], ordinal: int) -> dict[str, Any]:
    if len(row) != 16:
        raise RuntimeError(f"Ravenna row {ordinal}: expected exactly 16 cells, got {len(row)}")
    progressive, company_raw, office, application_raw, listing_raw, note_raw, *section_cells = map(_clean, row)
    if not progressive.isdigit():
        raise RuntimeError(f"Ravenna row {ordinal}: nonnumeric progressive {progressive!r}")
    if not company_raw:
        raise RuntimeError(f"Ravenna row {ordinal}: company name is blank after reviewed extraction repair")
    if not office:
        raise RuntimeError(f"Ravenna row {ordinal}: registered office is blank")

    name, identifier_raw, identifiers = _identity(company_raw)
    if not name:
        raise RuntimeError(f"Ravenna row {ordinal}: company identity contains no name after identifier extraction")
    application_date = _source_date(application_raw, field="application", ordinal=ordinal)
    listing_date = _source_date(listing_raw, field="listing", ordinal=ordinal)
    status = _status(application_raw=application_raw, listing_raw=listing_raw, note_raw=note_raw)
    activities, section_markers = _sections(section_cells)
    malformed = []
    for field, raw, normalised in (
        ("application", application_raw, application_date),
        ("listing", listing_raw, listing_date),
    ):
        if raw and not normalised:
            malformed.append(f"{field}:{raw}")

    primary_label = "Data iscrizione" if listing_raw else ("Data presentazione istanza" if application_raw else "")
    source_fields = {
        "source_progressive": progressive,
        "company_identity_raw": company_raw,
        "registered_office_variants": [office],
        "application_date_raw_variants": [application_raw] if application_raw else [],
        "listing_date_raw_variants": [listing_raw] if listing_raw else [],
        "normalised_application_date_variants": [application_date] if application_date else [],
        "normalised_listing_date_variants": [listing_date] if listing_date else [],
        "note_raw": note_raw,
        "sections": [item.removeprefix("Sezione ") for item in activities],
        "section_markers": section_markers,
        "malformed_date_pairs": malformed,
    }
    record = _record(
        cfg,
        ordinal,
        name=name,
        office=office,
        identifier_raw=identifier_raw,
        activities=activities,
        status=status,
        outcome_raw=note_raw,
        application_date=application_date,
        listing_date=listing_date,
        primary_date_label=primary_label,
        source_fields=source_fields,
    )
    record["identifiers"] = identifiers
    return record


def parse_ravenna_combined(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    source_bytes = path.read_bytes()
    digest = hashlib.sha256(source_bytes).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"Ravenna parser v{PARSER_VERSION} source digest drift: expected {EXPECTED_SHA256}, got {digest}")
    if cfg.get("sha256") and cfg["sha256"] != digest:
        raise RuntimeError(f"Ravenna config/source digest mismatch: cfg={cfg['sha256']}, source={digest}")

    rows: list[list[str]] = []
    page_rows: list[int] = []
    progressives: list[str] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _EXPECTED_PAGES:
            raise RuntimeError(f"Ravenna source layout changed: expected {_EXPECTED_PAGES} pages, got {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, 1):
            table = _company_table(page, page_number)
            data_rows = [list(map(_clean, row)) for row in table[1:] if any(_clean(cell) for cell in row)]
            page_rows.append(len(data_rows))
            repaired = _repair_reviewed_extraction(page_number, data_rows)
            rows.extend(repaired)
            progressives.extend(row[0] for row in repaired)

    if page_rows != _EXPECTED_PAGE_ROWS:
        raise RuntimeError(f"Ravenna page-row denominators changed: expected {_EXPECTED_PAGE_ROWS}, got {page_rows}")
    if len(rows) != _EXPECTED_ROWS:
        raise RuntimeError(f"Ravenna source layout changed: expected {_EXPECTED_ROWS} rows, got {len(rows)}")
    if len(set(progressives)) != len(progressives):
        raise RuntimeError("Ravenna source contains duplicate progressive identifiers")

    records = [_record_from_cells(row, cfg, ordinal) for ordinal, row in enumerate(rows, 1)]
    statuses = Counter(record["source_status"] for record in records)
    if statuses != _EXPECTED_STATUSES:
        raise RuntimeError(f"Ravenna reviewed status denominator drift: expected {dict(_EXPECTED_STATUSES)}, got {dict(statuses)}")
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != _EXPECTED_IDENTIFIER_COVERAGE:
        raise RuntimeError(
            f"Ravenna reviewed identifier coverage drift: expected {_EXPECTED_IDENTIFIER_COVERAGE}, got {identifier_coverage}"
        )
    malformed = [record for record in records if record["source_fields"]["malformed_date_pairs"]]
    if len(malformed) != 1 or malformed[0]["source_fields"]["malformed_date_pairs"] != ["application:23/06/026"]:
        raise RuntimeError("Ravenna reviewed malformed-date boundary drift")

    diagnostics = {
        "parser": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "pages": _EXPECTED_PAGES,
        "page_rows": page_rows,
        "source_rows": len(rows),
        "public_records": len(records),
        "status_counts": dict(statuses),
        "identifier_coverage": identifier_coverage,
        "raw_identifier_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "malformed_date_rows": len(malformed),
        "dropped_rows": 0,
    }
    return ParsedBatch(records, diagnostics)


PARSERS = {PARSER_NAME: parse_ravenna_combined}
