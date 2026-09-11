from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-08-27"
_APPLICANT_PAGE_COUNTS = (10,) + (11,) * 54 + (8,)
_LISTED_PAGE_COUNTS = (9,) + (11,) * 129 + (6,)
_APPLICANT_BLANK_APPLICATIONS = {
    (2, 6), (13, 4), (14, 1), (14, 2), (38, 1), (41, 1),
    (42, 2), (42, 9), (46, 1), (48, 9), (49, 7), (53, 5),
}
_APPLICANT_BLANK_ACTIVITY = {(11, 9)}
_LISTED_BLANK_ACTIVITY = {(130, 9)}

# These source rows contain activity text without a recoverable Roman section
# prefix (or, at the two documented coordinates above, no recoverable activity
# text at all). They were reviewed against the byte-pinned PDFs. We preserve the
# raw activity but deliberately do not infer a section from similar text in other
# rows, because at least one description is used under more than one section.
_APPLICANT_UNLABELLED_ACTIVITY = {
    (4, 11), (5, 1), (11, 9), (16, 6), (16, 7), (25, 6),
    (30, 3), (30, 4), (45, 10), (47, 6), (54, 11),
}
_LISTED_UNLABELLED_ACTIVITY = {
    (3, 3), (4, 5), (4, 6), (4, 7), (4, 8), (9, 7), (20, 3),
    (21, 6), (21, 7), (21, 8), (22, 3), (24, 3), (24, 6), (24, 8),
    (25, 2), (34, 9), (34, 10), (34, 11), (49, 7), (49, 8), (49, 9),
    (49, 10), (51, 6), (56, 10), (56, 11), (57, 1), (61, 6), (61, 7),
    (61, 8), (87, 10), (92, 3), (93, 10), (95, 7), (97, 9), (97, 10),
    (97, 11), (98, 1), (98, 2), (98, 3), (102, 3), (104, 3), (104, 4),
    (109, 10), (112, 7), (118, 3), (130, 4), (130, 9),
}

_VALID_IDENTIFIER = re.compile(r"(?<![A-Za-z0-9])(?:\d{11}|[A-Za-z0-9]{16})(?![A-Za-z0-9])", re.I)
_VALID_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_ROMAN = re.compile(r"^(XII|XI|X|IX|VIII|VII|VI|V|IV|III|II|I)\b", re.I)
_ROMAN_NUMBER = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
    "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12,
}
_BANDS = {
    "applicant": {
        "name": (25, 190), "municipality": (190, 285), "street": (285, 390),
        "number": (390, 415), "identifier": (415, 500), "activity": (500, 680),
        "application": (680, 735),
    },
    "listed": {
        "name": (25, 190), "municipality": (190, 285), "street": (285, 390),
        "number": (390, 412), "identifier": (412, 500), "activity": (500, 645),
        "listing": (645, 695), "expiry": (695, 745), "update": (745, 825),
    },
}


def _centre(word: dict[str, Any]) -> float:
    return (float(word["x0"]) + float(word["x1"])) / 2


def _text_band(words: list[dict[str, Any]], x0: float, x1: float, y0: float, y1: float) -> str:
    selected = [
        word for word in words
        if x0 <= _centre(word) < x1 and y0 <= float(word["top"]) < y1
    ]
    selected.sort(key=lambda word: (round(float(word["top"]), 1), float(word["x0"])))
    return _clean(" ".join(str(word["text"]) for word in selected))


def _strict_identifiers(raw: str) -> list[str]:
    values: list[str] = []
    for match in _VALID_IDENTIFIER.finditer(_clean(raw)):
        value = match.group(0).upper()
        if value not in values:
            values.append(value)
    return values


def _strict_date(raw: str, *, allow_blank: bool, source_key: str, page: int, row: int) -> str:
    value = _clean(raw)
    if not value:
        if allow_blank:
            return ""
        raise RuntimeError(f"{source_key}: unexpected blank date at page {page} row {row}")
    match = _VALID_DATE.fullmatch(value)
    if not match:
        raise RuntimeError(f"{source_key}: unreviewed date typography at page {page} row {row}: {value!r}")
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError as exc:
        raise RuntimeError(f"{source_key}: invalid calendar date at page {page} row {row}: {value!r}") from exc


