from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import (
    ParsedBatch,
    _clean,
    _identifiers,
    _iso_date,
    _record,
)

_DATE = re.compile(r"^\d{1,2}[./-]\d{1,2}[./-]\d{4}$")
_SECTION = re.compile(r"\bSezione\s+([IVX]+)\b", re.I)
_LISTED_PAGES = 39
_APPLICANT_PAGES = 6
_LISTED_COLUMNS = (
    ("name", 20.0, 145.0),
    ("office", 145.0, 240.0),
    ("secondary", 240.0, 380.0),
    ("identifier", 380.0, 510.0),
    ("listing_date", 510.0, 610.0),
    ("expiry", 610.0, 685.0),
    ("update", 685.0, 825.0),
)


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", _clean(value))


def _line_groups(words: list[dict[str, Any]], tolerance: float = 3.0) -> list[list[dict[str, Any]]]:
    groups: dict[int, list[dict[str, Any]]] = {}
    for word in words:
        groups.setdefault(round(float(word["top"]) / tolerance), []).append(word)
    return [sorted(group, key=lambda item: float(item["x0"])) for _, group in sorted(groups.items())]


def _date_spans(words: list[dict[str, Any]]) -> list[dict[str, float | str]]:
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
                            "kind": "dated",
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


def _row_vertical_bounds(row: Any) -> tuple[float, float]:
    cells = [cell for cell in row.cells if cell is not None]
    if not cells:
        raise RuntimeError("Asti parser encountered a source table row without geometry")
    return min(float(cell[1]) for cell in cells), max(float(cell[3]) for cell in cells)


def _section_info(table: Any) -> tuple[str, str] | None:
    extracted = table.extract()
    intro: list[str] = []
    for row in extracted[:12]:
        folded = " ".join(_clean(cell).casefold() for cell in row if _clean(cell))
        if any(marker in folded for marker in ("sede secondaria", "codice fiscale", "ragione sociale")):
            break
        text = _clean(" ".join(_clean(cell) for cell in row if _clean(cell)))
        if text:
            intro.append(text)
    combined = _clean(" ".join(intro))
    match = _SECTION.search(combined)
    if not match:
        return None
    section = f"Sezione {match.group(1).upper()}"
    activity = _clean(_SECTION.sub("", combined, count=1))
    if not activity:
        raise RuntimeError(f"Asti parser found {section} without an activity description")
    return section, activity


def _header_bottom(table: Any) -> float:
    extracted = table.extract()
    header_bottom: float | None = None
    header_markers = (
        "ragione sociale",
        "sede legale",
        "sede secondaria",
        "rappresentanza stabile",
        "codice fiscale",
        "partita iva",
        "data di iscrizione",
        "o di rinnovo",
        "data scadenza",
        "aggiornamento in corso",
        "italia",
    )
    for row, cells in zip(table.rows, extracted):
        cleaned = [_clean(cell) for cell in cells]
        if any(_DATE.fullmatch(value) for value in cleaned if value):
            break
        folded = " ".join(value.casefold() for value in cleaned if value)
        if any(marker in folded for marker in header_markers):
            bounds = [cell for cell in row.cells if cell is not None]
            if bounds:
                header_bottom = max(float(cell[3]) for cell in bounds)
    if header_bottom is not None:
        return header_bottom
    raise RuntimeError("Asti parser could not establish the ruled table header boundary before the first dated source row")


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
            raise RuntimeError("Asti parser encountered an invalid positioned-row boundary")
        bounds.append((top, bottom))
    return bounds


def _pending_anchors(table: Any, words: list[dict[str, Any]]) -> list[dict[str, float | str]]:
    candidates: list[dict[str, float | str]] = []
    date_spans = _date_spans(words)
    extracted = table.extract()
    for row, cells in zip(table.rows, extracted):
        folded = _clean(" ".join(_clean(cell) for cell in cells)).casefold()
        if "in istruttoria" not in folded:
            continue
        y_min, y_max = _row_vertical_bounds(row)
        name = _text_in_band(words, 20.0, 145.0, y_min, y_max)
        office = _text_in_band(words, 145.0, 240.0, y_min, y_max)
        identifier = _text_in_band(words, 380.0, 510.0, y_min, y_max)
        outcome = _text_in_band(words, 685.0, 825.0, y_min, y_max)
        if not (name and office and identifier and "istruttoria" in outcome.casefold()):
            continue
        if any(
            510.0 <= float(span["x0"]) < 610.0
            and y_min <= (float(span["top"]) + float(span["bottom"])) / 2.0 <= y_max
            for span in date_spans
        ):
            continue
        candidates.append(
            {
                "value": "",
                "x0": 535.0,
                "x1": 535.0,
                "top": y_min,
                "bottom": y_max,
                "kind": "pending",
            }
        )
    return candidates


