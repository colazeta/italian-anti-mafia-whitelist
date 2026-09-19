from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
LISTED_PARSER_NAME = "lucca_listed"
APPLICANT_PARSER_NAME = "lucca_applicants"

_LISTED_REFERENCE_DATE = "2026-09-11"
_APPLICANT_REFERENCE_DATE = "2026-09-08"
_LISTED_DOCUMENT_MARKER = "Aggiornato al 11/09/2026"
_APPLICANT_DOCUMENT_MARKER = "Aggiornato al 08/09/2026"

_EXPECTED_LISTED_PAGE_ROWS = (
    5, 14, 12, 12, 14, 14, 12, 13, 14, 14, 13, 13, 15,
    14, 14, 14, 16, 15, 13, 15, 13, 13, 13, 14, 11, 1,
)
_EXPECTED_APPLICANT_PAGE_ROWS = (1, 17, 15, 17, 18, 3)
_EXPECTED_LISTED_RECORDS = 331
_EXPECTED_APPLICANT_RECORDS = 71
_EXPECTED_LISTED_STATUSES = Counter({"listed": 229, "renewal_update_in_progress": 102})
_EXPECTED_LISTED_IDENTIFIER_COVERAGE = 324
_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE = 69
_EXPECTED_LISTED_RAW_ONLY = {
    "CF/PI",
    "C.F. / P.I. 002493530469",
    "C.F./P.I.",
    "C.F./ P.I. 1351930464",
    "0263091467",
    "C.F./ P.I. 0129100458",
}
_EXPECTED_LISTED_RAW_ONLY_COUNTS = Counter({"C.F./P.I.": 2, "CF/PI": 1, "C.F. / P.I. 002493530469": 1, "C.F./ P.I. 1351930464": 1, "0263091467": 1, "C.F./ P.I. 0129100458": 1})
_EXPECTED_APPLICANT_RAW_ONLY_COUNTS = Counter({"0269090460": 1, "022189230465": 1})
_EXPECTED_LISTED_DUPLICATE_IDENTIFIERS = {
    "02100230461", "02221960467", "02370380467", "01946560461",
}
_EXPECTED_APPLICANT_DUPLICATE_IDENTIFIERS = {"02617900465"}
_EXPECTED_REVIEWED_COMPLETED_UPDATE_NOTES = {
    "18/01/2027 Aggiornato con Modifica compagine del 23.6.2026.",
    "16/05/2025 AGGIORNATA COMPAGINE SOC. IL 17/05/2024",
}

_DATE_TOKEN = re.compile(r"(?<!\d)(\d{1,2}[./]\d{1,2}[./]\d{4})(?!\d)")
_FULL_DATE = re.compile(r"^\d{1,2}[./]\d{1,2}[./]\d{4}$")
_IN_AGG = re.compile(r"\bIN\s+AGG\.", re.I)