def _section(
    activity: str, *, reviewed_unlabelled: bool, source_key: str, page: int, row: int
) -> tuple[list[str], str]:
    value = _clean(activity)
    match = _ROMAN.match(value) if value else None
    if match:
        roman = match.group(1).upper()
        return [f"Sezione {_ROMAN_NUMBER[roman]}"], value
    if reviewed_unlabelled:
        return [], value
    if not value:
        raise RuntimeError(f"{source_key}: unexpected blank activity at page {page} row {row}")
    raise RuntimeError(f"{source_key}: unreviewed activity prefix at page {page} row {row}: {value!r}")


def _targets(kind: str, page: int, count: int) -> list[float]:
    if kind == "applicant":
        first = 117.3 if page == 1 else 54.2
    else:
        first = 157.7 if page == 1 else 73.0
    return [first + 42.5 * index for index in range(count)]


def _rows(path: Path, *, kind: str, page_counts: tuple[int, ...], source_key: str) -> list[tuple[int, int, dict[str, str]]]:
    bands = _BANDS[kind]
    output: list[tuple[int, int, dict[str, str]]] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != len(page_counts):
            raise RuntimeError(
                f"{source_key}: page-count drift; expected {len(page_counts)}, got {len(pdf.pages)}"
            )
        for page_number, (page, expected_count) in enumerate(zip(pdf.pages, page_counts), 1):
            words = page.extract_words(x_tolerance=1, y_tolerance=2, keep_blank_chars=False, use_text_flow=False)
            targets = _targets(kind, page_number, expected_count)
            for index, y in enumerate(targets):
                y0 = y - 4
                y1 = targets[index + 1] - 4 if index + 1 < len(targets) else min(y + 38, float(page.height) - 15)
                values = {field: _text_band(words, x0, x1, y0, y1) for field, (x0, x1) in bands.items()}
                if not values["name"] or not values["municipality"]:
                    raise RuntimeError(
                        f"{source_key}: unresolved row boundary at page {page_number} row {index + 1}: "
                        f"name={values['name']!r}, municipality={values['municipality']!r}"
                    )
                output.append((page_number, index + 1, values))
    if len(output) != sum(page_counts):
        raise RuntimeError(f"{source_key}: denominator drift: expected {sum(page_counts)}, got {len(output)}")
    return output


def _office(values: dict[str, str]) -> str:
    return _clean(" ".join(part for part in (values["municipality"], values["street"], values["number"]) if part))


def parse_bergamo_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"{cfg['source_key']}: unexpected reference date {cfg.get('reference_date')!r}")
    rows = _rows(path, kind="applicant", page_counts=_APPLICANT_PAGE_COUNTS, source_key=cfg["source_key"])
    records: list[dict[str, Any]] = []
    blank_dates: set[tuple[int, int]] = set()
    blank_activities: set[tuple[int, int]] = set()
    unlabelled_activities: set[tuple[int, int]] = set()
    multi_ids = 0
    for page, row, values in rows:
        coordinate = (page, row)
        application = _strict_date(
            values["application"], allow_blank=coordinate in _APPLICANT_BLANK_APPLICATIONS,
            source_key=cfg["source_key"], page=page, row=row,
        )
        if not values["application"]:
            blank_dates.add(coordinate)
        sections, activity_raw = _section(
            values["activity"], reviewed_unlabelled=coordinate in _APPLICANT_UNLABELLED_ACTIVITY,
            source_key=cfg["source_key"], page=page, row=row,
        )
        if not _ROMAN.match(_clean(values["activity"])):
            unlabelled_activities.add(coordinate)
        if not values["activity"]:
            blank_activities.add(coordinate)
        identifiers = _strict_identifiers(values["identifier"])
        if len(identifiers) > 1:
            multi_ids += 1
        record = _record(
            cfg, len(records) + 1,
            name=values["name"], office=_office(values), identifier_raw=values["identifier"],
            activities=sections, status="pending", application_date=application,
            primary_date_label="Data presentazione istanza" if application else "",
            source_fields={
                "sections": sections,
                "application_date_raw_variants": [values["application"]] if values["application"] else [],
                "requested_activities_source": activity_raw,
            },
        )
        record["identifiers"] = identifiers
        records.append(record)
    if blank_dates != _APPLICANT_BLANK_APPLICATIONS:
        raise RuntimeError(f"{cfg['source_key']}: reviewed blank-date set drift: {sorted(blank_dates)!r}")
    if blank_activities != _APPLICANT_BLANK_ACTIVITY:
        raise RuntimeError(f"{cfg['source_key']}: reviewed blank-activity set drift: {sorted(blank_activities)!r}")
    if unlabelled_activities != _APPLICANT_UNLABELLED_ACTIVITY:
        raise RuntimeError(
            f"{cfg['source_key']}: reviewed unlabelled-activity set drift: {sorted(unlabelled_activities)!r}"
        )
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != 555 or multi_ids != 0:
        raise RuntimeError(
            f"{cfg['source_key']}: identifier boundary drift: coverage={identifier_coverage}, multi={multi_ids}"
        )
    return ParsedBatch(records, {
        "parser": "bergamo_positioned_applicants",
        "public_records": len(records),
        "status_counts": {"pending": len(records)},
        "identifier_coverage": identifier_coverage,
        "multiple_strict_identifier_records": multi_ids,
        "reviewed_blank_application_dates": len(blank_dates),
        "reviewed_unlabelled_activity_rows": len(unlabelled_activities),
        "dropped_date_rows": 0,
    })


