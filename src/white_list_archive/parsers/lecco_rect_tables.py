from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-09-14"

_LISTED_SOURCE_KEY = "lecco-listed"
_APPLICANT_SOURCE_KEY = "lecco-applicants"

_LISTED_SHA256 = "80c439521cf2bd4062b54fff3646666487367f0f8b47c1a91a6c8f62bcf8e5bc"
_APPLICANT_SHA256 = "7c24e015342cc2cb61cf4b5bf726621c8b3b90b195cd91c40942fc3ef6b6ba5b"

_LISTED_BYTES = 448763
_APPLICANT_BYTES = 235376
_LISTED_PAGES = 19
_APPLICANT_PAGES = 4
_LISTED_RECORDS = 230
_APPLICANT_RECORDS = 26

_LISTED_PAGE_COUNTS = (6, 12, 15, 14, 12, 13, 12, 10, 13, 11, 12, 13, 14, 13, 13, 12, 14, 13, 8)
_APPLICANT_PAGE_COUNTS = (0, 8, 14, 4)
_EXPECTED_LISTED_STATUS_COUNTS = {"listed": 201, "renewal_update_in_progress": 29}
_EXPECTED_APPLICANT_STATUS_COUNTS = {"rejected_or_denied": 4, "pending": 22}
_EXPECTED_LISTED_IDENTIFIER_COVERAGE = 228
_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE = 26

_REVIEWED_MALFORMED_LISTED_IDENTIFIERS = {
    "BIGS di Ivan Chavarriaga": "0416200136",
    "Termoidraulica": "035180050137",
}

_DATE = re.compile(r"^\d{2}[./]\d{2}[./]\d{4}$")
_STRICT_IDENTIFIER = re.compile(r"^(?:\d{11}|[A-Z]{6}[0-9A-Z]{10})$")
_SECTION = re.compile(r"Sez\.?\s*[IVX]+", re.I)

