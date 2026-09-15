from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-09-10"

_LISTED_SOURCE_KEY = "catanzaro-listed"
_APPLICANT_SOURCE_KEY = "catanzaro-applicants"

_LISTED_SHA256 = "8578a1b2d3ef0e2d71f1133381082d63d131182fd1b74c456cffe708ed94df7f"
_APPLICANT_SHA256 = "8c5b0ea684b20f0893016e4a528bac57fb2b05c40aa9669340bdf7bd7dab115c"
_LISTED_BYTES = 619398
_APPLICANT_BYTES = 338826
_LISTED_PAGES = 82
_APPLICANT_PAGES = 46

_EXPECTED_LISTED_SECTOR_ROWS = 1556
_EXPECTED_LISTED_RECORDS = 610
_EXPECTED_APPLICANT_RECORDS = 277
_EXPECTED_LISTED_STATUS_COUNTS = {"listed": 377, "renewal_update_in_progress": 233}
_EXPECTED_APPLICANT_STATUS_COUNTS = {"pending": 277}
_EXPECTED_LISTED_IDENTIFIER_COVERAGE = 601
_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE = 272
_EXPECTED_LISTED_SECTION_ROWS = {
    1: 254,
    2: 108,
    3: 394,
    4: 115,
    5: 388,
    6: 146,
    7: 1,
    8: 8,
    9: 18,
    10: 124,
}
_EXPECTED_LISTED_HEADERS = 82
_EXPECTED_APPLICANT_HEADERS = 43
_EXPECTED_APPLICANT_LAYOUT_MARKERS = 1
_EXPECTED_APPLICANT_BLANK_DATES = 2
_EXPECTED_APPLICANT_MALFORMED_DATES = 1

_SECTION = re.compile(r"\bsezione\s+(X|IX|VIII|VII|VI|V|IV|III|II|I|10|[1-9])\b", re.I)
_ROMAN = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
}
_STRICT_IDENTIFIER_11 = re.compile(r"^\d{11}$")
_STRICT_IDENTIFIER_16 = re.compile(r"^[A-Z0-9]{16}$")
_STRICT_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")