def _source_date(raw: str) -> str:
    value = _clean(raw)
    match = re.fullmatch(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", value)
    if match is None:
        return ""
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def _first_source_date(raw: str) -> tuple[str, str]:
    match = _DATE_TOKEN.search(_clean(raw))
    if match is None:
        return "", ""
    token = match.group(1)
    return _source_date(token), token


def _source_identifiers(raw: str) -> list[str]:
    """Extract only explicit source tokens; never join broken numeric fragments."""
    value = _clean(raw).upper()
    # Strip only field labels. Slashes remain separators, so split source digits are
    # deliberately not repaired into a tax/VAT identifier.
    value = re.sub(r"C\.?\s*F\.?\s*/\s*P\.?\s*(?:I\.?|IVA\.?)", " ", value, flags=re.I)
    value = re.sub(r"\bCF\s*/\s*PI\b", " ", value, flags=re.I)
    value = re.sub(r"C\.?\s*F\.?", " ", value, flags=re.I)
    value = re.sub(r"P\.?\s*IVA\.?", " ", value, flags=re.I)
    value = re.sub(r"P\.?\s*I\.?", " ", value, flags=re.I)
    identifiers: list[str] = []
    for token in re.split(r"[\s/·;,]+", value):
        token = re.sub(r"[^A-Z0-9]", "", token)
        if ((token.isdigit() and len(token) == 11) or (len(token) == 16 and token.isalnum())) and token not in identifiers:
            identifiers.append(token)
    return identifiers


def _listed_status(expiry_raw: str) -> str:
    value = _clean(expiry_raw)
    if _IN_AGG.search(value):
        return "renewal_update_in_progress"
    if re.search(r"[A-Za-zÀ-ÿ]", value) and value not in _EXPECTED_REVIEWED_COMPLETED_UPDATE_NOTES:
        raise RuntimeError(f"lucca_listed: unreviewed expiry/status note {expiry_raw!r}")
    return "listed"


def _extract_rows(
    path: Path,
    *,
    source_key: str,
    pages: int,
    expected_columns: int,
    expected_page_rows: tuple[int, ...],
    document_marker: str,
    width: float,
    height: float,
) -> tuple[list[list[str]], tuple[int, ...]]:
    rows: list[list[str]] = []
    page_counts: list[int] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != pages:
            raise RuntimeError(f"{source_key}: page-count drift; expected {pages}, got {len(pdf.pages)}")
        first_text = _clean(pdf.pages[0].extract_text() or "")
        if document_marker not in first_text:
            raise RuntimeError(f"{source_key}: approved document marker missing: {document_marker!r}")
        for page_number, page in enumerate(pdf.pages, 1):
            if abs(float(page.width) - width) > 0.2 or abs(float(page.height) - height) > 0.2:
                raise RuntimeError(
                    f"{source_key}: page geometry drift at page {page_number}: "
                    f"{float(page.width):.2f}x{float(page.height):.2f}"
                )
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(f"{source_key}: expected one table on page {page_number}, got {len(tables)}")
            page_rows: list[list[str]] = []
            for row_number, raw in enumerate(tables[0].extract() or [], 1):
                values = [_clean(cell) for cell in raw]
                if len(values) != expected_columns:
                    raise RuntimeError(
                        f"{source_key}: column-count drift at page {page_number} row {row_number}: {len(values)}"
                    )
                if page_number == 1 and row_number == 1 and values[0].casefold().startswith("ragione sociale"):
                    continue
                if not values[0] or not values[1] or not values[2] or not values[3]:
                    raise RuntimeError(
                        f"{source_key}: incomplete source row at page {page_number} row {row_number}: {values!r}"
                    )
                page_rows.append(values)
            page_counts.append(len(page_rows))
            rows.extend(page_rows)
    observed = tuple(page_counts)
    if observed != expected_page_rows:
        raise RuntimeError(f"{source_key}: page-row denominator drift: {observed!r}")
    return rows, observed


def _identifier_boundary(rows: list[list[str]]) -> tuple[int, Counter[str], set[str]]:
    structured: list[str] = []
    raw_only: Counter[str] = Counter()
    for row in rows:
        ids = _source_identifiers(row[2])
        if ids:
            structured.extend(ids)
        else:
            raw_only[_clean(row[2])] += 1
    duplicates = {value for value, count in Counter(structured).items() if count > 1}
    coverage = sum(bool(_source_identifiers(row[2])) for row in rows)
    return coverage, raw_only, duplicates


def parse_lucca_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    if cfg.get("reference_date") != _LISTED_REFERENCE_DATE:
        raise RuntimeError(f"{cfg['source_key']}: unexpected reference date {cfg.get('reference_date')!r}")
    rows, page_counts = _extract_rows(
        path,
        source_key=cfg["source_key"],
        pages=26,
        expected_columns=6,
        expected_page_rows=_EXPECTED_LISTED_PAGE_ROWS,
        document_marker=_LISTED_DOCUMENT_MARKER,
        width=792.0,
        height=612.0,
    )
    if len(rows) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(f"{cfg['source_key']}: expected 331 listed source rows, got {len(rows)}")

    coverage, raw_only, duplicates = _identifier_boundary(rows)
    if coverage != _EXPECTED_LISTED_IDENTIFIER_COVERAGE or raw_only != _EXPECTED_LISTED_RAW_ONLY_COUNTS:
        raise RuntimeError(
            f"{cfg['source_key']}: listed identifier boundary drift: coverage={coverage}, raw_only={dict(raw_only)!r}"
        )
    if duplicates != _EXPECTED_LISTED_DUPLICATE_IDENTIFIERS:
        raise RuntimeError(f"{cfg['source_key']}: listed duplicate identifiers drift: {sorted(duplicates)!r}")

    records: list[dict[str, Any]] = []
    statuses: Counter[str] = Counter()
    no_expiry_date = 0
    completed_update_notes: set[str] = set()
    for ordinal, row in enumerate(rows, 1):
        name, office, identifier_raw, activity_raw, listing_raw, expiry_raw = row
        if not _FULL_DATE.fullmatch(listing_raw) or not _source_date(listing_raw):
            raise RuntimeError(f"{cfg['source_key']}: unreviewed listing date at row {ordinal}: {listing_raw!r}")
        status = _listed_status(expiry_raw)
        statuses[status] += 1
        expiry_date, expiry_token = _first_source_date(expiry_raw)
        if not expiry_date:
            no_expiry_date += 1
            if _clean(expiry_raw).casefold() != "in agg.":
                raise RuntimeError(f"{cfg['source_key']}: unreviewed missing expiry date at row {ordinal}: {expiry_raw!r}")
        if re.search(r"[A-Za-zÀ-ÿ]", _clean(expiry_raw)) and status == "listed":
            completed_update_notes.add(_clean(expiry_raw))

        record = _record(
            cfg,
            ordinal,
            name=name,
            office=office,
            identifier_raw=identifier_raw,
            activities=[activity_raw],
            status=status,
            outcome_raw=expiry_raw if status == "renewal_update_in_progress" else "",
            listing_date=listing_raw,
            expiry_date=expiry_date,
            primary_date_label="Data iscrizione",
            source_fields={
                "sections": [activity_raw],
                "listing_date_raw_variants": [listing_raw],
                "expiry_date_raw_variants": [expiry_token] if expiry_token else [],
                "in_aggiornamento": expiry_raw if status == "renewal_update_in_progress" else "",
                "notes": [expiry_raw] if status == "listed" and re.search(r"[A-Za-zÀ-ÿ]", expiry_raw) else [],
            },
        )
        record["identifiers"] = _source_identifiers(identifier_raw)
        records.append(record)

    if statuses != _EXPECTED_LISTED_STATUSES:
        raise RuntimeError(f"{cfg['source_key']}: listed status boundary drift: {dict(statuses)!r}")
    if no_expiry_date != 1:
        raise RuntimeError(f"{cfg['source_key']}: missing-expiry reviewed boundary drift: {no_expiry_date}")
    if completed_update_notes != _EXPECTED_REVIEWED_COMPLETED_UPDATE_NOTES:
        raise RuntimeError(
            f"{cfg['source_key']}: completed-update note boundary drift: {sorted(completed_update_notes)!r}"
        )

    return ParsedBatch(records, {
        "parser": LISTED_PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "pages": 26,
        "page_rows": list(page_counts),
        "source_rows": len(rows),
        "public_records": len(records),
        "status_counts": dict(statuses),
        "identifier_coverage": coverage,
        "raw_identifier_only": sum(raw_only.values()),
        "duplicate_structured_identifier_values": len(duplicates),
        "reviewed_missing_expiry_date": no_expiry_date,
        "reviewed_completed_update_notes": len(completed_update_notes),
    })


def parse_lucca_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    if cfg.get("reference_date") != _APPLICANT_REFERENCE_DATE:
        raise RuntimeError(f"{cfg['source_key']}: unexpected reference date {cfg.get('reference_date')!r}")
    rows, page_counts = _extract_rows(
        path,
        source_key=cfg["source_key"],
        pages=6,
        expected_columns=5,
        expected_page_rows=_EXPECTED_APPLICANT_PAGE_ROWS,
        document_marker=_APPLICANT_DOCUMENT_MARKER,
        width=841.92,
        height=595.32,
    )
    if len(rows) != _EXPECTED_APPLICANT_RECORDS:
        raise RuntimeError(f"{cfg['source_key']}: expected 71 applicant source rows, got {len(rows)}")

    coverage, raw_only, duplicates = _identifier_boundary(rows)
    if coverage != _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE or raw_only != _EXPECTED_APPLICANT_RAW_ONLY_COUNTS:
        raise RuntimeError(
            f"{cfg['source_key']}: applicant identifier boundary drift: coverage={coverage}, raw_only={dict(raw_only)!r}"
        )
    if duplicates != _EXPECTED_APPLICANT_DUPLICATE_IDENTIFIERS:
        raise RuntimeError(f"{cfg['source_key']}: applicant duplicate identifiers drift: {sorted(duplicates)!r}")

    records: list[dict[str, Any]] = []
    for ordinal, row in enumerate(rows, 1):
        name, office, identifier_raw, activity_raw, application_raw = row
        if not _FULL_DATE.fullmatch(application_raw) or not _source_date(application_raw):
            raise RuntimeError(f"{cfg['source_key']}: unreviewed application date at row {ordinal}: {application_raw!r}")
        record = _record(
            cfg,
            ordinal,
            name=name,
            office=office,
            identifier_raw=identifier_raw,
            activities=[activity_raw],
            status="pending",
            application_date=application_raw,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "requested_activities_source": activity_raw,
                "application_date_raw_variants": [application_raw],
            },
        )
        record["identifiers"] = _source_identifiers(identifier_raw)
        records.append(record)

    return ParsedBatch(records, {
        "parser": APPLICANT_PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "pages": 6,
        "page_rows": list(page_counts),
        "source_rows": len(rows),
        "public_records": len(records),
        "status_counts": {"pending": len(records)},
        "identifier_coverage": coverage,
        "raw_identifier_only": sum(raw_only.values()),
        "duplicate_structured_identifier_values": len(duplicates),
    })


PARSERS = {
    LISTED_PARSER_NAME: parse_lucca_listed,
    APPLICANT_PARSER_NAME: parse_lucca_applicants,
}
