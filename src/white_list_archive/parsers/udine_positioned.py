from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-09-09"
_LISTED_PAGE_COUNTS = (
    20, 24, 25, 27, 27, 25, 26, 25, 23, 28, 15, 24, 27, 17, 15, 26,
    24, 27, 27, 26, 25, 28, 28, 26, 26, 14, 22, 24, 23, 25, 13, 21,
    23, 23, 22, 27, 24, 23, 22, 22, 23, 23, 20, 22, 25, 11, 24, 23,
    26, 27, 25, 24, 15, 5, 12, 15, 19, 7, 24, 24, 27, 24, 25, 22,
)
_APPLICANT_PAGE_COUNTS = (17, 2)
_EXPECTED_SECTION_HEADINGS = (
    (1, "I"), (11, "II"), (15, "III"), (26, "IV"), (31, "V"),
    (46, "VI"), (54, "VII"), (54, "VIII"), (56, "IX"), (58, "X"),
)
_ROMAN_TO_NUMBER = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
}
_VALID_IDENTIFIER = re.compile(r"(?:\d{11}|[A-Z0-9]{16})")
_REVIEWED_NONSTANDARD_IDENTIFIER = "000152050308"
_DATE_TOKEN = re.compile(r"\d{1,3}/\d{1,2}/\d{4}")
_REVIEWED_BAD_DATES = {"269/01/2027"}
_ACTIVITY_CODES = set("ABCDEFGHIL")


def _centre(word: dict[str, Any]) -> float:
    return (float(word["x0"]) + float(word["x1"])) / 2


def _cluster(values: list[float], tolerance: float = 3.2) -> list[float]:
    groups: list[list[float]] = []
    for value in sorted(values):
        if not groups or value - groups[-1][-1] > tolerance:
            groups.append([value])
        else:
            groups[-1].append(value)
    return [sum(group) / len(group) for group in groups]


def _text_in_band(
    words: list[dict[str, Any]], x_min: float, x_max: float, y_min: float, y_max: float
) -> str:
    selected = [
        word for word in words
        if x_min <= _centre(word) < x_max and y_min <= float(word["top"]) < y_max
    ]
    selected.sort(key=lambda word: (round(float(word["top"]), 1), float(word["x0"])))
    return _clean(" ".join(str(word["text"]) for word in selected))


def _strict_source_date(raw: str, *, page: int, row: int, source_key: str) -> str:
    value = _clean(raw)
    if value in _REVIEWED_BAD_DATES:
        return ""
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
        raise RuntimeError(f"{source_key}: unreviewed date typography at page {page} row {row}: {raw!r}")
    day, month, year = map(int, value.split("/"))
    try:
        return date(year, month, day).isoformat()
    except ValueError as exc:
        raise RuntimeError(f"{source_key}: invalid calendar date at page {page} row {row}: {raw!r}") from exc


def _section_headings(words: list[dict[str, Any]]) -> list[tuple[float, str]]:
    headings: list[tuple[float, str]] = []
    for word in words:
        if str(word["text"]).casefold() != "sezione":
            continue
        peers = [
            candidate for candidate in words
            if float(word["x1"]) < float(candidate["x0"]) < float(word["x1"]) + 100
            and abs(float(candidate["top"]) - float(word["top"])) <= 3
        ]
        for candidate in sorted(peers, key=lambda item: float(item["x0"])):
            token = str(candidate["text"]).upper().strip(".,:")
            if token in _ROMAN_TO_NUMBER:
                headings.append((float(word["top"]), token))
                break
    return headings