def _listed_sector_rows(path: Path) -> tuple[list[dict[str, Any]], list[int], int]:
    rows: list[dict[str, Any]] = []
    page_rows: list[int] = []
    pending_exception_count = 0
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGES:
            raise RuntimeError(f"asti_listed: expected {_LISTED_PAGES} pages, got {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False, x_tolerance=1, y_tolerance=2)
            all_dates = _date_spans(words)
            page_count = 0
            matched_date_anchors: set[tuple[float, float]] = set()
            matched_tables = 0
            for table in page.find_tables():
                section_info = _section_info(table)
                if section_info is None:
                    continue
                matched_tables += 1
                section, activity = section_info
                anchors = [
                    span
                    for span in all_dates
                    if 510.0 <= float(span["x0"]) < 610.0
                    and float(table.bbox[1]) <= (float(span["top"]) + float(span["bottom"])) / 2.0 <= float(table.bbox[3])
                ]
                for span in anchors:
                    key = (float(span["top"]), float(span["x0"]))
                    if key in matched_date_anchors:
                        raise RuntimeError(f"asti_listed: a primary-date anchor belongs to multiple tables on page {page_number}")
                    matched_date_anchors.add(key)
                pending = _pending_anchors(table, words)
                pending_exception_count += len(pending)
                anchors.extend(pending)
                anchors.sort(key=lambda item: (float(item["top"]), float(item["x0"])))
                if not anchors:
                    continue
                for first, second in zip(anchors, anchors[1:]):
                    if float(second["top"]) - float(first["top"]) < 4.0:
                        raise RuntimeError(f"asti_listed: ambiguous logical-row anchors on page {page_number}")
                top = _header_bottom(table)
                for anchor, (y_min, y_max) in zip(anchors, _row_bounds(anchors, top, float(table.bbox[3]))):
                    cells = {
                        name: _text_in_band(words, x_min, x_max, y_min, y_max)
                        for name, x_min, x_max in _LISTED_COLUMNS
                    }
                    cells["listing_date"] = str(anchor["value"]) if anchor["kind"] == "dated" else ""
                    cells["source_status"] = "listed" if anchor["kind"] == "dated" else "pending"
                    cells["section"] = section
                    cells["activity"] = activity
                    cells["source_page"] = str(page_number)
                    rows.append(cells)
                    page_count += 1
            if matched_tables == 0:
                raise RuntimeError(f"asti_listed: no section table recognised on page {page_number}")
            primary_on_page = sum(510.0 <= float(span["x0"]) < 610.0 for span in all_dates)
            if len(matched_date_anchors) != primary_on_page:
                raise RuntimeError(
                    f"asti_listed: page {page_number} matched {len(matched_date_anchors)} of {primary_on_page} primary-date anchors"
                )
            page_rows.append(page_count)
    if pending_exception_count != 1:
        raise RuntimeError(
            f"asti_listed: expected the single source-explicit no-date 'In istruttoria' exception, got {pending_exception_count}"
        )
    return rows, page_rows, pending_exception_count


def _identity_key(row: dict[str, Any]) -> tuple[Any, ...]:
    canonical_ids = tuple(_identifiers(row.get("identifier", "")))
    return (
        _clean(row.get("name", "")).casefold(),
        _clean(row.get("office", "")).casefold(),
        _clean(row.get("secondary", "")).casefold(),
        canonical_ids or (_clean(row.get("identifier", "")).casefold(),),
        _iso_date(row.get("listing_date", "")),
        _clean(row.get("expiry", "")).casefold(),
        _clean(row.get("update", "")).casefold(),
        row.get("source_status", ""),
    )


def _group_listed(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    order: list[tuple[Any, ...]] = []
    for row in rows:
        key = _identity_key(row)
        if key not in groups:
            groups[key] = {**row, "sections": [], "activities": []}
            order.append(key)
        group = groups[key]
        if row["section"] not in group["sections"]:
            group["sections"].append(row["section"])
        if row["activity"] not in group["activities"]:
            group["activities"].append(row["activity"])
    return [groups[key] for key in order]


def _validate_listed_sector_rows(rows: list[dict[str, Any]]) -> None:
    missing = {
        field: sum(not _clean(row.get(field, "")) for row in rows)
        for field in ("name", "office", "identifier")
    }
    if any(missing.values()):
        raise RuntimeError(f"asti_listed: incomplete positioned source rows: {missing}")
    invalid_primary = sum(
        row["source_status"] == "listed" and not _iso_date(row.get("listing_date", ""))
        for row in rows
    )
    if invalid_primary:
        raise RuntimeError(f"asti_listed: {invalid_primary} dated rows have an invalid source listing date")
    pending = [row for row in rows if row["source_status"] == "pending"]
    if len(pending) != 1 or "istruttoria" not in _clean(pending[0].get("update", "")).casefold():
        raise RuntimeError("asti_listed: source-explicit pending exception was not preserved exactly")


def parse_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    sector_rows, page_rows, pending_exception_count = _listed_sector_rows(path)
    _validate_listed_sector_rows(sector_rows)
    grouped = _group_listed(sector_rows)
    records: list[dict[str, Any]] = []
    malformed_expiry = 0
    for ordinal, row in enumerate(grouped, start=1):
        expiry_raw = _clean(row.get("expiry", ""))
        expiry = _iso_date(expiry_raw)
        source_fields: dict[str, Any] = {"sections": row["sections"]}
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
                activities=row["activities"],
                status=row["source_status"],
                listing_date=row.get("listing_date", ""),
                expiry_date=expiry,
                outcome_raw=row.get("update", ""),
                primary_date_label="Data iscrizione" if row["source_status"] == "listed" else "",
                source_fields=source_fields,
            )
        )
    diagnostics = {
        "parser": "asti_listed",
        "page_rows": page_rows,
        "sector_rows": len(sector_rows),
        "positioned_rows": len(sector_rows),
        "public_records": len(records),
        "pending_source_exceptions": pending_exception_count,
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


def _activity_parts(raw: str) -> tuple[list[str], list[str]]:
    raw = _clean(raw)
    matches = list(_SECTION.finditer(raw))
    if not matches:
        return ([raw] if raw else []), []
    activities: list[str] = []
    sections: list[str] = []
    for index, match in enumerate(matches):
        sections.append(f"Sezione {match.group(1).upper()}")
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        description = _clean(raw[start:end])
        if not description:
            raise RuntimeError(f"Asti applicant activity is missing after {match.group(0)!r}")
        activities.append(description)
    return activities, sections


def _status_applicant(outcome: str) -> str:
    folded = _clean(outcome).casefold()
    if folded.startswith("iscritta ") or folded.startswith("iscritto "):
        return "listed"
    if folded == "in istruttoria":
        return "pending"
    return "other_or_unknown"


def parse_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    rows: list[list[str]] = []
    page_rows: list[int] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGES:
            raise RuntimeError(f"asti_applicants: expected {_APPLICANT_PAGES} pages, got {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            if len(tables) != 1:
                raise RuntimeError(f"asti_applicants: expected one ruled table on page {page_number}, got {len(tables)}")
            table = tables[0]
            if any(len(row) != 7 for row in table):
                raise RuntimeError(f"asti_applicants: source table width changed on page {page_number}")
            page_count = 0
            for row in table[1:]:
                cleaned = [_clean(cell) for cell in row]
                if not any(cleaned):
                    continue
                if not cleaned[0] or not cleaned[1]:
                    raise RuntimeError(f"asti_applicants: incomplete source identity on page {page_number}: {cleaned!r}")
                rows.append(cleaned)
                page_count += 1
            page_rows.append(page_count)
    records: list[dict[str, Any]] = []
    for ordinal, row in enumerate(rows, start=1):
        name, office, secondary, identifier, activity_raw, application_raw, outcome = row
        application_date = _iso_date(application_raw)
        if application_raw and not application_date:
            raise RuntimeError(f"asti_applicants: invalid application date preserved by source: {application_raw!r}")
        activities, sections = _activity_parts(activity_raw)
        records.append(
            _record(
                cfg,
                ordinal,
                name=name,
                office=office,
                secondary=secondary,
                identifier_raw=identifier,
                activities=activities,
                status=_status_applicant(outcome),
                outcome_raw=outcome,
                application_date=application_date,
                primary_date_label="Data presentazione istanza" if application_date else "",
                source_fields={"sections": sections, "requested_activities_source": activity_raw},
            )
        )
    diagnostics = {
        "parser": "asti_applicants",
        "page_rows": page_rows,
        "public_records": len(records),
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "application_date_coverage": sum(bool(record["application_date"]) for record in records),
        "missing_application_dates": sum(not bool(record["application_date"]) for record in records),
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records, diagnostics)


PARSERS = {
    "asti_listed": parse_listed,
    "asti_applicants": parse_applicants,
}
