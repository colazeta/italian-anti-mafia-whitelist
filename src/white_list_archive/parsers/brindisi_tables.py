from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-09-08"
_LISTED_PAGES = 39
_APPLICANT_PAGES = 3
_EXPECTED_SECTION_MARKERS = (
    (1, "I"), (6, "II"), (9, "III"), (15, "IV"), (18, "V"),
    (24, "VI"), (30, "VII"), (31, "VIII"), (32, "IX"), (34, "X"),
)
_EXPECTED_SECTOR_COUNTS = {
    "I": 109, "II": 55, "III": 137, "IV": 52, "V": 150,
    "VI": 155, "VII": 4, "VIII": 14, "IX": 32, "X": 122,
}
_EXPECTED_SECTOR_ROWS = 830
_EXPECTED_SECTOR_STATUS_COUNTS = Counter({"listed": 718, "renewal_update_in_progress": 112})
_EXPECTED_LISTED_RECORDS = 385
_EXPECTED_LISTED_STATUS_COUNTS = Counter({"listed": 341, "renewal_update_in_progress": 44})
_EXPECTED_APPLICANT_PAGE_COUNTS = (10, 15, 1)
_EXPECTED_APPLICANTS = 26
_EXPECTED_APPLICANT_BLANK_DATES = {(1, 1)}
_REVIEWED_BAD_DATES = {"0S-03-2027", "25-03-20270", "07-04-2027ti"}
_ROMAN_TO_NUMBER = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
}
_SECTION_RE = re.compile(r"\bSezione\s+([IVX]+)\b", re.I)
_STRICT_IDENTIFIER = re.compile(r"(?<![A-Za-z0-9])(?:\d{11}|[A-Za-z0-9]{16})(?![A-Za-z0-9])", re.I)
_IDENTIFIER_LIKE = re.compile(r"(?<!\d)\d{10,11}(?!\d)|(?<![A-Za-z0-9])[A-Za-z0-9]{16}(?![A-Za-z0-9])", re.I)
_VALID_DATE = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$")
_DATE_ANYWHERE = re.compile(r"(?<!\d)\d{1,2}[-/.]\d{1,2}[-/.]\d{4,5}(?!\d)")
_ADMIN_TOKENS = ("ragione sociale", "codice fiscale", "data iscrizione", "data scadenza")


def _strict_identifiers(text: str) -> list[str]:
    values: list[str] = []
    for match in _STRICT_IDENTIFIER.finditer(_clean(text)):
        value = match.group(0).upper()
        if value not in values:
            values.append(value)
    return values


def _parse_source_date(raw: str, *, source_key: str, page: int, row: int, allow_blank: bool = False) -> str:
    value = _clean(raw)
    if not value:
        if allow_blank:
            return ""
        raise RuntimeError(f"{source_key}: unexpected blank date at page {page} row {row}")
    match = _VALID_DATE.fullmatch(value)
    if match:
        day, month, year = map(int, match.groups())
        try:
            return date(year, month, day).isoformat()
        except ValueError as exc:
            raise RuntimeError(f"{source_key}: invalid calendar date at page {page} row {row}: {raw!r}") from exc
    if value in _REVIEWED_BAD_DATES:
        return ""
    raise RuntimeError(f"{source_key}: unreviewed date typography at page {page} row {row}: {raw!r}")


def _semantic_date_key(raw: str, *, source_key: str, page: int, row: int) -> str:
    parsed = _parse_source_date(raw, source_key=source_key, page=page, row=row, allow_blank=True)
    return f"ISO:{parsed}" if parsed else f"RAW:{_clean(raw)}"


