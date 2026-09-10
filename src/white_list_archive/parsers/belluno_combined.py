from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_NAME = "belluno_combined"
PARSER_VERSION = "1"
_EXPECTED_PAGES = 44
_EXPECTED_DATA_PAGES = 42
_EXPECTED_SOURCE_ROWS = 402
_HEADER = (
    "ragione sociale",
    "sede legale",
    "codice fiscale partita iva",
    "data iscrizione",
    "data scadenza iscrizione",
    "sezioni",
    "note",
    "data presentazione istanza",
)
_DATE_TOKEN = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)")
_ROMAN_SECTION = re.compile(r"(?<![A-Z])(VIII|VII|III|VI|IV|IX|II|V|X|I)(?![A-Z])", re.I)
_FOOTNOTE_ONLY = re.compile(r"^[A-Za-z]$")


def _fold_row(row: list[str]) -> tuple[str, ...]:
    return tuple(_clean(value).casefold() for value in row)


def _valid_date_token(raw: str, *, required: bool) -> str:
    raw = _clean(raw)
    matches = list(_DATE_TOKEN.finditer(raw))
    if not matches:
        if required:
            raise ValueError(f"Missing required Belluno date token: {raw!r}")
        return ""
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one Belluno date token, found {len(matches)} in {raw!r}")
    day, month, year = map(int, matches[0].groups())
    try:
        parsed = date(year, month, day)
    except ValueError as exc:
        raise ValueError(f"Invalid Belluno date token in {raw!r}") from exc
    return parsed.isoformat()


def _sections(raw: str) -> list[str]:
    raw = _clean(raw).upper()
    values: list[str] = []
    for match in _ROMAN_SECTION.finditer(raw):
        value = match.group(1).upper()
        if value not in values:
            values.append(value)
    if not values:
        raise ValueError(f"Missing Belluno White List section code: {raw!r}")
    residue = _ROMAN_SECTION.sub("", raw)
    residue = re.sub(r"[\s\-–—·;,]+", "", residue)
    if residue:
        raise ValueError(f"Unsupported Belluno section-cell content: {raw!r}")
    return values


def _status(note: str, *, applicant: bool) -> str:
    folded = _clean(note).casefold()
    if applicant:
        if folded == "in fase istruttoria":
            return "pending"
        raise ValueError(f"Belluno applicant row lacks the explicit in-progress outcome: {note!r}")
    if not folded:
        return "listed"
    if "aggiornamento in corso" in folded and "iscrizione resta valida anche oltre la scadenza" in folded:
        return "renewal_update_in_progress"
    if folded.startswith("scaduta:"):
        return "expired_observed"
    raise ValueError(f"Unsupported Belluno listed-row note: {note!r}")


def _parse_row(row: list[str], cfg: dict[str, Any], row_ordinal: int) -> tuple[dict[str, Any], bool]:
    if len(row) != 8:
        raise ValueError(f"Belluno source row must have eight columns, got {len(row)}: {row!r}")
    name, office, identifier_raw, listing_raw, expiry_raw, sections_raw, note, application_raw = map(_clean, row)
    if not name:
        raise ValueError(f"Belluno source row lacks a company name: {row!r}")

    section_codes = _sections(sections_raw)
    activities = [f"Sezione {code}" for code in section_codes]
    note_folded = note.casefold()
    applicant = note_folded == "in fase istruttoria"

    if applicant:
        if expiry_raw:
            raise ValueError(f"Belluno applicant row unexpectedly has an expiry value: {row!r}")
        if listing_raw and not _FOOTNOTE_ONLY.fullmatch(listing_raw):
            raise ValueError(f"Belluno applicant row has unsupported listing-cell content: {row!r}")
        listing_date = ""
        expiry_date = ""
        application_date = _valid_date_token(application_raw, required=True)
        primary_label = "Data presentazione istanza"
    else:
        listing_date = _valid_date_token(listing_raw, required=True)
        expiry_date = _valid_date_token(expiry_raw, required=True)
        # The source contains one visibly truncated application date (07/04/202).
        # It is deliberately not repaired; an exact valid token is required before
        # a canonical application date is emitted.
        application_date = _valid_date_token(application_raw, required=False)
        primary_label = "Data iscrizione"

    status = _status(note, applicant=applicant)
    source_fields = {
        "sections": section_codes,
        "registered_office_variants": [office] if office else [],
        "secondary_office_variants": [],
        "listing_date_raw_variants": [listing_raw] if listing_raw else [],
        "expiry_date_raw_variants": [expiry_raw] if expiry_raw else [],
        "normalised_listing_date_variants": [listing_date] if listing_date else [],
        "normalised_expiry_date_variants": [expiry_date] if expiry_date else [],
        "date_conflict_fields": [],
        "malformed_date_pairs": [],
    }
    record = _record(
        cfg,
        row_ordinal,
        name=name,
        office=office,
        identifier_raw=identifier_raw,
        activities=activities,
        status=status,
        outcome_raw=note,
        application_date=application_date,
        listing_date=listing_date,
        expiry_date=expiry_date,
        primary_date_label=primary_label,
        source_fields=source_fields,
    )
    return record, applicant


