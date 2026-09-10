from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_LISTED_PAGES = 110
_APPLICANT_PAGES = 9
_EXPECTED_LISTED_ROWS = 544
_EXPECTED_APPLICANT_ROWS = 57
_REFERENCE_DATE = "11/08/2026"
_DATE = re.compile(r"(?<!\d)(\d{2})/(\d{2})/(\d{4})(?!\d)")
_SECTION = re.compile(r"\bSEZ\s+([IVX]+)\s*[°º]?", re.I)


def _source_date(raw: str, *, field: str) -> str:
    value = _clean(raw)
    match = _DATE.fullmatch(value)
    if not match:
        raise ValueError(f"Ascoli Piceno {field} is not an exact source date: {raw!r}")
    day, month, year = map(int, match.groups())
    try:
        parsed = date(year, month, day)
    except ValueError as exc:
        raise ValueError(f"Ascoli Piceno {field} is not a valid calendar date: {raw!r}") from exc
    return parsed.isoformat()


def _document_text(path: Path, *, expected_pages: int, source_key: str) -> tuple[str, list[int]]:
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != expected_pages:
            raise RuntimeError(
                f"{source_key}: layout drift; expected {expected_pages} pages, got {len(pdf.pages)}"
            )
        for page in pdf.pages:
            pages.append(page.extract_text(x_tolerance=2, y_tolerance=3) or "")
    text = "\n".join(pages)
    if text.count(f"Aggiornato al {_REFERENCE_DATE}") != 1:
        raise RuntimeError(
            f"{source_key}: expected exactly one explicit Aggiornato al {_REFERENCE_DATE} marker"
        )
    return text, [len(page.splitlines()) for page in pages]


def _records(text: str, marker: str) -> list[str]:
    parts = re.split(rf"(?={re.escape(marker)})", text)
    return [part for part in parts if part.lstrip().startswith(marker)]


def _sections(activity_text: str, *, source_key: str, ordinal: int) -> tuple[list[str], str]:
    codes: list[str] = []
    for match in _SECTION.finditer(activity_text):
        code = match.group(1).upper()
        if code not in codes:
            codes.append(code)
    if not codes:
        raise RuntimeError(f"{source_key}:{ordinal}: no source-backed White List section found")
    raw = _clean(activity_text)
    if not raw:
        raise RuntimeError(f"{source_key}:{ordinal}: blank activity text")
    return [f"Sezione {code}" for code in codes], raw


def _listed_status(raw: str, *, ordinal: int) -> str:
    folded = _clean(raw).casefold()
    if folded == "iscritto":
        return "listed"
    if folded == "in aggiornamento":
        return "renewal_update_in_progress"
    raise RuntimeError(f"ascoli-piceno-listed:{ordinal}: unreviewed source status {raw!r}")


def _parse_listed_block(block: str, cfg: dict[str, Any], ordinal: int) -> dict[str, Any]:
    identity = re.search(
        r"^Ragione Sociale:\s*(.*?)\s+CODICE FISCALE:\s*([^\n]+)",
        block.lstrip(),
        re.S | re.I,
    )
    if not identity:
        raise RuntimeError(f"{cfg['source_key']}:{ordinal}: company identity boundary not recognised")
    name = _clean(identity.group(1))
    identifier_raw = _clean(identity.group(2))

    details = re.search(
        r"Indirizzo:\s*(.*?)\s+DATA PROVVEDIMENTO\s*-\s*(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})(.*?)STATO:\s*([^\n]+)",
        block,
        re.S | re.I,
    )
    if not details:
        raise RuntimeError(f"{cfg['source_key']}:{ordinal}: address/date/status boundary not recognised")
    office_head, decision_raw, expiry_raw, office_tail, status_raw = details.groups()
    office_tail = re.sub(r"\bSCADENZA:\s*", " ", office_tail, flags=re.I)
    office = _clean(f"{office_head} {office_tail}")
    if not name or not office or not identifier_raw:
        raise RuntimeError(f"{cfg['source_key']}:{ordinal}: required source identity field is blank")

    activity_match = re.search(r"Lista attività:\s*(.*)$", block, re.S | re.I)
    if not activity_match:
        raise RuntimeError(f"{cfg['source_key']}:{ordinal}: Lista attività boundary not recognised")
    activities, activities_raw = _sections(
        activity_match.group(1), source_key=cfg["source_key"], ordinal=ordinal
    )

    return _record(
        cfg,
        ordinal,
        name=name,
        office=office,
        identifier_raw=identifier_raw,
        activities=activities,
        status=_listed_status(status_raw, ordinal=ordinal),
        outcome_raw=_clean(status_raw),
        decision_date=_source_date(decision_raw, field="decision date"),
        expiry_date=_source_date(expiry_raw, field="expiry date"),
        primary_date_label="Data provvedimento",
        source_fields={
            "sections": [value.removeprefix("Sezione ") for value in activities],
            "registered_office_variants": [office],
            "requested_activities_source": activities_raw,
        },
    )


