from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_NAME = "ancona_combined"
PARSER_VERSION = "1"
_EXPECTED_PAGES = 23
_EXPECTED_ROWS = 577
_EXPECTED_PAGE_ROWS = [14, 26, 26, 25, 26, 26, 26, 26, 26, 26, 25, 25, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 20]
_REFERENCE_MARKER = "Agg. al 07/09/2026"
_HEADER = (
    "ragione sociale",
    "sede legale",
    "sede secondaria con rappresentanza stabile in italia",
    "codice fiscale / partita iva",
    "data iscrizione",
    "data scadenza iscrizione",
    "sezioni",
    "aggiornamento in corso",
    "data presentazione istanza",
)
_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_SECTION = re.compile(r"(?<![A-Z])(VIII|VII|III|VI|IV|IX|II|V|X|I)(?![A-Z])", re.I)


def _source_date(raw: str, *, field: str, ordinal: int) -> str:
    value = _clean(raw)
    if not value:
        return ""
    match = _DATE.fullmatch(value)
    if not match:
        raise RuntimeError(f"Ancona row {ordinal}: unsupported {field} source date {raw!r}")
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError as exc:
        raise RuntimeError(f"Ancona row {ordinal}: invalid {field} source date {raw!r}") from exc


def _sections(raw: str) -> list[str]:
    value = _clean(raw).upper()
    if not value:
        return []
    codes: list[str] = []
    for match in _SECTION.finditer(value):
        code = match.group(1).upper()
        if code not in codes:
            codes.append(code)
    residue = _SECTION.sub("", value)
    residue = re.sub(r"[\s\-–—·;,]+", "", residue)
    if residue:
        raise RuntimeError(f"Ancona source contains unsupported section-cell content: {raw!r}")
    return [f"Sezione {code}" for code in codes]


def _identifier_values(raw: str) -> list[str]:
    values: list[str] = []
    for part in re.split(r"[/;,]+", _clean(raw)):
        token = re.sub(r"[^A-Za-z0-9]", "", part).upper()
        if ((token.isdigit() and len(token) == 11) or (len(token) == 16 and token.isalnum())) and token not in values:
            values.append(token)
    return values


def _company_table(page: pdfplumber.page.Page, page_number: int) -> list[list[Any]]:
    matches: list[list[list[Any]]] = []
    for table in page.extract_tables():
        if not table or not table[0]:
            continue
        header = tuple(_clean(value).casefold() for value in table[0])
        if header == _HEADER:
            matches.append(table)
    if len(matches) != 1:
        raise RuntimeError(f"Ancona page {page_number}: expected one exact company table, found {len(matches)}")
    return matches[0]


def _status(*, listing_raw: str, expiry_raw: str, update_raw: str, application_raw: str, ordinal: int) -> str:
    if bool(listing_raw) != bool(expiry_raw):
        raise RuntimeError(f"Ancona row {ordinal}: listing/expiry source-date pair is structurally incomplete")
    if update_raw:
        if update_raw == "Richiesto rinnovo":
            return "renewal_update_in_progress"
        # One current source row contains punctuation in this field. Preserve it,
        # but never promote punctuation to an update/renewal claim.
        return "other_or_unknown"
    if listing_raw:
        # A source listing-date pair is direct positive evidence of enrolment.
        # Some rows also retain an application date; that date is preserved but
        # does not by itself negate the listing evidence or imply a pending case.
        return "listed"
    if application_raw:
        # The official publication is explicitly the combined list of enrolled
        # companies and companies requesting enrolment. In a row without any
        # listing-date pair, the dedicated application-date field is the positive
        # structural signal for the applicant population.
        return "pending"
    return "other_or_unknown"