# The source PDFs are Word-exported tables. Their true logical cells are preserved as
# white rectangle objects; pdfplumber's generic row reconstruction additionally exposes
# text-line subdivisions. Binding to the wider source-cell rectangles avoids joining
# section/name fragments from adjacent companies while remaining fully byte-pinned.
_LISTED_SPECS = (
    (25.0, 26.0, 79.0, 81.0),
    (105.7, 106.4, 68.0, 70.0),
    (175.2, 175.9, 62.0, 64.0),
    (239.2, 239.9, 62.0, 64.0),
    (303.1, 303.9, 74.0, 76.0),
    (378.8, 379.2, 55.0, 56.0),
    (434.7, 435.4, 53.0, 55.0),
    (489.2, 489.9, 87.0, 89.0),
)
_APPLICANT_SPECS = (
    (66.3, 67.0, 84.0, 84.8),
    (151.3, 151.9, 69.8, 70.6),
    (222.2, 222.9, 69.8, 70.6),
    (293.1, 293.8, 64.5, 65.3),
    (358.8, 359.4, 83.0, 83.8),
    (442.9, 443.4, 52.6, 53.0),
    (496.3, 496.9, 79.7, 80.4),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_cfg(
    cfg: dict[str, Any],
    *,
    source_key: str,
    population_scope: str,
    sha256: str,
) -> None:
    if cfg.get("source_key") != source_key:
        raise RuntimeError(f"Lecco source-key drift: {cfg.get('source_key')!r} != {source_key!r}")
    if cfg.get("authority_key") != "lecco":
        raise RuntimeError("Lecco parser bound to a non-Lecco authority")
    if cfg.get("population_scope") != population_scope:
        raise RuntimeError(
            f"Lecco population-scope drift for {source_key}: "
            f"{cfg.get('population_scope')!r} != {population_scope!r}"
        )
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(
            f"Lecco reference-date drift for {source_key}: "
            f"{cfg.get('reference_date')!r} != {_REFERENCE_DATE!r}"
        )
    if cfg.get("sha256") != sha256:
        raise RuntimeError(
            f"Lecco configured SHA-256 drift for {source_key}: {cfg.get('sha256')!r} != {sha256!r}"
        )


def _validate_file(path: Path, *, source_key: str, sha256: str, byte_count: int) -> None:
    if path.stat().st_size != byte_count:
        raise RuntimeError(
            f"Lecco byte-length drift for {source_key}: {path.stat().st_size} != {byte_count}"
        )
    actual_sha = _sha256(path)
    if actual_sha != sha256:
        raise RuntimeError(
            f"Lecco byte identity drift for {source_key}: {actual_sha!r} != {sha256!r}"
        )


def _strict_date(raw: str, *, source_key: str, locator: str) -> str:
    value = _clean(raw)
    if not _DATE.fullmatch(value):
        raise RuntimeError(f"Lecco unreviewed date typography for {source_key} at {locator}: {value!r}")
    fmt = "%d/%m/%Y" if "/" in value else "%d.%m.%Y"
    try:
        return datetime.strptime(value, fmt).date().isoformat()
    except ValueError as exc:
        raise RuntimeError(f"Lecco invalid calendar date for {source_key} at {locator}: {value!r}") from exc


def _strict_identifier(raw: str) -> str:
    value = _clean(raw).upper()
    return value if _STRICT_IDENTIFIER.fullmatch(value) else ""


def _is_white_rect(rect: dict[str, Any]) -> bool:
    value = rect.get("non_stroking_color")
    return value in (1, 1.0, (1, 1, 1))


def _rect_text(page: pdfplumber.page.Page, rect: dict[str, Any]) -> str:
    return _clean(page.crop((rect["x0"], rect["top"], rect["x1"], rect["bottom"])).extract_text())


def _full_cell(
    page: pdfplumber.page.Page,
    *,
    y: float,
    spec: tuple[float, float, float, float],
    locator: str,
    column: int,
) -> tuple[str, dict[str, Any]]:
    x0_min, x0_max, width_min, width_max = spec
    candidates = [
        rect
        for rect in page.rects
        if _is_white_rect(rect)
        and x0_min <= rect["x0"] <= x0_max
        and width_min <= rect["width"] <= width_max
        and rect["top"] - 0.01 <= y <= rect["bottom"] + 0.01
    ]
    if not candidates:
        raise RuntimeError(f"Lecco logical-cell geometry drift at {locator}, column {column}")
    rect = max(candidates, key=lambda item: (item["height"], item["width"]))
    return _rect_text(page, rect), rect


def _sections(raw: str, *, source_key: str, locator: str) -> list[str]:
    value = _clean(raw)
    sections = [_clean(item) for item in _SECTION.findall(value)]
    sections = list(dict.fromkeys(sections))
    if not sections:
        raise RuntimeError(f"Lecco blank/unparsed activity section for {source_key} at {locator}: {value!r}")
    residue = _SECTION.sub(" ", value)
    if _clean(residue):
        raise RuntimeError(
            f"Lecco unreviewed activity typography for {source_key} at {locator}: {value!r}"
        )
    return sections


def _listed_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page_counts: list[int] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGES:
            raise RuntimeError(f"Lecco listed page-count drift: {len(pdf.pages)} != {_LISTED_PAGES}")
        for page_number, page in enumerate(pdf.pages, start=1):
            date_rects: list[tuple[dict[str, Any], str]] = []
            for rect in page.rects:
                if not _is_white_rect(rect):
                    continue
                if not (378.8 <= rect["x0"] <= 379.2 and 55.0 <= rect["width"] <= 56.0):
                    continue
                text = _rect_text(page, rect)
                if _DATE.fullmatch(text):
                    date_rects.append((rect, text))
            date_rects.sort(key=lambda item: item[0]["top"])
            page_counts.append(len(date_rects))
            for rect, source_date in date_rects:
                y = (rect["top"] + rect["bottom"]) / 2
                locator = f"p{page_number}:y{rect['top']:.3f}-{rect['bottom']:.3f}"
                cells = [
                    _full_cell(page, y=y, spec=spec, locator=locator, column=index)[0]
                    for index, spec in enumerate(_LISTED_SPECS)
                ]
                if cells[5] != source_date:
                    raise RuntimeError(
                        f"Lecco listed date-cell disagreement at {locator}: {cells[5]!r} != {source_date!r}"
                    )
                rows.append({"page": page_number, "locator": locator, "cells": cells})
    if tuple(page_counts) != _LISTED_PAGE_COUNTS:
        raise RuntimeError(
            f"Lecco listed per-page denominator drift: {tuple(page_counts)!r} != {_LISTED_PAGE_COUNTS!r}"
        )
    if len(rows) != _LISTED_RECORDS:
        raise RuntimeError(f"Lecco listed record-count drift: {len(rows)} != {_LISTED_RECORDS}")
    return rows


def _applicant_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page_counts: list[int] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGES:
            raise RuntimeError(f"Lecco applicant page-count drift: {len(pdf.pages)} != {_APPLICANT_PAGES}")
        for page_number, page in enumerate(pdf.pages, start=1):
            date_rects: list[tuple[dict[str, Any], str]] = []
            for rect in page.rects:
                if not _is_white_rect(rect):
                    continue
                if not (
                    442.5 <= rect["x0"] <= 443.5
                    and 52.6 <= rect["width"] <= 53.2
                    and rect["height"] > 20
                ):
                    continue
                text = _rect_text(page, rect)
                if _DATE.fullmatch(text):
                    date_rects.append((rect, text))
            date_rects.sort(key=lambda item: item[0]["top"])
            page_counts.append(len(date_rects))
            for rect, source_date in date_rects:
                y = (rect["top"] + rect["bottom"]) / 2
                locator = f"p{page_number}:y{rect['top']:.3f}-{rect['bottom']:.3f}"
                cells = [
                    _full_cell(page, y=y, spec=spec, locator=locator, column=index)[0]
                    for index, spec in enumerate(_APPLICANT_SPECS)
                ]
                if cells[5] != source_date:
                    raise RuntimeError(
                        f"Lecco applicant date-cell disagreement at {locator}: {cells[5]!r} != {source_date!r}"
                    )
                rows.append({"page": page_number, "locator": locator, "cells": cells})
    if tuple(page_counts) != _APPLICANT_PAGE_COUNTS:
        raise RuntimeError(
            f"Lecco applicant per-page denominator drift: {tuple(page_counts)!r} != {_APPLICANT_PAGE_COUNTS!r}"
        )
    if len(rows) != _APPLICANT_RECORDS:
        raise RuntimeError(f"Lecco applicant record-count drift: {len(rows)} != {_APPLICANT_RECORDS}")
    return rows


def _finalise(
    records: list[dict[str, Any]],
    *,
    source_key: str,
    expected_records: int,
    expected_status_counts: dict[str, int],
    expected_identifier_coverage: int,
) -> ParsedBatch:
    if len(records) != expected_records:
        raise RuntimeError(f"Lecco output denominator drift for {source_key}: {len(records)} != {expected_records}")
    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != expected_status_counts:
        raise RuntimeError(
            f"Lecco status-count drift for {source_key}: {status_counts!r} != {expected_status_counts!r}"
        )
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != expected_identifier_coverage:
        raise RuntimeError(
            f"Lecco identifier-coverage drift for {source_key}: {identifier_coverage} != {expected_identifier_coverage}"
        )
    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": source_key,
            "parser_version": PARSER_VERSION,
            "source_rows": expected_records,
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_coverage": identifier_coverage,
        },
    )