def _listed_sector_rows(path: Path, source_key: str) -> tuple[list[dict[str, Any]], tuple[tuple[int, str], ...]]:
    rows: list[dict[str, Any]] = []
    markers: list[tuple[int, str]] = []
    current_section: str | None = None
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGES:
            raise RuntimeError(f"{source_key}: page-count drift; expected {_LISTED_PAGES}, got {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text() or ""
            marker = _SECTION_RE.search(page_text)
            if marker:
                current_section = marker.group(1).upper()
                markers.append((page_number, current_section))
            for table in page.find_tables():
                for row_number, raw in enumerate(table.extract() or [], 1):
                    values = [_clean(cell) for cell in raw]
                    if len(values) < 7 or not any(values):
                        continue
                    folded = " | ".join(values).casefold()
                    if any(token in folded for token in _ADMIN_TOKENS):
                        continue
                    name = values[0]
                    listing_raw = values[4]
                    if not name or not _VALID_DATE.fullmatch(listing_raw):
                        continue
                    if current_section is None:
                        raise RuntimeError(f"{source_key}: missing section at page {page_number} row {row_number}")
                    rows.append({
                        "page": page_number,
                        "row": row_number,
                        "section": current_section,
                        "name": name,
                        "office": values[1],
                        "secondary_office": values[2],
                        "identifier_raw": values[3],
                        "listing_raw": listing_raw,
                        "expiry_raw": values[5],
                        "note_raw": values[6],
                    })
    return rows, tuple(markers)


def parse_brindisi_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"{cfg['source_key']}: unexpected reference date {cfg.get('reference_date')!r}")
    source_rows, markers = _listed_sector_rows(path, cfg["source_key"])
    if markers != _EXPECTED_SECTION_MARKERS:
        raise RuntimeError(f"{cfg['source_key']}: section-marker drift: {markers!r}")
    if len(source_rows) != _EXPECTED_SECTOR_ROWS:
        raise RuntimeError(f"{cfg['source_key']}: sector denominator drift; expected {_EXPECTED_SECTOR_ROWS}, got {len(source_rows)}")
    section_counts = Counter(row["section"] for row in source_rows)
    if dict(section_counts) != _EXPECTED_SECTOR_COUNTS:
        raise RuntimeError(f"{cfg['source_key']}: section denominator drift: {dict(section_counts)}")

    reviewed: list[dict[str, Any]] = []
    malformed = Counter()
    for item in source_rows:
        identifiers = _strict_identifiers(item["identifier_raw"])
        listing_date = _parse_source_date(
            item["listing_raw"], source_key=cfg["source_key"], page=item["page"], row=item["row"]
        )
        expiry_date = _parse_source_date(
            item["expiry_raw"], source_key=cfg["source_key"], page=item["page"], row=item["row"], allow_blank=True
        )
        if item["expiry_raw"] and not expiry_date:
            malformed[item["expiry_raw"]] += 1
        status = (
            "renewal_update_in_progress"
            if "rinnovo" in item["note_raw"].casefold() or "aggiornamento" in item["note_raw"].casefold()
            else "listed"
        )
        identity: tuple[Any, ...] = ("id", *sorted(identifiers)) if identifiers else ("name", item["name"].casefold())
        item["identifiers"] = identifiers
        item["listing_date"] = listing_date
        item["expiry_date"] = expiry_date
        item["status"] = status
        item["group_key"] = (
            *identity,
            _semantic_date_key(item["listing_raw"], source_key=cfg["source_key"], page=item["page"], row=item["row"]),
            _semantic_date_key(item["expiry_raw"], source_key=cfg["source_key"], page=item["page"], row=item["row"]),
            status,
            item["note_raw"].casefold(),
        )
        reviewed.append(item)

    sector_statuses = Counter(item["status"] for item in reviewed)
    if sector_statuses != _EXPECTED_SECTOR_STATUS_COUNTS:
        raise RuntimeError(f"{cfg['source_key']}: sector status drift: {dict(sector_statuses)}")

    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in reviewed:
        group = grouped.setdefault(item["group_key"], {
            "items": [], "sections": [], "identifiers": [], "listing_raw": [], "expiry_raw": [],
        })
        group["items"].append(item)
        if item["section"] not in group["sections"]:
            group["sections"].append(item["section"])
        for identifier in item["identifiers"]:
            if identifier not in group["identifiers"]:
                group["identifiers"].append(identifier)
        if item["listing_raw"] not in group["listing_raw"]:
            group["listing_raw"].append(item["listing_raw"])
        if item["expiry_raw"] and item["expiry_raw"] not in group["expiry_raw"]:
            group["expiry_raw"].append(item["expiry_raw"])

    if len(grouped) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(f"{cfg['source_key']}: public-record denominator drift; expected {_EXPECTED_LISTED_RECORDS}, got {len(grouped)}")

    records: list[dict[str, Any]] = []
    for ordinal, group in enumerate(grouped.values(), 1):
        items = group["items"]
        representative = items[0]
        sections = [f"Sezione {_ROMAN_TO_NUMBER[roman]}" for roman in group["sections"]]
        name = max((item["name"] for item in items), key=len)
        office = max((item["office"] for item in items), key=len, default="")
        secondary = max((item["secondary_office"] for item in items), key=len, default="")
        identifier_raw = max((item["identifier_raw"] for item in items), key=len, default="")
        source_fields = {
            "sections": sections,
            "listing_date_raw_variants": group["listing_raw"],
            "expiry_date_raw_variants": group["expiry_raw"],
            "in_aggiornamento": representative["note_raw"] if representative["status"] == "renewal_update_in_progress" else "",
        }
        record = _record(
            cfg, ordinal,
            name=name, office=office, identifier_raw=identifier_raw, activities=sections,
            status=representative["status"], outcome_raw=representative["note_raw"],
            listing_date=representative["listing_date"], expiry_date=representative["expiry_date"],
            primary_date_label="Data iscrizione", source_fields=source_fields,
        )
        record["secondary_office"] = secondary
        record["identifiers"] = group["identifiers"]
        records.append(record)

    statuses = Counter(record["source_status"] for record in records)
    if statuses != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(f"{cfg['source_key']}: public status drift: {dict(statuses)}")
    return ParsedBatch(records, {
        "parser": "brindisi_listed",
        "sector_rows": len(reviewed),
        "public_records": len(records),
        "sector_counts": dict(section_counts),
        "sector_status_counts": dict(sector_statuses),
        "status_counts": dict(statuses),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "reviewed_malformed_dates": dict(malformed),
        "dropped_date_rows": 0,
    })