def parse_belluno_combined(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    rows: list[list[str]] = []
    header_count = 0
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _EXPECTED_PAGES:
            raise ValueError(f"Expected {_EXPECTED_PAGES} Belluno pages, found {len(pdf.pages)}")
        first_page_text = _clean(pdf.pages[0].extract_text() or "").upper()
        for code in ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"):
            if f"SEZIONE {code}" not in first_page_text:
                raise ValueError(f"Belluno section legend is missing SEZIONE {code}")
        if "02/09/2026" not in _clean(pdf.pages[-1].extract_text() or "") and "02/09/2026" not in first_page_text:
            # The reference date is source evidence, not inferred from retrieval time.
            # Accept it anywhere in the document, checked below if not on boundary pages.
            document_text = "\n".join(_clean(page.extract_text() or "") for page in pdf.pages)
            if "02/09/2026" not in document_text:
                raise ValueError("Belluno source reference date 02/09/2026 not found in the PDF")

        data_pages = pdf.pages[1:43]
        if len(data_pages) != _EXPECTED_DATA_PAGES:
            raise ValueError(f"Expected {_EXPECTED_DATA_PAGES} Belluno data pages, found {len(data_pages)}")
        for page in data_pages:
            tables = page.extract_tables()
            if len(tables) != 1:
                raise ValueError(f"Expected one Belluno data table on page {page.page_number}, found {len(tables)}")
            page_header_count = 0
            for raw_row in tables[0]:
                row = [_clean(value) for value in raw_row]
                if len(row) != 8:
                    raise ValueError(f"Unexpected Belluno table width on page {page.page_number}: {row!r}")
                if _fold_row(row) == _HEADER:
                    page_header_count += 1
                    header_count += 1
                    continue
                if not any(row):
                    continue
                if not row[0]:
                    raise ValueError(f"Unexpected non-empty Belluno continuation row on page {page.page_number}: {row!r}")
                rows.append(row)
            if page_header_count != 1:
                raise ValueError(
                    f"Expected one exact Belluno header on page {page.page_number}, found {page_header_count}"
                )
        if pdf.pages[43].extract_tables():
            raise ValueError("Belluno trailing page unexpectedly contains a data table")

    if header_count != _EXPECTED_DATA_PAGES:
        raise ValueError(f"Expected {_EXPECTED_DATA_PAGES} Belluno headers, found {header_count}")
    if len(rows) != _EXPECTED_SOURCE_ROWS:
        raise ValueError(f"Expected {_EXPECTED_SOURCE_ROWS} Belluno source rows, found {len(rows)}")

    records: list[dict[str, Any]] = []
    applicant_rows = 0
    malformed_application_dates = 0
    for row in rows:
        raw_application = _clean(row[7])
        record, applicant = _parse_row(row, cfg, len(records) + 1)
        applicant_rows += int(applicant)
        if raw_application and not record["application_date"]:
            malformed_application_dates += 1
        records.append(record)

    diagnostics = {
        "parser": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "source_rows": len(rows),
        "public_records": len(records),
        "applicant_rows": applicant_rows,
        "listed_population_rows": len(rows) - applicant_rows,
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_only": sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records),
        "malformed_application_dates": malformed_application_dates,
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records, diagnostics)


PARSERS = {PARSER_NAME: parse_belluno_combined}
