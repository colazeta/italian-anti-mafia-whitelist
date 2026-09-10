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


# Column boundaries are the stable ruling-line positions of the byte-pinned
# 31 August 2026 Benevento PDFs. The parser intentionally fails closed if a
# future edition changes page count or cannot produce the approved row count.
_LISTED = _Layout(
    parser_name="benevento_listed",
    page_count=64,
    anchor_x_min=436.0,
    anchor_x_max=491.0,
    columns=(
        ("name", 25.0, 146.36),
        ("office", 146.36, 287.36),
        ("secondary", 287.36, 349.79),
        ("identifier", 349.79, 436.79),
        ("listing_date", 436.79, 490.81),
        ("expiry", 490.81, 544.81),
        ("update", 544.81, 639.40),
        ("activities", 639.40, 773.22),
    ),
    primary_date_label="Data iscrizione",
)

_APPLICANTS = _Layout(
    parser_name="benevento_applicants",
    page_count=16,
    anchor_x_min=724.0,
    anchor_x_max=778.3,
    columns=(
        ("name", 17.40, 233.30),
        ("office", 233.30, 406.25),
        ("identifier", 406.25, 476.59),
        ("activities", 476.59, 724.06),
        ("application_date", 724.06, 778.30),
        ("notes", 778.30, 820.08),
    ),
    primary_date_label="Data istanza",
)


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", _clean(value))


def _line_groups(words: list[dict[str, Any]], tolerance: float = 3.0) -> list[list[dict[str, Any]]]:
    groups: dict[int, list[dict[str, Any]]] = {}
    for word in words:
        groups.setdefault(round(float(word["top"]) / tolerance), []).append(word)
    return [sorted(group, key=lambda item: float(item["x0"])) for _, group in sorted(groups.items())]


def _date_spans(words: list[dict[str, Any]]) -> list[dict[str, float | str]]:
    """Recover visually contiguous source dates without changing any digit."""
    candidates: list[dict[str, float | str]] = []
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
                        }
                    )
                    break
                if len(joined) > 12:
                    break

    chosen: list[dict[str, float | str]] = []
    for item in sorted(candidates, key=lambda value: (float(value["top"]), float(value["x0"]))):
        if any(
            abs(float(item["top"]) - float(previous["top"])) < 2.0
            and float(item["x0"]) < float(previous["x1"])
            and float(item["x1"]) > float(previous["x0"])
            for previous in chosen[-3:]
        ):
            continue
        chosen.append(item)
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


def _header_bottom(table: Any) -> float:
    extracted = table.extract()
    for row, cells in zip(table.rows, extracted):
        folded = " ".join(_clean(cell).casefold() for cell in cells)
        if "ragione" in folded and "data" in folded:
            bottoms = [float(cell[3]) for cell in row.cells if cell is not None]
            if bottoms:
                return max(bottoms)
    return float(table.bbox[1])