def _centre(word: dict[str, Any]) -> float:
    return (float(word["x0"]) + float(word["x1"])) / 2


def _band_text(words: list[dict[str, Any]], x0: float, x1: float, y0: float, y1: float) -> str:
    selected = [word for word in words if x0 <= _centre(word) < x1 and y0 <= float(word["top"]) < y1]
    selected.sort(key=lambda word: (round(float(word["top"]), 1), float(word["x0"])))
    return _clean(" ".join(str(word["text"]) for word in selected))


def _header_starts(page: Any, source_key: str) -> tuple[float, float, float, float, float]:
    words = page.extract_words(x_tolerance=1, y_tolerance=2, keep_blank_chars=False, use_text_flow=False)
    ragione = [word for word in words if str(word["text"]).casefold() == "ragione"]
    if not ragione:
        raise RuntimeError(f"{source_key}: applicant header Ragione not found")
    header_top = float(ragione[0]["top"])
    same_line = [word for word in words if abs(float(word["top"]) - header_top) <= 3]

    def x_for(prefix: str, *, after: float = -1.0) -> float:
        candidates = [word for word in same_line if str(word["text"]).casefold().startswith(prefix) and float(word["x0"]) > after]
        if len(candidates) != 1:
            raise RuntimeError(f"{source_key}: applicant header {prefix!r} ambiguous: {[(w['text'], w['x0']) for w in candidates]!r}")
        return float(candidates[0]["x0"])

    sede_x = x_for("sede", after=float(ragione[0]["x0"]))
    cf_x = x_for("c.f./partita", after=sede_x)
    activity_x = x_for("attività", after=cf_x)
    esito_x = x_for("esito", after=activity_x)
    date_candidates = [
        word for word in words
        if str(word["text"]).casefold() == "data" and float(word["x0"]) > esito_x and float(word["top"]) <= header_top + 5
    ]
    if len(date_candidates) != 1:
        raise RuntimeError(f"{source_key}: applicant Data header ambiguous: {[(w['text'], w['x0'], w['top']) for w in date_candidates]!r}")
    date_x = float(date_candidates[0]["x0"])
    return sede_x, cf_x, activity_x, esito_x, date_x