def parse_lecco_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key=_LISTED_SOURCE_KEY, population_scope="listed", sha256=_LISTED_SHA256)
    _validate_file(path, source_key=_LISTED_SOURCE_KEY, sha256=_LISTED_SHA256, byte_count=_LISTED_BYTES)
    records: list[dict[str, Any]] = []
    malformed: dict[str, str] = {}
    for ordinal, item in enumerate(_listed_rows(path), start=1):
        cells = item["cells"]
        name, office, secondary, identifier_raw, activities_raw, listing_raw, expiry_raw, outcome = cells
        if not name:
            raise RuntimeError(f"Lecco blank listed company at {item['locator']}")
        identifier = _strict_identifier(identifier_raw)
        if not identifier:
            malformed[name] = identifier_raw
        sections = _sections(activities_raw, source_key=_LISTED_SOURCE_KEY, locator=item["locator"])
        listing_date = _strict_date(listing_raw, source_key=_LISTED_SOURCE_KEY, locator=item["locator"])
        expiry_date = _strict_date(expiry_raw, source_key=_LISTED_SOURCE_KEY, locator=item["locator"])
        if outcome == "Aggiornamento in corso":
            status = "renewal_update_in_progress"
        elif not outcome or outcome == "Iscritta con Misura Collaborativa Ex Art. 94 Bis D.Lgs. 159/2011 per mesi 12":
            status = "listed"
        else:
            raise RuntimeError(f"Lecco unreviewed listed outcome at {item['locator']}: {outcome!r}")
        records.append(
            _record(
                cfg,
                ordinal,
                name=name,
                office=office,
                secondary=secondary,
                identifier_raw=identifier_raw,
                activities=sections,
                status=status,
                outcome_raw=outcome,
                listing_date=listing_date,
                expiry_date=expiry_date,
                primary_date_label="Data iscrizione",
                source_fields={
                    "sections": sections,
                    "requested_activities_source": activities_raw,
                    "physical_locator": item["locator"],
                },
            )
        )
    if malformed != _REVIEWED_MALFORMED_LISTED_IDENTIFIERS:
        raise RuntimeError(
            f"Lecco reviewed malformed-identifier set drift: {malformed!r} != {_REVIEWED_MALFORMED_LISTED_IDENTIFIERS!r}"
        )
    identifiers = [identifier for record in records for identifier in record["identifiers"]]
    duplicates = {value: count for value, count in Counter(identifiers).items() if count > 1}
    if duplicates:
        raise RuntimeError(f"Lecco duplicate strict listed identifiers: {duplicates!r}")
    return _finalise(
        records,
        source_key=_LISTED_SOURCE_KEY,
        expected_records=_LISTED_RECORDS,
        expected_status_counts=_EXPECTED_LISTED_STATUS_COUNTS,
        expected_identifier_coverage=_EXPECTED_LISTED_IDENTIFIER_COVERAGE,
    )


