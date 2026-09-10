from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import (
    ParsedBatch,
    _clean,
    _iso_date,
    _record,
)

_LISTED_PAGE_COUNT = 63
_APPLICANT_PAGE_COUNT = 16

_LISTED_BANDS = {
    "name": (57.0, 188.5),
    "office": (188.5, 276.5),
    "secondary": (276.5, 319.1),
    "activity": (319.1, 418.2),
    "identifier": (418.2, 538.6),
    "listing": (538.6, 616.5),
    "expiry": (616.5, 694.4),
    "update": (694.4, 809.0),
}
_APPLICANT_BANDS = {
    "name": (56.0, 169.7),
    "office": (169.7, 290.1),
    "secondary": (290.1, 387.4),
    "identifier": (387.4, 507.2),
    "activity": (507.2, 613.3),
    "application": (613.3, 698.2),
    "outcome": (698.2, 806.0),
}
_SECTION_CODES = re.compile(r"^\s*\d{1,2}(?:\s*,\s*\d{1,2})*\s*$")


def _row_vertical_bounds(row: Any) -> tuple[float, float] | None:
    cells = [cell for cell in row.cells if cell is not None]
    if not cells:
        return None
    return min(float(cell[1]) for cell in cells), max(float(cell[3]) for cell in cells)