def parse_ascoli_piceno_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    text, page_line_counts = _document_text(
        path, expected_pages=_LISTED_PAGES, source_key=cfg["source_key"]
    )
    blocks = _records(text, "Ragione Sociale:")
    if len(blocks) != _EXPECTED_LISTED_ROWS:
        raise RuntimeError(
            f"{cfg['source_key']}: expected {_EXPECTED_LISTED_ROWS} source rows, got {len(blocks)}"
        )
    if text.count("CODICE FISCALE:") != _EXPECTED_LISTED_ROWS:
        raise RuntimeError(f"{cfg['source_key']}: identifier-label denominator drift")

    records = [_parse_listed_block(block, cfg, ordinal) for ordinal, block in enumerate(blocks, 1)]
    statuses = Counter(record["source_status"] for record in records)
    if statuses != Counter({"listed": 448, "renewal_update_in_progress": 96}):
        raise RuntimeError(f"{cfg['source_key']}: reviewed status denominator drift: {dict(statuses)}")
    diagnostics = {
        "parser": "ascoli_piceno_listed",
        "public_records": len(records),
        "status_counts": dict(statuses),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "identifier_raw_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "page_line_counts": page_line_counts,
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records, diagnostics)


def _parse_applicant_block(block: str, cfg: dict[str, Any], ordinal: int) -> dict[str, Any]:
    identity = re.search(
        r"^Azienda:\s*(.*?)\s+Sede legale:\s*(.*?)\s+Codice fiscale:\s*(.*?)\s+Data Presentazione Istanza:\s*(\d{2}/\d{2}/\d{4})",
        block.lstrip(),
        re.S | re.I,
    )
    if not identity:
        raise RuntimeError(f"{cfg['source_key']}:{ordinal}: applicant identity boundary not recognised")
    name, office, identifier_raw, application_raw = map(_clean, identity.groups())
    if not name or not office or not identifier_raw:
        raise RuntimeError(f"{cfg['source_key']}:{ordinal}: required applicant source field is blank")

    outcome_match = re.search(
        r"ESITO:\s*(.*?)\s+ESITO note aggiuntive:\s*(.*?)\s+Lista attività:\s*(.*)$",
        block,
        re.S | re.I,
    )
    if not outcome_match:
        raise RuntimeError(f"{cfg['source_key']}:{ordinal}: applicant outcome/activity boundary not recognised")
    outcome, additional_notes, activity_text = map(_clean, outcome_match.groups())
    if outcome.casefold() != "istruttoria":
        raise RuntimeError(f"{cfg['source_key']}:{ordinal}: unreviewed applicant outcome {outcome!r}")
    activities, activities_raw = _sections(
        activity_text, source_key=cfg["source_key"], ordinal=ordinal
    )
    outcome_raw = outcome if not additional_notes else f"{outcome}; note aggiuntive: {additional_notes}"

    return _record(
        cfg,
        ordinal,
        name=name,
        office=office,
        identifier_raw=identifier_raw,
        activities=activities,
        status="pending",
        outcome_raw=outcome_raw,
        application_date=_source_date(application_raw, field="application date"),
        primary_date_label="Data presentazione istanza",
        source_fields={
            "sections": [value.removeprefix("Sezione ") for value in activities],
            "registered_office_variants": [office],
            "requested_activities_source": activities_raw,
        },
    )


def parse_ascoli_piceno_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    text, page_line_counts = _document_text(
        path, expected_pages=_APPLICANT_PAGES, source_key=cfg["source_key"]
    )
    blocks = _records(text, "Azienda:")
    if len(blocks) != _EXPECTED_APPLICANT_ROWS:
        raise RuntimeError(
            f"{cfg['source_key']}: expected {_EXPECTED_APPLICANT_ROWS} source rows, got {len(blocks)}"
        )
    if len(re.findall(r"(?i)Codice fiscale:", text)) != _EXPECTED_APPLICANT_ROWS:
        raise RuntimeError(f"{cfg['source_key']}: applicant identifier-label denominator drift")

    records = [_parse_applicant_block(block, cfg, ordinal) for ordinal, block in enumerate(blocks, 1)]
    statuses = Counter(record["source_status"] for record in records)
    if statuses != Counter({"pending": 57}):
        raise RuntimeError(f"{cfg['source_key']}: reviewed applicant denominator drift: {dict(statuses)}")
    diagnostics = {
        "parser": "ascoli_piceno_applicants",
        "public_records": len(records),
        "status_counts": dict(statuses),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "identifier_raw_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "page_line_counts": page_line_counts,
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records, diagnostics)


PARSERS = {
    "ascoli_piceno_listed": parse_ascoli_piceno_listed,
    "ascoli_piceno_applicants": parse_ascoli_piceno_applicants,
}