def _applicant_rows(path: Path, source_key: str) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    page_counts: list[int] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGES:
            raise RuntimeError(f"{source_key}: applicant page-count drift; expected {_APPLICANT_PAGES}, got {len(pdf.pages)}")
        sede_x, cf_x, activity_x, esito_x, date_x = _header_starts(pdf.pages[0], source_key)
        for page_number, page in enumerate(pdf.pages, 1):
            words = page.extract_words(x_tolerance=1, y_tolerance=2, keep_blank_chars=False, use_text_flow=False)
            page_rows: list[dict[str, Any]] = []
            for table in page.find_tables():
                extracted = table.extract() or []
                table_rows = table.rows
                if len(extracted) != len(table_rows):
                    raise RuntimeError(f"{source_key}: applicant table geometry mismatch at page {page_number}")
                for raw, table_row in zip(extracted, table_rows):
                    blob = _clean(" ".join(_clean(cell) for cell in raw))
                    if not blob or not _IDENTIFIER_LIKE.search(blob):
                        continue
                    x0, y0, x1, y1 = table_row.bbox
                    values = {
                        "name": _band_text(words, 0, sede_x, y0, y1),
                        "office": _band_text(words, sede_x, cf_x, y0, y1),
                        "identifier": _band_text(words, cf_x, activity_x, y0, y1),
                        "activity": _band_text(words, activity_x, esito_x, y0, y1),
                        "outcome": _band_text(words, esito_x, date_x, y0, y1),
                        "application": _band_text(words, date_x, float(page.width) + 1, y0, y1),
                    }
                    if not values["name"] or not values["office"] or not values["identifier"]:
                        raise RuntimeError(f"{source_key}: unresolved applicant columns at page {page_number}: {values!r}")
                    page_rows.append({"page": page_number, "row": len(page_rows) + 1, **values})
            page_counts.append(len(page_rows))
            output.extend(page_rows)
    if tuple(page_counts) != _EXPECTED_APPLICANT_PAGE_COUNTS:
        raise RuntimeError(f"{source_key}: applicant page denominators drift: {tuple(page_counts)!r}")
    return output


def parse_brindisi_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"{cfg['source_key']}: unexpected reference date {cfg.get('reference_date')!r}")
    source_rows = _applicant_rows(path, cfg["source_key"])
    if len(source_rows) != _EXPECTED_APPLICANTS:
        raise RuntimeError(f"{cfg['source_key']}: applicant denominator drift; expected {_EXPECTED_APPLICANTS}, got {len(source_rows)}")
    blank_dates: set[tuple[int, int]] = set()
    records: list[dict[str, Any]] = []
    for ordinal, item in enumerate(source_rows, 1):
        coordinate = (item["page"], item["row"])
        raw_date = _clean(item["application"])
        application_date = _parse_source_date(
            raw_date, source_key=cfg["source_key"], page=item["page"], row=item["row"],
            allow_blank=coordinate in _EXPECTED_APPLICANT_BLANK_DATES,
        )
        if not raw_date:
            blank_dates.add(coordinate)
        identifiers = _strict_identifiers(item["identifier"])
        activity = _clean(item["activity"])
        activities = [activity] if activity else []
        record = _record(
            cfg, ordinal,
            name=item["name"], office=item["office"], identifier_raw=item["identifier"],
            activities=activities, status="pending", outcome_raw=item["outcome"] or "richiedente iscrizione",
            application_date=application_date,
            primary_date_label="Data presentazione istanza" if application_date else "",
            source_fields={
                "application_date_raw_variants": [raw_date] if raw_date else [],
                "requested_activities_source": activity,
            },
        )
        record["identifiers"] = identifiers
        records.append(record)
    if blank_dates != _EXPECTED_APPLICANT_BLANK_DATES:
        raise RuntimeError(f"{cfg['source_key']}: reviewed blank application-date set drift: {sorted(blank_dates)!r}")
    if sum(bool(record["identifiers"]) for record in records) != 25:
        raise RuntimeError(f"{cfg['source_key']}: applicant identifier boundary drift")
    if sum(len(record["identifiers"]) > 1 for record in records) != 1:
        raise RuntimeError(f"{cfg['source_key']}: applicant multiple-identifier boundary drift")
    return ParsedBatch(records, {
        "parser": "brindisi_applicants",
        "public_records": len(records),
        "status_counts": {"pending": len(records)},
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "multiple_strict_identifier_records": sum(len(record["identifiers"]) > 1 for record in records),
        "reviewed_blank_application_dates": len(blank_dates),
        "dropped_date_rows": 0,
    })


PARSERS = {
    "brindisi_listed": parse_brindisi_listed,
    "brindisi_applicants": parse_brindisi_applicants,
}