def parse_bergamo_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"{cfg['source_key']}: unexpected reference date {cfg.get('reference_date')!r}")
    rows = _rows(path, kind="listed", page_counts=_LISTED_PAGE_COUNTS, source_key=cfg["source_key"])
    records: list[dict[str, Any]] = []
    blank_activities: set[tuple[int, int]] = set()
    unlabelled_activities: set[tuple[int, int]] = set()
    multi_ids = 0
    for page, row, values in rows:
        coordinate = (page, row)
        listing = _strict_date(values["listing"], allow_blank=False, source_key=cfg["source_key"], page=page, row=row)
        expiry = _strict_date(values["expiry"], allow_blank=False, source_key=cfg["source_key"], page=page, row=row)
        update = _strict_date(values["update"], allow_blank=True, source_key=cfg["source_key"], page=page, row=row)
        sections, activity_raw = _section(
            values["activity"], reviewed_unlabelled=coordinate in _LISTED_UNLABELLED_ACTIVITY,
            source_key=cfg["source_key"], page=page, row=row,
        )
        if not _ROMAN.match(_clean(values["activity"])):
            unlabelled_activities.add(coordinate)
        if not values["activity"]:
            blank_activities.add(coordinate)
        identifiers = _strict_identifiers(values["identifier"])
        if len(identifiers) > 1:
            multi_ids += 1
        updating = bool(update)
        record = _record(
            cfg, len(records) + 1,
            name=values["name"], office=_office(values), identifier_raw=values["identifier"],
            activities=sections,
            status="renewal_update_in_progress" if updating else "listed",
            outcome_raw="Aggiornamento in corso" if updating else "",
            listing_date=listing, expiry_date=expiry, primary_date_label="Data iscrizione",
            source_fields={
                "sections": sections,
                "listing_date_raw_variants": [values["listing"]],
                "expiry_date_raw_variants": [values["expiry"]],
                "requested_activities_source": activity_raw,
                "in_aggiornamento": values["update"] if updating else "",
            },
        )
        record["identifiers"] = identifiers
        records.append(record)
    if blank_activities != _LISTED_BLANK_ACTIVITY:
        raise RuntimeError(f"{cfg['source_key']}: reviewed blank-activity set drift: {sorted(blank_activities)!r}")
    if unlabelled_activities != _LISTED_UNLABELLED_ACTIVITY:
        raise RuntimeError(
            f"{cfg['source_key']}: reviewed unlabelled-activity set drift: {sorted(unlabelled_activities)!r}"
        )
    statuses = Counter(record["source_status"] for record in records)
    expected_statuses = Counter({"listed": 626, "renewal_update_in_progress": 808})
    if statuses != expected_statuses:
        raise RuntimeError(f"{cfg['source_key']}: reviewed status denominator drift: {dict(statuses)}")
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != 1425 or multi_ids != 22:
        raise RuntimeError(
            f"{cfg['source_key']}: identifier boundary drift: coverage={identifier_coverage}, multi={multi_ids}"
        )
    return ParsedBatch(records, {
        "parser": "bergamo_positioned_listed",
        "public_records": len(records),
        "status_counts": dict(statuses),
        "identifier_coverage": identifier_coverage,
        "multiple_strict_identifier_records": multi_ids,
        "reviewed_unlabelled_activity_rows": len(unlabelled_activities),
        "dropped_date_rows": 0,
    })


PARSERS = {
    "bergamo_positioned_listed": parse_bergamo_listed,
    "bergamo_positioned_applicants": parse_bergamo_applicants,
}
