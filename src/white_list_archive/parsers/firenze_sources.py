from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.arezzo_openxml import parse_arezzo_listed
from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record


LISTED_PARSER_NAME = "firenze_listed"
APPLICANT_PARSER_NAME = "firenze_applicants"
PARSER_VERSION = "1"

_EXPECTED_LISTED = {
    "sector_rows": 989,
    "date_rows": 989,
    "public_records": 539,
    "dropped_date_rows": 0,
    "malformed_date_rows_preserved": 0,
    "date_conflict_identity_groups": 0,
    "identifier_coverage": 537,
    "raw_identifier_only": 2,
}
_EXPECTED_LISTED_STATUSES = {
    "listed": 429,
    "renewal_update_in_progress": 110,
}
_EXPECTED_APPLICANT_PAGE_ROWS = [15, 16, 16, 16, 16, 16, 16, 14, 0]
_EXPECTED_APPLICANT_ROWS = 125
_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_STRICT_11 = re.compile(r"^\d{11}$")
_STRICT_16 = re.compile(r"^[A-Z]{6}[0-9A-Z]{10}$")

_REVIEWED_RAW_ONLY_IDENTIFIERS = {
    ("CALENZANO SPURGHI DI DANI MICHELE", "DNAMHL69H19B832"),
    ("VALDARNO SPURGHI DI BENEDETTI MASSIMILIANO", "BNDMSM73B08D583"),
}
_REVIEWED_BLANK_OFFICES = {
    ("SAN TOMMASO D'AQUINO Soc. Coop. Sociale", "05056380487"),
    ("TECNOCONFERENCE Srl", "03755090481"),
}


def parse_firenze_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    """Parse the Firenze listed-side workbook through the audited grouped-sector family."""
    batch = parse_arezzo_listed(path, cfg)
    diagnostics = dict(batch.diagnostics)

    for field, expected in _EXPECTED_LISTED.items():
        observed = diagnostics.get(field)
        if observed != expected:
            raise RuntimeError(
                f"Firenze listed reviewed boundary drift for {field}: expected {expected!r}, got {observed!r}"
            )
    statuses = diagnostics.get("status_counts") or {}
    if statuses != _EXPECTED_LISTED_STATUSES:
        raise RuntimeError(
            f"Firenze listed reviewed status boundary drift: expected {_EXPECTED_LISTED_STATUSES!r}, got {statuses!r}"
        )

    diagnostics["parser"] = LISTED_PARSER_NAME
    diagnostics["parser_version"] = PARSER_VERSION
    return ParsedBatch(batch.records, diagnostics)


def _header_x(words: list[dict[str, Any]], page_number: int) -> tuple[float, float, float, float]:
    candidates: dict[str, list[dict[str, Any]]] = {}
    for word in words:
        text = str(word.get("text", ""))
        if text in {"Sede", "Codice", "Data", "Esito"}:
            candidates.setdefault(text, []).append(word)

    missing = [key for key in ("Sede", "Codice", "Data", "Esito") if not candidates.get(key)]
    if missing:
        raise RuntimeError(f"Firenze applicant page {page_number}: missing reviewed header words {missing!r}")

    # The repeated header appears once per page in the current official edition.
    # If the source introduces another same-named token at a different vertical
    # position, do not guess which one is the table header.
    header_top = min(float(word["top"]) for word in candidates["Sede"])

    def closest(label: str) -> dict[str, Any]:
        matches = sorted(candidates[label], key=lambda word: abs(float(word["top"]) - header_top))
        if not matches or abs(float(matches[0]["top"]) - header_top) > 1.0:
            raise RuntimeError(f"Firenze applicant page {page_number}: {label!r} header is not aligned")
        return matches[0]

    office_x = float(closest("Sede")["x0"])
    identifier_x = float(closest("Codice")["x0"])
    date_x = float(closest("Data")["x0"])
    outcome_x = float(closest("Esito")["x0"])
    if not (300 < office_x < 350 < identifier_x < 600 < date_x < 700 < outcome_x < 800):
        raise RuntimeError(
            f"Firenze applicant page {page_number}: reviewed column geometry changed: "
            f"{(office_x, identifier_x, date_x, outcome_x)!r}"
        )
    return office_x, identifier_x, date_x, outcome_x


def _words_in_source_row(
    words: list[dict[str, Any]],
    date_word: dict[str, Any],
    *,
    tolerance: float = 2.2,
) -> list[dict[str, Any]]:
    top = float(date_word["top"])
    return sorted(
        [word for word in words if abs(float(word["top"]) - top) <= tolerance],
        key=lambda word: float(word["x0"]),
    )


