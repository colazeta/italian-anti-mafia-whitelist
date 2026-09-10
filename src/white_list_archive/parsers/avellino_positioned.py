from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import (
    ParsedBatch,
    _activities,
    _clean,
    _iso_date,
    _record,
)

_DATE = re.compile(r"^\d{1,2}[./-]\d{1,2}[./-]\d{4}$")


@dataclass(frozen=True)
class _Layout:
    parser_name: str
    page_count: int
    anchor_x_min: float
    anchor_x_max: float
    columns: tuple[tuple[str, float, float], ...]
    primary_date_label: str


_LISTED = _Layout(
    parser_name="avellino_listed",
    page_count=9,
    anchor_x_min=600.0,
    anchor_x_max=675.0,
    columns=(
        ("name", 100.0, 260.0),
        ("identifier", 260.0, 320.0),
        ("office", 320.0, 435.0),
        ("activities", 435.0, 555.0),
        ("update", 555.0, 610.0),
        ("date", 610.0, 680.0),
        ("notes", 680.0, 850.0),
    ),
    primary_date_label="Data scadenza",
)

_APPLICANTS = _Layout(
    parser_name="avellino_applicants",
    page_count=5,
    anchor_x_min=680.0,
    anchor_x_max=780.0,
    columns=(
        ("name", 100.0, 278.0),
        ("identifier", 278.0, 348.0),
        ("office", 348.0, 484.0),
        ("activities", 484.0, 687.0),
        ("date", 687.0, 850.0),
    ),
    primary_date_label="Data presentazione istanza",
)


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", _clean(value))


def _line_groups(words: list[dict[str, Any]], tolerance: float = 4.0) -> list[list[dict[str, Any]]]:
    groups: dict[int, list[dict[str, Any]]] = {}
    for word in words:
        key = round(float(word["top"]) / tolerance)
        groups.setdefault(key, []).append(word)
    return [sorted(group, key=lambda item: float(item["x0"])) for _, group in sorted(groups.items())]


def _date_spans(words: list[dict[str, Any]]) -> list[dict[str, float | str]]:
    candidates: list[dict[str, float | str | int]] = []
    for line in _line_groups(words):
        for start in range(len(line)):
            joined = ""
            for end in range(start, min(len(line), start + 7)):
                joined += _compact(str(line[end]["text"]))
                if _DATE.fullmatch(joined):
                    segment = line[start : end + 1]
                    candidates.append(
                        {
                            "value": joined,
                            "x0": float(segment[0]["x0"]),
                            "x1": float(segment[-1]["x1"]),
                            "top": min(float(word["top"]) for word in segment),
                            "bottom": max(float(word["bottom"]) for word in segment),
                            "start": start,
                            "end": end,
                        }
                    )
                    break
                if len(joined) > 12:
                    break

    # A multi-word date can generate overlapping candidates on the same visual line.
    # Keep only the first non-overlapping span. The source hash and expected row
    # count provide the outer fail-closed boundary.
    chosen: list[dict[str, float | str]] = []
    for item in sorted(candidates, key=lambda value: (float(value["top"]), float(value["x0"]))):
        if chosen:
            previous = chosen[-1]
            overlaps = (
                abs(float(item["top"]) - float(previous["top"])) < 3.0
                and float(item["x0"]) < float(previous["x1"])
            )
            if overlaps:
                continue
        chosen.append({key: item[key] for key in ("value", "x0", "x1", "top", "bottom")})
    return chosen


