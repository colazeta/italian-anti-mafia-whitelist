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


def _expect(row: list[str], *, page: int, row_number: int, cells: dict[int, str]) -> None:
    for index, expected in cells.items():
        if row[index] != expected:
            raise RuntimeError(
                f"Ancona reviewed extraction repair no longer matches page {page} row {row_number} "
                f"cell {index}: expected {expected!r}, got {row[index]!r}"
            )


def _repair_reviewed_extraction(page_number: int, rows: list[list[str]]) -> list[list[str]]:
    """Repair a small set of byte-pinned PDF table-boundary extraction errors.

    The official PDF has 577 logical source rows. pdfplumber preserves that row
    denominator, but at a few vertical boundaries it assigns name/office/identifier
    text to a neighbouring cell while page text still exposes the complete rows.
    Each repair is anchored to exact observed cells and therefore fails closed if
    the source layout changes. No source status, section or date is invented.
    """
    out = [list(row) for row in rows]

    if page_number == 2:
        r21, r22, r23 = out[20], out[21], out[22]
        _expect(
            r21,
            page=2,
            row_number=21,
            cells={
                0: "ARTITALY SRLS ASSCOOP - SOCIETA' COOPERATIVA SOCIALE IMPRESA SOCIALE AT APPLICAZIONI SRLS",
                1: "via Podesti n. 71 - SENIGALLIA",
                3: "02780960429",
                8: "12/06/2026",
            },
        )
        _expect(r22, page=2, row_number=22, cells={0: "", 1: "Via 1 Maggio 150/A - ANCONA", 3: "00733460422", 8: "11/05/2026"})
        _expect(r23, page=2, row_number=23, cells={0: "", 1: "Via Mario Saveri 18 - JESI", 3: "02809800424", 8: "24/02/2026"})
        r21[0] = "ARTITALY SRLS"
        r22[0] = "ASSCOOP - SOCIETA' COOPERATIVA SOCIALE IMPRESA SOCIALE"
        r23[0] = "AT APPLICAZIONI SRLS"

    if page_number == 3:
        row = out[24]
        _expect(row, page=3, row_number=25, cells={0: "", 1: "", 3: "01479620427", 4: "21/02/2025", 8: "16/02/2026"})
        row[0] = "BARBINI EMILIA SNC DI FABBRETTI ROBERTO E C"
        row[1] = "Via 2 Giugno, 15 - CASTELPLANIO"

    if page_number == 8:
        row = out[22]
        _expect(row, page=8, row_number=23, cells={0: "", 1: "", 3: "07898760637", 4: "17/10/2025", 5: "16/10/2026"})
        row[0] = "EDIL QUARANTA SRL"
        row[1] = "Via Montebello n. 71 - ANCONA"

    if page_number == 13:
        row = out[24]
        _expect(row, page=13, row_number=25, cells={0: "", 1: "", 3: "02272920428", 4: "08/07/2026", 5: "07/07/2027"})
        row[0] = "IDROGAS SRL"
        row[1] = "Via Valdicerro Sotto, 2 - LORETO"

    if page_number == 21:
        r8, r9, r10, r26 = out[7], out[8], out[9], out[25]
        _expect(
            r8,
            page=21,
            row_number=8,
            cells={0: "SIRIO COSTRUZIONI SRL", 1: "", 3: "00715570420 03033810429 02566930422", 4: "28/03/2025", 7: "Richiesto rinnovo"},
        )
        _expect(r9, page=21, row_number=9, cells={0: "SM SRL", 1: "", 3: "", 6: "VI", 8: "20/05/2026"})
        _expect(r10, page=21, row_number=10, cells={0: "", 1: "", 3: "", 4: "27/08/2026", 5: "25/08/2027", 6: "II"})
        _expect(r26, page=21, row_number=26, cells={0: "", 1: "Via Veneto 8/10/12 - FABRIANO", 3: "02557530421", 8: "11/08/2025"})
        r8[1] = "Via Molini I, 18 - SIROLO"
        r8[3] = "00715570420"
        r9[1] = "via Manzoni n. 65 -OSIMO"
        r9[3] = "03033810429"
        r10[0] = "SMART BUILDING DESIGN SRL"
        r10[1] = "Via Giancarlo Mascino n.3/F - ANCONA"
        r10[3] = "02566930422"
        r26[0] = "TAVERNA DA IVO SRL"

    return out


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
    if not name:
        raise RuntimeError(f"Ancona row {ordinal}: company name is blank after reviewed extraction repair")
    if not identifier_raw:
        raise RuntimeError(f"Ancona row {ordinal}: source identifier field is blank after reviewed extraction repair")

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
    rows: list[list[str]] = []
    page_rows: list[int] = []
    reference_markers = 0
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _EXPECTED_PAGES:
            raise RuntimeError(f"Ancona source layout changed: expected {_EXPECTED_PAGES} pages, got {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, 1):
            text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            reference_markers += text.count(_REFERENCE_MARKER)
            table = _company_table(page, page_number)
            data_rows = [list(map(_clean, row)) for row in table[1:] if any(_clean(cell) for cell in row)]
            page_rows.append(len(data_rows))
            rows.extend(_repair_reviewed_extraction(page_number, data_rows))

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