def _column_text(words: list[dict[str, Any]], lower: float, upper: float) -> str:
    return _clean(" ".join(str(word["text"]) for word in words if lower <= float(word["x0"]) < upper))


def parse_firenze_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    """Parse the reviewed 9-page Firenze applicant PDF without inferring missing source fields."""
    extracted: list[tuple[int, str, str, str, str, str]] = []
    page_rows: list[int] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != 9:
            raise RuntimeError(f"Firenze applicant page denominator changed: expected 9, got {len(pdf.pages)}")

        for page_number, page in enumerate(pdf.pages, 1):
            words = page.extract_words(x_tolerance=2, y_tolerance=2, keep_blank_chars=False)
            office_x, identifier_x, date_x, outcome_x = _header_x(words, page_number)
            date_words = [
                word
                for word in words
                if _DATE.fullmatch(str(word.get("text", "")))
                and date_x - 5 <= float(word["x0"]) < outcome_x
            ]
            date_words.sort(key=lambda word: float(word["top"]))
            page_rows.append(len(date_words))

            for date_word in date_words:
                row_words = _words_in_source_row(words, date_word)
                name = _column_text(row_words, 0, office_x)
                office = _column_text(row_words, office_x, identifier_x)
                identifier_raw = _column_text(row_words, identifier_x, date_x)
                application_raw = _column_text(row_words, date_x, outcome_x)
                outcome = _column_text(row_words, outcome_x, 10000)

                if not name or not identifier_raw:
                    raise RuntimeError(
                        f"Firenze applicant page {page_number}: row at top={date_word['top']!r} "
                        "has a blank company identity field"
                    )
                if not _DATE.fullmatch(application_raw):
                    raise RuntimeError(
                        f"Firenze applicant page {page_number}: application-date column drift: {application_raw!r}"
                    )
                if outcome:
                    raise RuntimeError(
                        f"Firenze applicant page {page_number}: non-empty Esito requires review: {outcome!r}"
                    )
                extracted.append((page_number, name, office, identifier_raw, application_raw, outcome))

    if page_rows != _EXPECTED_APPLICANT_PAGE_ROWS:
        raise RuntimeError(
            f"Firenze applicant page-row denominator drift: expected {_EXPECTED_APPLICANT_PAGE_ROWS}, got {page_rows}"
        )
    if len(extracted) != _EXPECTED_APPLICANT_ROWS:
        raise RuntimeError(
            f"Firenze applicant denominator drift: expected {_EXPECTED_APPLICANT_ROWS}, got {len(extracted)}"
        )

    raw_only = {
        (name, identifier_raw)
        for _page, name, _office, identifier_raw, _date, _outcome in extracted
        if not (_STRICT_11.fullmatch(identifier_raw) or _STRICT_16.fullmatch(identifier_raw.upper()))
    }
    if raw_only != _REVIEWED_RAW_ONLY_IDENTIFIERS:
        raise RuntimeError(
            f"Firenze applicant reviewed raw-only identifier boundary changed: {sorted(raw_only)!r}"
        )

    blank_offices = {
        (name, identifier_raw)
        for _page, name, office, identifier_raw, _date, _outcome in extracted
        if not office
    }
    if blank_offices != _REVIEWED_BLANK_OFFICES:
        raise RuntimeError(
            f"Firenze applicant reviewed blank-office boundary changed: {sorted(blank_offices)!r}"
        )

    records: list[dict[str, Any]] = []
    for ordinal, (page_number, name, office, identifier_raw, application_raw, outcome) in enumerate(extracted, 1):
        records.append(
            _record(
                cfg,
                ordinal,
                name=name,
                office=office,
                identifier_raw=identifier_raw,
                status="pending",
                outcome_raw=outcome,
                application_date=application_raw,
                primary_date_label="Data presentazione istanza",
                source_fields={
                    "source_page_number": page_number,
                    "application_date_raw": application_raw,
                },
            )
        )

    statuses = Counter(record["source_status"] for record in records)
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    raw_identifier_only = sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records)
    if statuses != Counter({"pending": 125}):
        raise RuntimeError(f"Firenze applicant status boundary drift: {dict(statuses)!r}")
    if identifier_coverage != 123 or raw_identifier_only != 2:
        raise RuntimeError(
            f"Firenze applicant identifier boundary drift: structured={identifier_coverage}, raw_only={raw_identifier_only}"
        )

    diagnostics = {
        "parser": APPLICANT_PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "pages": 9,
        "page_rows": page_rows,
        "source_rows": len(extracted),
        "public_records": len(records),
        "status_counts": dict(statuses),
        "identifier_coverage": identifier_coverage,
        "raw_identifier_only": raw_identifier_only,
        "blank_registered_office": len(blank_offices),
    }
    return ParsedBatch(records, diagnostics)