def _row_bounds(
    anchors: list[dict[str, float | str]],
    table_top: float,
    table_bottom: float,
) -> list[tuple[float, float]]:
    centres = [(float(anchor["top"]) + float(anchor["bottom"])) / 2.0 for anchor in anchors]
    bounds: list[tuple[float, float]] = []
    for index, centre in enumerate(centres):
        top = table_top if index == 0 else (centres[index - 1] + centre) / 2.0
        bottom = table_bottom if index + 1 == len(centres) else (centre + centres[index + 1]) / 2.0
        if bottom <= top:
            raise RuntimeError("Benevento parser encountered an invalid positioned-row boundary")
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
                x_tolerance=1,
                y_tolerance=2,
            )
            anchors = [
                span
                for span in _date_spans(words)
                if layout.anchor_x_min <= float(span["x0"]) < layout.anchor_x_max
            ]
            anchors.sort(key=lambda item: (float(item["top"]), float(item["x0"])))

            page_count = 0
            matched_anchors: set[int] = set()
            tables = page.find_tables()
            for table in tables:
                table_anchors = [
                    (index, anchor)
                    for index, anchor in enumerate(anchors)
                    if float(table.bbox[0]) <= float(anchor["x0"]) <= float(table.bbox[2])
                    and float(table.bbox[1]) <= (float(anchor["top"]) + float(anchor["bottom"])) / 2.0 <= float(table.bbox[3])
                ]
                if not table_anchors:
                    continue
                for index, _anchor in table_anchors:
                    if index in matched_anchors:
                        raise RuntimeError(f"{layout.parser_name}: date anchor belongs to multiple tables on page {page_number}")
                    matched_anchors.add(index)
                source_anchors = [anchor for _index, anchor in table_anchors]
                for first, second in zip(source_anchors, source_anchors[1:]):
                    if float(second["top"]) - float(first["top"]) < 5.0:
                        raise RuntimeError(f"{layout.parser_name}: ambiguous primary-date anchors on page {page_number}")
                top = _header_bottom(table)
                for anchor, (y_min, y_max) in zip(
                    source_anchors,
                    _row_bounds(source_anchors, top, float(table.bbox[3])),
                ):
                    cells = {
                        name: _text_in_band(words, x_min, x_max, y_min, y_max)
                        for name, x_min, x_max in layout.columns
                    }
                    source_date = str(anchor["value"])
                    if layout is _LISTED:
                        cells["listing_date"] = source_date
                    else:
                        cells["application_date"] = source_date
                    cells["source_page"] = str(page_number)
                    rows.append(cells)
                    page_count += 1
            # Date-like document metadata outside the ruled source table are
            # deliberately ignored. Only anchors geometrically inside a table
            # can establish a company observation.
            page_rows.append(page_count)
    return rows, page_rows


def _validate_identity(rows: list[dict[str, str]], layout: _Layout) -> None:
    # Source identifiers can legitimately be absent or malformed. The parser
    # preserves the raw cell and never reconstructs an identifier. Name and
    # registered office are the fail-closed row-identity requirements here.
    essential = ("name", "office")
    missing = {field: sum(not _clean(row.get(field, "")) for row in rows) for field in essential}
    if any(missing.values()):
        raise RuntimeError(f"{layout.parser_name}: incomplete positioned source rows: {missing}")
    date_field = "listing_date" if layout is _LISTED else "application_date"
    invalid_dates = sum(not _iso_date(row[date_field]) for row in rows)
    if invalid_dates:
        raise RuntimeError(f"{layout.parser_name}: {invalid_dates} primary source dates are invalid")


def parse_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    rows, page_rows = _positioned_rows(path, _LISTED)
    _validate_identity(rows, _LISTED)
    records: list[dict[str, Any]] = []
    malformed_expiry = 0
    for ordinal, row in enumerate(rows, start=1):
        expiry_raw = _clean(row.get("expiry", ""))
        expiry = _iso_date(expiry_raw)
        source_fields: dict[str, Any] = {}
        if expiry_raw and not expiry:
            malformed_expiry += 1
            source_fields["expiry_date_raw_variants"] = [expiry_raw]
        records.append(
            _record(
                cfg,
                ordinal,
                name=row["name"],
                office=row["office"],
                secondary=row.get("secondary", ""),
                identifier_raw=row.get("identifier", ""),
                activities=_activities(row.get("activities", "")),
                status="listed",
                listing_date=row["listing_date"],
                expiry_date=expiry,
                outcome_raw=row.get("update", ""),
                primary_date_label=_LISTED.primary_date_label,
                source_fields=source_fields,
            )
        )

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
        "malformed_expiry_values": malformed_expiry,
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records, diagnostics)


def parse_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    rows, page_rows = _positioned_rows(path, _APPLICANTS)
    _validate_identity(rows, _APPLICANTS)
    records: list[dict[str, Any]] = []
    for ordinal, row in enumerate(rows, start=1):
        records.append(
            _record(
                cfg,
                ordinal,
                name=row["name"],
                office=row["office"],
                identifier_raw=row.get("identifier", ""),
                activities=_activities(row.get("activities", "")),
                status="pending",
                application_date=row["application_date"],
                primary_date_label=_APPLICANTS.primary_date_label,
                source_fields={},
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
    "benevento_listed": parse_listed,
    "benevento_applicants": parse_applicants,
}