_REVIEWED_LISTING_DATE_RAW = {
    "x",
    "01/07/205",
    "12/03//2026",
    "05/0/05/2026",
    "06/08/206",
    "13/05/026",
}
_REVIEWED_EXPIRY_DATE_RAW = {
    "",
    "x",
    "03/082027",
    "06/08/207",
    "10/06/207",
    "17/112026",
    "30/03//2027",
    "03/092026",
    "18/12/026",
    "26/082026",
    "21/112026",
}
_REVIEWED_APPLICANT_DATE_RAW = {
    "",
    "1/8/12/2025",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_text(value: str) -> str:
    return _clean(unicodedata.normalize("NFKC", value or "")).casefold()


def _normalise_address(value: str) -> str:
    text = _normalise_text(value).replace("–", "-").replace("—", "-").replace("−", "-")
    text = re.sub(r"\s*([,;:/.-])\s*", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        value = _clean(value)
        if value not in out:
            out.append(value)
    return out


def _strict_identifiers(raw: str) -> list[str]:
    # pdfplumber can introduce whitespace inside a source identifier at a visual line wrap.
    # Removing whitespace is therefore a source-extraction normalisation only; punctuation is
    # not stripped to manufacture an identifier, and the raw field remains preserved.
    compact = re.sub(r"\s+", "", _clean(raw).upper()).lstrip("*")
    values: list[str] = []
    for token in re.split(r"[/;]", compact):
        token = token.strip("*.,:;-")
        if (_STRICT_IDENTIFIER_11.fullmatch(token) or _STRICT_IDENTIFIER_16.fullmatch(token)) and token not in values:
            values.append(token)
    return values


def _parse_date(raw: str, *, field: str) -> str:
    value = _clean(raw)
    reviewed = {
        "listing": _REVIEWED_LISTING_DATE_RAW,
        "expiry": _REVIEWED_EXPIRY_DATE_RAW,
        "applicant": _REVIEWED_APPLICANT_DATE_RAW,
    }[field]
    if value in reviewed:
        return ""
    if not _STRICT_DATE.fullmatch(value):
        raise RuntimeError(f"Catanzaro unreviewed {field} date typography: {value!r}")
    try:
        return datetime.strptime(value, "%d/%m/%Y").date().isoformat()
    except ValueError as exc:
        raise RuntimeError(f"Catanzaro invalid calendar {field} date: {value!r}") from exc


def _date_key(raw: str, parsed: str) -> str:
    return parsed or f"RAW:{_normalise_text(raw)}"


def _is_header(cells: list[str]) -> bool:
    folded = " | ".join(cells).casefold()
    return "ragione sociale" in folded and ("codice fiscale" in folded or "partita iva" in folded)


def _section_from_page(page: pdfplumber.page.Page, *, page_number: int) -> int:
    # Restrict section detection to the document heading so that references to a court
    # 'Sezione' inside company notes cannot change the current White List section.
    heading = page.crop((0, 0, page.width, min(page.height, 230))).extract_text() or ""
    hits = _SECTION.findall(heading)
    values: list[int] = []
    for hit in hits:
        value = int(hit) if hit.isdigit() else _ROMAN[hit.upper()]
        if value not in values:
            values.append(value)
    if len(values) != 1:
        raise RuntimeError(
            f"Catanzaro ambiguous/missing listed section on page {page_number}: {values!r} from {hits!r}"
        )
    return values[0]


def _validate_cfg(
    cfg: dict[str, Any],
    *,
    source_key: str,
    population_scope: str,
    sha256: str,
) -> None:
    if cfg.get("source_key") != source_key:
        raise RuntimeError(f"Catanzaro source-key drift: {cfg.get('source_key')!r} != {source_key!r}")
    if cfg.get("authority_key") != "catanzaro":
        raise RuntimeError("Catanzaro parser bound to a non-Catanzaro authority")
    if cfg.get("population_scope") != population_scope:
        raise RuntimeError(
            f"Catanzaro population-scope drift for {source_key}: "
            f"{cfg.get('population_scope')!r} != {population_scope!r}"
        )
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(
            f"Catanzaro reference-date drift for {source_key}: "
            f"{cfg.get('reference_date')!r} != {_REFERENCE_DATE!r}"
        )
    if cfg.get("sha256") != sha256:
        raise RuntimeError(
            f"Catanzaro configured SHA-256 drift for {source_key}: "
            f"{cfg.get('sha256')!r} != {sha256!r}"
        )


def _validate_file(path: Path, *, source_key: str, sha256: str, byte_count: int) -> None:
    actual_bytes = path.stat().st_size
    if actual_bytes != byte_count:
        raise RuntimeError(
            f"Catanzaro byte-length drift for {source_key}: {actual_bytes} != {byte_count}"
        )
    actual_sha = _sha256(path)
    if actual_sha != sha256:
        raise RuntimeError(
            f"Catanzaro byte identity drift for {source_key}: {actual_sha!r} != {sha256!r}"
        )


def _status(note: str) -> str:
    folded = _clean(note).casefold()
    if any(token in folded for token in ("rinnovo", "aggiornamento", "istruttoria")):
        return "renewal_update_in_progress"
    return "listed"


def parse_catanzaro_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(
        cfg,
        source_key=_LISTED_SOURCE_KEY,
        population_scope="listed",
        sha256=_LISTED_SHA256,
    )
    _validate_file(path, source_key=_LISTED_SOURCE_KEY, sha256=_LISTED_SHA256, byte_count=_LISTED_BYTES)

    sector_rows: list[dict[str, Any]] = []
    header_count = 0
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGES:
            raise RuntimeError(f"Catanzaro listed page-count drift: {len(pdf.pages)} != {_LISTED_PAGES}")
        for page_number, page in enumerate(pdf.pages, start=1):
            section = _section_from_page(page, page_number=page_number)
            tables = page.extract_tables() or []
            if len(tables) != 1:
                raise RuntimeError(
                    f"Catanzaro listed table-count drift p{page_number}: {len(tables)} != 1"
                )
            for row_number, row in enumerate(tables[0] or [], start=1):
                cells = [_clean(cell) for cell in row]
                if not any(cells):
                    continue
                if len(cells) != 7:
                    raise RuntimeError(
                        f"Catanzaro listed row-width drift p{page_number}:r{row_number}: {len(cells)} != 7"
                    )
                if _is_header(cells):
                    header_count += 1
                    continue
                if not cells[0]:
                    raise RuntimeError(
                        f"Catanzaro blank listed company p{page_number}:r{row_number}: {cells!r}"
                    )
                if not cells[3].startswith("*"):
                    raise RuntimeError(
                        f"Catanzaro unreviewed listed identifier marker p{page_number}:r{row_number}: {cells[3]!r}"
                    )
                listing_date = _parse_date(cells[4], field="listing")
                expiry_date = _parse_date(cells[5], field="expiry")
                sector_rows.append(
                    {
                        "page": page_number,
                        "row": row_number,
                        "locator": f"p{page_number}:r{row_number}",
                        "section": section,
                        "name": cells[0],
                        "office": cells[1],
                        "secondary": cells[2],
                        "identifier_raw": cells[3],
                        "listing_raw": cells[4],
                        "listing_date": listing_date,
                        "expiry_raw": cells[5],
                        "expiry_date": expiry_date,
                        "note": cells[6],
                        "status": _status(cells[6]),
                    }
                )

    if header_count != _EXPECTED_LISTED_HEADERS:
        raise RuntimeError(
            f"Catanzaro listed header-count drift: {header_count} != {_EXPECTED_LISTED_HEADERS}"
        )
    if len(sector_rows) != _EXPECTED_LISTED_SECTOR_ROWS:
        raise RuntimeError(
            f"Catanzaro listed sector-row drift: {len(sector_rows)} != {_EXPECTED_LISTED_SECTOR_ROWS}"
        )
    section_counts = dict(Counter(row["section"] for row in sector_rows))
    if section_counts != _EXPECTED_LISTED_SECTION_ROWS:
        raise RuntimeError(
            f"Catanzaro listed section-row drift: {section_counts!r} != {_EXPECTED_LISTED_SECTION_ROWS!r}"
        )

    grouped: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in sector_rows:
        key = (
            _normalise_text(row["name"]),
            _normalise_address(row["office"]),
            _normalise_address(row["secondary"]),
            _normalise_text(row["identifier_raw"]),
            _date_key(row["listing_raw"], row["listing_date"]),
            _date_key(row["expiry_raw"], row["expiry_date"]),
            row["status"],
        )
        group = grouped.setdefault(key, {"row": row, "sections": [], "rows": []})
        if row["section"] in group["sections"]:
            raise RuntimeError(
                "Catanzaro duplicate same-section observation after conservative normalisation: "
                f"{row['name']!r}, section {row['section']}"
            )
        group["sections"].append(row["section"])
        group["rows"].append(row)

    if len(grouped) != _EXPECTED_LISTED_RECORDS:
        raise RuntimeError(
            f"Catanzaro listed grouping drift: {len(grouped)} != {_EXPECTED_LISTED_RECORDS}"
        )

    records: list[dict[str, Any]] = []
    for group in grouped.values():
        row = group["row"]
        rows = group["rows"]
        sections = sorted(group["sections"])
        notes = _unique([item["note"] for item in rows if item["note"]])
        record = _record(
            cfg,
            len(records) + 1,
            name=row["name"],
            office=row["office"],
            secondary=row["secondary"],
            identifier_raw=row["identifier_raw"],
            activities=[f"Sezione {section}" for section in sections],
            status=row["status"],
            outcome_raw=" · ".join(notes),
            listing_date=row["listing_date"],
            expiry_date=row["expiry_date"],
            primary_date_label="Data iscrizione",
            source_fields={
                "sections": [f"Sezione {section}" for section in sections],
                "physical_locators": [item["locator"] for item in rows],
                "registered_office_variants": _unique([item["office"] for item in rows]),
                "secondary_office_variants": _unique([item["secondary"] for item in rows]),
                "listing_date_raw_variants": _unique([item["listing_raw"] for item in rows]),
                "expiry_date_raw_variants": _unique([item["expiry_raw"] for item in rows]),
                "notes": notes,
            },
        )
        record["identifiers"] = _strict_identifiers(row["identifier_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(
            f"Catanzaro listed grouped-status drift: {status_counts!r} != {_EXPECTED_LISTED_STATUS_COUNTS!r}"
        )
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != _EXPECTED_LISTED_IDENTIFIER_COVERAGE:
        raise RuntimeError(
            "Catanzaro listed identifier-coverage drift: "
            f"{identifier_coverage} != {_EXPECTED_LISTED_IDENTIFIER_COVERAGE}"
        )

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "catanzaro_listed",
            "parser_version": PARSER_VERSION,
            "source_pages": _LISTED_PAGES,
            "sector_rows": len(sector_rows),
            "section_rows": section_counts,
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_coverage": identifier_coverage,
        },
    )


def parse_catanzaro_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(
        cfg,
        source_key=_APPLICANT_SOURCE_KEY,
        population_scope="applicant",
        sha256=_APPLICANT_SHA256,
    )
    _validate_file(
        path,
        source_key=_APPLICANT_SOURCE_KEY,
        sha256=_APPLICANT_SHA256,
        byte_count=_APPLICANT_BYTES,
    )

    rows: list[dict[str, Any]] = []
    header_count = 0
    layout_markers = 0
    blank_dates = 0
    malformed_dates = 0
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGES:
            raise RuntimeError(
                f"Catanzaro applicant page-count drift: {len(pdf.pages)} != {_APPLICANT_PAGES}"
            )
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            if len(tables) != 1:
                raise RuntimeError(
                    f"Catanzaro applicant table-count drift p{page_number}: {len(tables)} != 1"
                )
            for row_number, row in enumerate(tables[0] or [], start=1):
                cells = [_clean(cell) for cell in row]
                if not any(cells):
                    continue
                if len(cells) != 5:
                    raise RuntimeError(
                        f"Catanzaro applicant row-width drift p{page_number}:r{row_number}: {len(cells)} != 5"
                    )
                if _is_header(cells):
                    header_count += 1
                    continue
                if cells == ["", "", "*", "", ""]:
                    layout_markers += 1
                    continue
                if not cells[0]:
                    raise RuntimeError(
                        f"Catanzaro blank applicant company p{page_number}:r{row_number}: {cells!r}"
                    )
                if not cells[2].startswith("*"):
                    raise RuntimeError(
                        f"Catanzaro unreviewed applicant identifier marker p{page_number}:r{row_number}: {cells[2]!r}"
                    )
                raw_date = cells[4]
                if not raw_date:
                    blank_dates += 1
                elif raw_date == "1/8/12/2025":
                    malformed_dates += 1
                application_date = _parse_date(raw_date, field="applicant")
                rows.append(
                    {
                        "page": page_number,
                        "row": row_number,
                        "locator": f"p{page_number}:r{row_number}",
                        "name": cells[0],
                        "office": cells[1],
                        "identifier_raw": cells[2],
                        "activities_raw": cells[3],
                        "application_raw": raw_date,
                        "application_date": application_date,
                    }
                )

    if header_count != _EXPECTED_APPLICANT_HEADERS:
        raise RuntimeError(
            f"Catanzaro applicant header-count drift: {header_count} != {_EXPECTED_APPLICANT_HEADERS}"
        )
    if layout_markers != _EXPECTED_APPLICANT_LAYOUT_MARKERS:
        raise RuntimeError(
            "Catanzaro applicant layout-marker drift: "
            f"{layout_markers} != {_EXPECTED_APPLICANT_LAYOUT_MARKERS}"
        )
    if len(rows) != _EXPECTED_APPLICANT_RECORDS:
        raise RuntimeError(
            f"Catanzaro applicant row drift: {len(rows)} != {_EXPECTED_APPLICANT_RECORDS}"
        )
    if blank_dates != _EXPECTED_APPLICANT_BLANK_DATES:
        raise RuntimeError(
            f"Catanzaro applicant blank-date drift: {blank_dates} != {_EXPECTED_APPLICANT_BLANK_DATES}"
        )
    if malformed_dates != _EXPECTED_APPLICANT_MALFORMED_DATES:
        raise RuntimeError(
            "Catanzaro applicant reviewed-malformed-date drift: "
            f"{malformed_dates} != {_EXPECTED_APPLICANT_MALFORMED_DATES}"
        )

    keys = [
        tuple(
            _normalise_text(value)
            for value in (
                row["name"],
                row["office"],
                row["identifier_raw"],
                row["activities_raw"],
                row["application_raw"],
            )
        )
        for row in rows
    ]
    if len(set(keys)) != len(keys):
        raise RuntimeError("Catanzaro duplicate reviewed applicant observation")

    records: list[dict[str, Any]] = []
    for row in rows:
        activities = [_clean(row["activities_raw"])] if _clean(row["activities_raw"]) else []
        record = _record(
            cfg,
            len(records) + 1,
            name=row["name"],
            office=row["office"],
            identifier_raw=row["identifier_raw"],
            activities=activities,
            status="pending",
            outcome_raw="",
            application_date=row["application_date"],
            primary_date_label="Data presentazione istanza",
            source_fields={
                "physical_locator": row["locator"],
                "application_date_raw": row["application_raw"],
                "requested_activities_source": row["activities_raw"],
            },
        )
        record["identifiers"] = _strict_identifiers(row["identifier_raw"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_APPLICANT_STATUS_COUNTS:
        raise RuntimeError(
            f"Catanzaro applicant status drift: {status_counts!r} != {_EXPECTED_APPLICANT_STATUS_COUNTS!r}"
        )
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE:
        raise RuntimeError(
            "Catanzaro applicant identifier-coverage drift: "
            f"{identifier_coverage} != {_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE}"
        )

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "catanzaro_applicants",
            "parser_version": PARSER_VERSION,
            "source_pages": _APPLICANT_PAGES,
            "public_records": len(records),
            "status_counts": status_counts,
            "identifier_coverage": identifier_coverage,
            "blank_application_dates": blank_dates,
            "reviewed_malformed_application_dates": malformed_dates,
            "excluded_layout_markers": layout_markers,
        },
    )


PARSERS = {
    "catanzaro_listed": parse_catanzaro_listed,
    "catanzaro_applicants": parse_catanzaro_applicants,
}