def _text_in_band(
    words: list[dict[str, Any]],
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> str:
    selected: list[dict[str, Any]] = []
    for word in words:
        centre_x = (float(word["x0"]) + float(word["x1"])) / 2.0
        centre_y = (float(word["top"]) + float(word["bottom"])) / 2.0
        if x_min <= centre_x < x_max and y_min <= centre_y < y_max:
            selected.append(word)
    selected.sort(key=lambda word: (round(float(word["top"]) / 2.0) * 2.0, float(word["x0"])))
    return _clean(" ".join(_clean(word["text"]) for word in selected))


def _row_bounds(anchors: list[dict[str, float | str]], page_height: float) -> list[tuple[float, float]]:
    centres = [(float(anchor["top"]) + float(anchor["bottom"])) / 2.0 for anchor in anchors]
    bounds: list[tuple[float, float]] = []
    for index, centre in enumerate(centres):
        if index:
            top = (centres[index - 1] + centre) / 2.0
        elif len(centres) > 1:
            top = max(0.0, centre - (centres[1] - centre) / 2.0)
        else:
            top = max(0.0, centre - 8.0)

        if index + 1 < len(centres):
            bottom = (centre + centres[index + 1]) / 2.0
        elif len(centres) > 1:
            bottom = min(page_height, centre + (centre - centres[index - 1]) / 2.0)
        else:
            bottom = min(page_height, centre + 8.0)
        if bottom <= top:
            raise RuntimeError("Avellino parser encountered an invalid positioned-row boundary")
        bounds.append((top, bottom))
    return bounds


def _positioned_rows(path: Path, layout: _Layout) -> tuple[list[dict[str, str]], list[int]]:
    rows: list[dict[str, str]] = []
    page_rows: list[int] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != layout.page_count:
            raise RuntimeError(
                f"{layout.parser_name}: expected {layout.page_count} pages for the approved source layout, got {len(pdf.pages)}"
            )
        for page_number, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(
                use_text_flow=False,
                keep_blank_chars=False,
                x_tolerance=2,
                y_tolerance=3,
            )
            anchors = [
                span
                for span in _date_spans(words)
                if layout.anchor_x_min <= float(span["x0"]) < layout.anchor_x_max
            ]
            anchors.sort(key=lambda item: float(item["top"]))
            for first, second in zip(anchors, anchors[1:]):
                if float(second["top"]) - float(first["top"]) < 4.0:
                    raise RuntimeError(f"{layout.parser_name}: ambiguous primary-date anchors on page {page_number}")
            page_rows.append(len(anchors))
            for anchor, (y_min, y_max) in zip(anchors, _row_bounds(anchors, float(page.height))):
                cells = {
                    name: _text_in_band(words, x_min, x_max, y_min, y_max)
                    for name, x_min, x_max in layout.columns
                }
                # The anchor itself is the authoritative source date. This avoids
                # accidentally absorbing a separate date from the free-text notes
                # column while retaining the source row as positioned evidence.
                cells["date"] = str(anchor["value"])
                cells["source_page"] = str(page_number)
                rows.append(cells)
    return rows, page_rows


def _validate_cells(rows: list[dict[str, str]], layout: _Layout) -> None:
    essential = ("name", "identifier", "office", "activities", "date")
    missing = {field: sum(not _clean(row.get(field, "")) for row in rows) for field in essential}
    if any(missing.values()):
        raise RuntimeError(f"{layout.parser_name}: incomplete positioned source rows: {missing}")
    invalid_dates = sum(not _iso_date(row["date"]) for row in rows)
    if invalid_dates:
        raise RuntimeError(f"{layout.parser_name}: {invalid_dates} primary source dates are invalid")


def parse_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    rows, page_rows = _positioned_rows(path, _LISTED)
    _validate_cells(rows, _LISTED)
    records: list[dict[str, Any]] = []
    for ordinal, row in enumerate(rows, start=1):
        record = _record(
            cfg,
            ordinal,
            name=row["name"],
            office=row["office"],
            identifier_raw=row["identifier"],
            activities=_activities(row["activities"]),
            status="listed",
            outcome_raw=row["update"],
            expiry_date=row["date"],
            primary_date_label="",
            source_fields={
                "update_registration_raw": row["update"],
                "notes_raw": row["notes"],
                "source_page": int(row["source_page"]),
            },
        )
        record["primary_date"] = record["observed_expiry_date"]
        record["primary_date_label"] = _LISTED.primary_date_label
        records.append(record)

    diagnostics = {
        "parser": _LISTED.parser_name,
        "page_rows": page_rows,
        "positioned_rows": len(rows),
        "public_records": len(records),
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "name_coverage": sum(bool(record["name"]) for record in records),
        "office_coverage": sum(bool(record["registered_office"]) for record in records),
        "activities_coverage": sum(bool(record["requested_activities"]) for record in records),
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records, diagnostics)


def parse_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    rows, page_rows = _positioned_rows(path, _APPLICANTS)
    _validate_cells(rows, _APPLICANTS)
    records: list[dict[str, Any]] = []
    for ordinal, row in enumerate(rows, start=1):
        records.append(
            _record(
                cfg,
                ordinal,
                name=row["name"],
                office=row["office"],
                identifier_raw=row["identifier"],
                activities=_activities(row["activities"]),
                status="pending",
                application_date=row["date"],
                primary_date_label=_APPLICANTS.primary_date_label,
                source_fields={"source_page": int(row["source_page"])},
            )
        )

    diagnostics = {
        "parser": _APPLICANTS.parser_name,
        "page_rows": page_rows,
        "positioned_rows": len(rows),
        "public_records": len(records),
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "name_coverage": sum(bool(record["name"]) for record in records),
        "office_coverage": sum(bool(record["registered_office"]) for record in records),
        "activities_coverage": sum(bool(record["requested_activities"]) for record in records),
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records, diagnostics)


PARSERS = {
    "avellino_listed": parse_listed,
    "avellino_applicants": parse_applicants,
}