def _listed_identifier_anchors(words: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for word in words:
        token = str(word["text"]).upper()
        if not 490 <= _centre(word) < 605:
            continue
        if _VALID_IDENTIFIER.fullmatch(token) or token == _REVIEWED_NONSTANDARD_IDENTIFIER:
            values.append(float(word["top"]))
    return _cluster(values)


def _applicant_identifier_anchors(words: list[dict[str, Any]]) -> list[float]:
    return _cluster([
        float(word["top"]) for word in words
        if 480 <= _centre(word) < 600 and _VALID_IDENTIFIER.fullmatch(str(word["text"]).upper())
    ])


def _row_bounds(
    y: float, anchors: list[float], index: int, headings: list[tuple[float, str]], page_height: float
) -> tuple[float, float]:
    candidates = [y + 38, page_height - 18]
    if index + 1 < len(anchors):
        candidates.append(anchors[index + 1] - 0.6)
    candidates.extend(top - 0.6 for top, _section in headings if y < top < y + 38)
    return y - 3.5, max(y + 7, min(candidates))


def _row_identifier(
    words: list[dict[str, Any]], y_min: float, y_max: float, *, page: int, row: int, source_key: str,
    allow_nonstandard: bool = False,
) -> str:
    candidates: list[str] = []
    for word in words:
        if not (490 <= _centre(word) < 605 and y_min <= float(word["top"]) < y_max):
            continue
        token = str(word["text"]).upper()
        if _VALID_IDENTIFIER.fullmatch(token) or (allow_nonstandard and token == _REVIEWED_NONSTANDARD_IDENTIFIER):
            candidates.append(token)
    if len(candidates) != 1:
        raise RuntimeError(f"{source_key}: expected one identifier token at page {page} row {row}, got {candidates!r}")
    return candidates[0]


def _row_dates(
    words: list[dict[str, Any]], y_min: float, y_max: float, *, expected: int, page: int, row: int, source_key: str,
) -> list[str]:
    values = [
        str(word["text"]) for word in words
        if 590 <= _centre(word) < 790 and y_min <= float(word["top"]) < y_max
        and _DATE_TOKEN.fullmatch(str(word["text"]))
    ]
    if len(values) != expected:
        raise RuntimeError(f"{source_key}: expected {expected} source date tokens at page {page} row {row}, got {values!r}")
    return values


def _activity_codes(raw: str, *, page: int, row: int, source_key: str) -> list[str]:
    value = _clean(raw).upper().replace("–", "-")
    codes = [token for token in re.split(r"[^A-Z]+", value) if token]
    if not codes or any(code not in _ACTIVITY_CODES for code in codes):
        raise RuntimeError(f"{source_key}: unreviewed activity code at page {page} row {row}: {raw!r}")
    return codes


def parse_udine_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"{cfg['source_key']}: unexpected reference date {cfg.get('reference_date')!r}")

    records: list[dict[str, Any]] = []
    page_counts: list[int] = []
    seen_headings: list[tuple[int, str]] = []
    current_section: str | None = None
    malformed_dates: Counter[str] = Counter()

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != len(_LISTED_PAGE_COUNTS):
            raise RuntimeError(f"{cfg['source_key']}: page-count drift; expected 64, got {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, 1):
            words = page.extract_words(x_tolerance=1, y_tolerance=2, keep_blank_chars=False, use_text_flow=False)
            headings = _section_headings(words)
            seen_headings.extend((page_number, section) for _top, section in headings)
            anchors = _listed_identifier_anchors(words)
            expected_page_count = _LISTED_PAGE_COUNTS[page_number - 1]
            if len(anchors) != expected_page_count:
                raise RuntimeError(
                    f"{cfg['source_key']}: company-anchor drift at page {page_number}; "
                    f"expected {expected_page_count}, got {len(anchors)}"
                )
            page_counts.append(len(anchors))
            for row_number, y in enumerate(anchors, 1):
                prior = [heading for heading in headings if heading[0] < y]
                if prior:
                    current_section = prior[-1][1]
                if current_section is None:
                    raise RuntimeError(f"{cfg['source_key']}: missing source section at page {page_number} row {row_number}")
                y_min, y_max = _row_bounds(y, anchors, row_number - 1, headings, float(page.height))
                name = _text_in_band(words, 45, 235, y_min, y_max)
                office = _text_in_band(words, 235, 470, y_min, y_max)
                secondary = _text_in_band(words, 470, 515, y_min, y_max)
                if not name or not office:
                    raise RuntimeError(
                        f"{cfg['source_key']}: unresolved name/office at page {page_number} row {row_number}: "
                        f"name={name!r}, office={office!r}"
                    )
                identifier_raw = _row_identifier(
                    words, y_min, y_max, page=page_number, row=row_number,
                    source_key=cfg["source_key"], allow_nonstandard=True,
                )
                dates = _row_dates(
                    words, y_min, y_max, expected=2, page=page_number, row=row_number, source_key=cfg["source_key"]
                )
                listing_date = _strict_source_date(dates[0], page=page_number, row=row_number, source_key=cfg["source_key"])
                expiry_date = _strict_source_date(dates[1], page=page_number, row=row_number, source_key=cfg["source_key"])
                for raw, parsed in zip(dates, (listing_date, expiry_date)):
                    if raw and not parsed:
                        malformed_dates[raw] += 1
                row_text = _clean(" ".join(
                    str(word["text"]) for word in words if y_min <= float(word["top"]) < y_max
                ))
                updating = "aggiornamento" in row_text.casefold()
                status = "renewal_update_in_progress" if updating else "listed"
                section_number = _ROMAN_TO_NUMBER[current_section]
                source_fields: dict[str, Any] = {
                    "source_page": page_number,
                    "source_page_row": row_number,
                    "section_roman": current_section,
                    "listing_date_raw": dates[0],
                    "expiry_date_raw": dates[1],
                    "update_raw": "In aggiornamento" if updating else "",
                    "registered_office_source_band": office,
                    "secondary_representation_source_band": secondary,
                }
                if not listing_date:
                    source_fields["listing_date_unparsed_reviewed"] = True
                if not expiry_date:
                    source_fields["expiry_date_unparsed_reviewed"] = True
                record = _record(
                    cfg,
                    len(records) + 1,
                    name=name,
                    office=office,
                    secondary=secondary,
                    identifier_raw=identifier_raw,
                    activities=[f"Sezione {section_number}"],
                    status=status,
                    outcome_raw="In aggiornamento" if updating else "",
                    listing_date=listing_date,
                    expiry_date=expiry_date,
                    primary_date_label="Data iscrizione" if listing_date else "",
                    source_fields=source_fields,
                )
                # _record is deliberately strict enough not to normalise the reviewed 12-digit source value.
                records.append(record)

    if tuple(seen_headings) != _EXPECTED_SECTION_HEADINGS:
        raise RuntimeError(f"{cfg['source_key']}: section-heading drift: {seen_headings!r}")
    if len(records) != sum(_LISTED_PAGE_COUNTS):
        raise RuntimeError(f"{cfg['source_key']}: denominator drift: {len(records)}")
    if malformed_dates - Counter(_REVIEWED_BAD_DATES):
        raise RuntimeError(f"{cfg['source_key']}: unexpected malformed dates: {dict(malformed_dates)}")

    statuses = Counter(record["source_status"] for record in records)
    return ParsedBatch(records, {
        "parser": "udine_positioned_listed",
        "public_records": len(records),
        "page_rows": page_counts,
        "status_counts": dict(statuses),
        "section_counts": dict(Counter(record["requested_activities"][0] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "identifier_raw_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "reviewed_malformed_dates": dict(malformed_dates),
        "dropped_date_rows": 0,
    })


def parse_udine_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"{cfg['source_key']}: unexpected reference date {cfg.get('reference_date')!r}")

    records: list[dict[str, Any]] = []
    page_counts: list[int] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != len(_APPLICANT_PAGE_COUNTS):
            raise RuntimeError(f"{cfg['source_key']}: page-count drift; expected 2, got {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, 1):
            words = page.extract_words(x_tolerance=1, y_tolerance=2, keep_blank_chars=False, use_text_flow=False)
            anchors = _applicant_identifier_anchors(words)
            expected_page_count = _APPLICANT_PAGE_COUNTS[page_number - 1]
            if len(anchors) != expected_page_count:
                raise RuntimeError(
                    f"{cfg['source_key']}: company-anchor drift at page {page_number}; "
                    f"expected {expected_page_count}, got {len(anchors)}"
                )
            page_counts.append(len(anchors))
            for row_number, y in enumerate(anchors, 1):
                y_min, y_max = _row_bounds(y, anchors, row_number - 1, [], float(page.height))
                name = _text_in_band(words, 25, 240, y_min, y_max)
                office = _text_in_band(words, 240, 470, y_min, y_max)
                if (page_number, row_number) == (1, 17):
                    if name != "MTL MESSAGGERIE TRASPORTI E":
                        raise RuntimeError(f"{cfg['source_key']}: reviewed MTL continuation drift: {name!r}")
                    name = "MTL MESSAGGERIE TRASPORTI E LOGISTICA SOCIETA’ COOPERATIVA"
                if not name or not office:
                    raise RuntimeError(
                        f"{cfg['source_key']}: unresolved name/office at page {page_number} row {row_number}: "
                        f"name={name!r}, office={office!r}"
                    )
                identifier_raw = _row_identifier(
                    words, y_min, y_max, page=page_number, row=row_number,
                    source_key=cfg["source_key"], allow_nonstandard=False,
                )
                dates = _row_dates(
                    words, y_min, y_max, expected=1, page=page_number, row=row_number, source_key=cfg["source_key"]
                )
                application_date = _strict_source_date(
                    dates[0], page=page_number, row=row_number, source_key=cfg["source_key"]
                )
                activity_raw = _text_in_band(words, 600, 680, y_min, y_max)
                codes = _activity_codes(activity_raw, page=page_number, row=row_number, source_key=cfg["source_key"])
                record = _record(
                    cfg,
                    len(records) + 1,
                    name=name,
                    office=office,
                    identifier_raw=identifier_raw,
                    activities=codes,
                    status="pending",
                    application_date=application_date,
                    primary_date_label="Data presentazione istanza",
                    source_fields={
                        "source_page": page_number,
                        "source_page_row": row_number,
                        "activity_codes_raw": activity_raw,
                        "application_date_raw": dates[0],
                        "population_evidence": "official current list of suppliers that requested White List registration",
                        "cross_page_name_repair": (page_number, row_number) == (1, 17),
                    },
                )
                records.append(record)

    if len(records) != sum(_APPLICANT_PAGE_COUNTS):
        raise RuntimeError(f"{cfg['source_key']}: denominator drift: {len(records)}")
    return ParsedBatch(records, {
        "parser": "udine_positioned_applicants",
        "public_records": len(records),
        "page_rows": page_counts,
        "status_counts": {"pending": len(records)},
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "identifier_raw_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "dropped_date_rows": 0,
    })


PARSERS = {
    "udine_positioned_listed": parse_udine_listed,
    "udine_positioned_applicants": parse_udine_applicants,
}