def _text_in_band(
    words: list[dict[str, Any]],
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> str:
    selected: list[dict[str, Any]] = []
    for word in words:
        center_x = (float(word["x0"]) + float(word["x1"])) / 2
        center_y = (float(word["top"]) + float(word["bottom"])) / 2
        if x_min <= center_x < x_max and y_min <= center_y < y_max:
            selected.append(word)
    selected.sort(key=lambda word: (round(float(word["top"]) / 2) * 2, float(word["x0"])))
    return _clean(" ".join(str(word["text"]) for word in selected))


def _main_table(page: Any, *, page_number: int, population: str) -> Any:
    tables = [
        table
        for table in page.find_tables()
        if float(table.bbox[0]) < 65.0 and float(table.bbox[2]) > 800.0
    ]
    if len(tables) != 1:
        raise RuntimeError(
            f"Agrigento {population} page {page_number}: expected one full-width ruled table, got {len(tables)}"
        )
    return tables[0]


def _safe_source_date(raw: str) -> str:
    """Canonicalise only a harmless whitespace-only date variant.

    Source digits and punctuation are never inserted, deleted or rewritten.
    Malformed non-blank values therefore remain uncoded and are retained in
    source_fields for review.
    """
    raw = _clean(raw)
    parsed = _iso_date(raw)
    if parsed:
        return parsed
    compact = re.sub(r"\s+", "", raw)
    if compact != raw and re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", compact):
        return _iso_date(compact)
    return ""


def _section_labels(raw: str) -> list[str]:
    raw = _clean(raw)
    if not raw or not _SECTION_CODES.fullmatch(raw):
        return []
    return [f"Sezione {number}" for number in re.findall(r"\d{1,2}", raw)]


def _values(
    words: list[dict[str, Any]],
    bands: dict[str, tuple[float, float]],
    y_min: float,
    y_max: float,
) -> dict[str, str]:
    return {
        field: _text_in_band(words, x_min, x_max, y_min, y_max)
        for field, (x_min, x_max) in bands.items()
    }


def parse_agrigento_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    records: list[dict[str, Any]] = []
    page_rows: list[int] = []
    continuation_rows = 0
    malformed_listing: list[str] = []
    malformed_expiry: list[str] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGE_COUNT:
            raise RuntimeError(
                f"Agrigento listed layout drift: expected {_LISTED_PAGE_COUNT} pages, got {len(pdf.pages)}"
            )

        for page_number, page in enumerate(pdf.pages, 1):
            if page_number == 1:
                page_rows.append(0)
                continue
            words = page.extract_words(
                use_text_flow=False,
                keep_blank_chars=False,
                x_tolerance=1,
                y_tolerance=2,
            )
            table = _main_table(page, page_number=page_number, population="listed")
            before = len(records)
            for row in table.rows:
                bounds = _row_vertical_bounds(row)
                if bounds is None:
                    continue
                values = _values(words, _LISTED_BANDS, *bounds)
                name = values["name"]
                if not name or "ragione sociale" in name.casefold():
                    continue

                # A logical source observation has an office and activity in
                # the same ruled row. Micro-grid continuation rows can carry
                # a name/date fragment but no office; they are not separate
                # companies and are deliberately not materialised.
                if not values["office"] or not values["activity"]:
                    if any(values[field] for field in ("identifier", "listing", "expiry", "update")):
                        continuation_rows += 1
                    continue

                listing_date = _safe_source_date(values["listing"])
                expiry_date = _safe_source_date(values["expiry"])
                if values["listing"] and not listing_date:
                    malformed_listing.append(values["listing"])
                if values["expiry"] and not expiry_date:
                    malformed_expiry.append(values["expiry"])

                source_fields: dict[str, Any] = {
                    "requested_activities_source": values["activity"],
                    "in_aggiornamento": values["update"],
                }
                if values["listing"] and not listing_date:
                    source_fields["listing_date_raw_variants"] = [values["listing"]]
                if values["expiry"] and not expiry_date:
                    source_fields["expiry_date_raw_variants"] = [values["expiry"]]

                records.append(
                    _record(
                        cfg,
                        len(records) + 1,
                        name=name,
                        office=values["office"],
                        secondary=values["secondary"],
                        identifier_raw=values["identifier"],
                        activities=_section_labels(values["activity"]),
                        status="listed",
                        listing_date=listing_date,
                        expiry_date=expiry_date,
                        primary_date_label="Data iscrizione" if listing_date else "",
                        source_fields=source_fields,
                    )
                )
            page_rows.append(len(records) - before)

    diagnostics = {
        "parser": "agrigento_positioned_listed",
        "public_records": len(records),
        "page_rows": page_rows,
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "identifier_raw_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "update_rows": sum(bool(record["source_fields"].get("in_aggiornamento")) for record in records),
        "continuation_rows_skipped": continuation_rows,
        "malformed_listing_dates": malformed_listing,
        "malformed_expiry_dates": malformed_expiry,
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records, diagnostics)


def parse_agrigento_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    records: list[dict[str, Any]] = []
    page_rows: list[int] = []
    continuation_rows = 0
    malformed_application: list[str] = []
    outcome_variants: Counter[str] = Counter()

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGE_COUNT:
            raise RuntimeError(
                f"Agrigento applicants layout drift: expected {_APPLICANT_PAGE_COUNT} pages, got {len(pdf.pages)}"
            )

        for page_number, page in enumerate(pdf.pages, 1):
            if page_number == 1:
                page_rows.append(0)
                continue
            words = page.extract_words(
                use_text_flow=False,
                keep_blank_chars=False,
                x_tolerance=1,
                y_tolerance=2,
            )
            table = _main_table(page, page_number=page_number, population="applicants")
            before = len(records)
            for row in table.rows:
                bounds = _row_vertical_bounds(row)
                if bounds is None:
                    continue
                values = _values(words, _APPLICANT_BANDS, *bounds)
                name = values["name"]
                if not name or "ragione sociale" in name.casefold():
                    continue

                # The PDF occasionally subdivides only the name cell into
                # several physical grid rows. Office is present on the
                # logical observation row and absent on those continuations.
                if not values["office"]:
                    if any(values[field] for field in ("identifier", "activity", "application", "outcome")):
                        continuation_rows += 1
                    continue

                outcome = values["outcome"]
                if "istruttoria" not in outcome.casefold():
                    raise RuntimeError(
                        f"Agrigento applicant row has an unreviewed outcome: {outcome!r}"
                    )
                outcome_variants[outcome] += 1

                application_date = _safe_source_date(values["application"])
                if values["application"] and not application_date:
                    malformed_application.append(values["application"])

                source_fields: dict[str, Any] = {
                    "requested_activities_source": values["activity"],
                }
                if values["application"] and not application_date:
                    source_fields["application_date_raw_variants"] = [values["application"]]

                records.append(
                    _record(
                        cfg,
                        len(records) + 1,
                        name=name,
                        office=values["office"],
                        secondary=values["secondary"],
                        identifier_raw=values["identifier"],
                        activities=_section_labels(values["activity"]),
                        status="pending",
                        outcome_raw=outcome,
                        application_date=application_date,
                        primary_date_label="Data presentazione istanza" if application_date else "",
                        source_fields=source_fields,
                    )
                )
            page_rows.append(len(records) - before)

    diagnostics = {
        "parser": "agrigento_positioned_applicants",
        "public_records": len(records),
        "page_rows": page_rows,
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "outcome_counts": dict(outcome_variants),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "identifier_raw_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "continuation_rows_skipped": continuation_rows,
        "malformed_application_dates": malformed_application,
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records, diagnostics)


PARSERS = {
    "agrigento_listed": parse_agrigento_listed,
    "agrigento_applicants": parse_agrigento_applicants,
}