def parse_lecco_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key=_APPLICANT_SOURCE_KEY, population_scope="applicant", sha256=_APPLICANT_SHA256)
    _validate_file(path, source_key=_APPLICANT_SOURCE_KEY, sha256=_APPLICANT_SHA256, byte_count=_APPLICANT_BYTES)
    records: list[dict[str, Any]] = []
    for ordinal, item in enumerate(_applicant_rows(path), start=1):
        cells = item["cells"]
        name, office, secondary, identifier_raw, activities_raw, application_raw, outcome = cells
        if not name or not office:
            raise RuntimeError(f"Lecco blank applicant identity field at {item['locator']}: {cells!r}")
        if not _strict_identifier(identifier_raw):
            raise RuntimeError(f"Lecco unreviewed applicant identifier at {item['locator']}: {identifier_raw!r}")
        sections = _sections(activities_raw, source_key=_APPLICANT_SOURCE_KEY, locator=item["locator"])
        application_date = _strict_date(application_raw, source_key=_APPLICANT_SOURCE_KEY, locator=item["locator"])
        folded = outcome.casefold()
        decision_date = ""
        if folded == "in istruttoria":
            status = "pending"
        elif folded.startswith("diniego di iscrizione"):
            status = "rejected_or_denied"
            match = re.search(r"\bdel\s+(\d{2}[./]\d{2}[./]\d{4})$", outcome, re.I)
            if not match:
                raise RuntimeError(
                    f"Lecco denied applicant without reviewable decision date at {item['locator']}: {outcome!r}"
                )
            decision_date = _strict_date(match.group(1), source_key=_APPLICANT_SOURCE_KEY, locator=item["locator"])
        else:
            raise RuntimeError(f"Lecco unreviewed applicant outcome at {item['locator']}: {outcome!r}")
        records.append(
            _record(
                cfg,
                ordinal,
                name=name,
                office=office,
                secondary=secondary,
                identifier_raw=identifier_raw,
                activities=sections,
                status=status,
                outcome_raw=outcome,
                application_date=application_date,
                decision_date=decision_date,
                primary_date_label="Data presentazione istanza",
                source_fields={
                    "sections": sections,
                    "requested_activities_source": activities_raw,
                    "physical_locator": item["locator"],
                },
            )
        )
    return _finalise(
        records,
        source_key=_APPLICANT_SOURCE_KEY,
        expected_records=_APPLICANT_RECORDS,
        expected_status_counts=_EXPECTED_APPLICANT_STATUS_COUNTS,
        expected_identifier_coverage=_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE,
    )

PARSERS = {
    "lecco_listed": parse_lecco_listed,
    "lecco_applicants": parse_lecco_applicants,
}