def _record_from_cells(row: list[Any], cfg: dict[str, Any], ordinal: int) -> dict[str, Any]:
    if len(row) != 9:
        raise RuntimeError(f"Ancona row {ordinal}: expected exactly 9 cells, got {len(row)}")
    name, office, secondary, identifier_raw, listing_raw, expiry_raw, sections_raw, update_raw, application_raw = map(_clean, row)

    listing_date = _source_date(listing_raw, field="listing", ordinal=ordinal)
    expiry_date = _source_date(expiry_raw, field="expiry", ordinal=ordinal)
    application_date = _source_date(application_raw, field="application", ordinal=ordinal)
    status = _status(
        listing_raw=listing_raw,
        expiry_raw=expiry_raw,
        update_raw=update_raw,
        application_raw=application_raw,
        ordinal=ordinal,
    )
    activities = _sections(sections_raw)
    source_fields = {
        "sections": [item.removeprefix("Sezione ") for item in activities],
        "registered_office_variants": [office] if office else [],
        "secondary_office_variants": [secondary] if secondary else [],
        "listing_date_raw_variants": [listing_raw] if listing_raw else [],
        "application_date_raw_variants": [application_raw] if application_raw else [],
        "expiry_date_raw_variants": [expiry_raw] if expiry_raw else [],
        "normalised_listing_date_variants": [listing_date] if listing_date else [],
        "normalised_expiry_date_variants": [expiry_date] if expiry_date else [],
        "date_conflict_fields": [],
        "malformed_date_pairs": [],
    }
    if update_raw:
        source_fields["in_aggiornamento"] = update_raw

    primary_label = "Data iscrizione" if listing_date else ("Data presentazione istanza" if application_date else "")
    record = _record(
        cfg,
        ordinal,
        name=name,
        office=office,
        secondary=secondary,
        identifier_raw=identifier_raw,
        activities=activities,
        status=status,
        outcome_raw=update_raw,
        application_date=application_date,
        listing_date=listing_date,
        expiry_date=expiry_date,
        primary_date_label=primary_label,
        source_fields=source_fields,
    )
    record["identifiers"] = _identifier_values(identifier_raw)
    return record


def parse_ancona_combined(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    rows: list[list[Any]] = []
    page_rows: list[int] = []
    reference_markers = 0
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _EXPECTED_PAGES:
            raise RuntimeError(f"Ancona source layout changed: expected {_EXPECTED_PAGES} pages, got {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, 1):
            text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            reference_markers += text.count(_REFERENCE_MARKER)
            table = _company_table(page, page_number)
            data_rows = [row for row in table[1:] if any(_clean(cell) for cell in row)]
            page_rows.append(len(data_rows))
            rows.extend(data_rows)

    if page_rows != _EXPECTED_PAGE_ROWS:
        raise RuntimeError(f"Ancona page-row denominators changed: expected {_EXPECTED_PAGE_ROWS}, got {page_rows}")
    if len(rows) != _EXPECTED_ROWS:
        raise RuntimeError(f"Ancona source layout changed: expected {_EXPECTED_ROWS} rows, got {len(rows)}")
    if reference_markers != _EXPECTED_PAGES:
        raise RuntimeError(f"Ancona reference-date marker drift: expected {_EXPECTED_PAGES}, got {reference_markers}")

    records = [_record_from_cells(row, cfg, ordinal) for ordinal, row in enumerate(rows, 1)]
    statuses = Counter(record["source_status"] for record in records)
    expected_statuses = Counter({
        "listed": 331,
        "pending": 145,
        "renewal_update_in_progress": 100,
        "other_or_unknown": 1,
    })
    if statuses != expected_statuses:
        raise RuntimeError(f"Ancona reviewed status denominator drift: expected {dict(expected_statuses)}, got {dict(statuses)}")

    diagnostics = {
        "parser": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "pages": _EXPECTED_PAGES,
        "page_rows": page_rows,
        "source_rows": len(rows),
        "public_records": len(records),
        "status_counts": dict(statuses),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "blank_name_rows": sum(not bool(record["name"]) for record in records),
        "blank_office_rows": sum(not bool(record["registered_office"]) for record in records),
        "blank_section_rows": sum(not bool(record["requested_activities"]) for record in records),
        "application_date_rows": sum(bool(record["application_date"]) for record in records),
        "listing_date_rows": sum(bool(record["observed_listing_date"]) for record in records),
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records, diagnostics)


PARSERS = {PARSER_NAME: parse_ancona_combined}
