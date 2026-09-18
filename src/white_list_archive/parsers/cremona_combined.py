from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_NAME = "cremona_combined"
PARSER_VERSION = "1"
_SOURCE_KEY = "cremona-combined"
_AUTHORITY_KEY = "cremona"
_REFERENCE_DATE = "2026-09-18"
_EXPECTED_PAGES = 6
_EXPECTED_PAGE_ROWS = [32, 38, 36, 39, 37, 5]
_EXPECTED_RECORDS = 187
_EXPECTED_STATUS_COUNTS = {
    "listed": 99,
    "pending": 38,
    "renewal_update_in_progress": 50,
}
_EXPECTED_IDENTIFIER_KIND_COUNTS = {
    "strict_11_only": 165,
    "strict_11_plus_fiscal16": 18,
    "reviewed_malformed_numeric_only": 4,
}
_REVIEWED_MALFORMED_IDENTIFIERS = {
    11: "009226901930",
    19: "1168200192",
    63: "017747090193",
    90: "0136901033",
}
_SECTION_CODES = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")
_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_PENDING_MARKER = "ISCRITTO ELENCO RICHIEDENTI- IN ISTRUTTORIA"
_INITIAL_APPLICATION = re.compile(r"^FATTA ISTANZA IN DATA (\d{2}/\d{2}/\d{4})$", re.I)
_RENEWAL = re.compile(
    r"^FATTA ISTANZA A PER(?:MANERE|AMERE)(?: (?:(?:IN DATA|IL) )?(\d{2}/\d{2}/\d{4}))?$",
    re.I,
)


def _source_date(raw: str, *, field: str, ordinal: int) -> str:
    value = _clean(raw)
    if not value:
        return ""
    match = _DATE.fullmatch(value)
    if not match:
        raise RuntimeError(f"Cremona row {ordinal}: unsupported {field} date {raw!r}")
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError as exc:
        raise RuntimeError(f"Cremona row {ordinal}: invalid {field} date {raw!r}") from exc


def _identifier_kind(raw: str, ordinal: int) -> tuple[str, list[str]]:
    tokens = [re.sub(r"[^A-Za-z0-9]", "", item).upper() for item in str(raw or "").splitlines() if _clean(item)]
    strict = [item for item in tokens if item.isdigit() and len(item) == 11]
    fiscal = [item for item in tokens if len(item) == 16 and item.isalnum() and not item.isdigit()]
    malformed = [item for item in tokens if item not in strict and item not in fiscal]
    reviewed = _REVIEWED_MALFORMED_IDENTIFIERS.get(ordinal)
    if malformed:
        if len(tokens) != 1 or reviewed != malformed[0]:
            raise RuntimeError(f"Cremona row {ordinal}: unreviewed identifier token(s) {tokens!r}")
        return "reviewed_malformed_numeric_only", []
    if reviewed is not None:
        raise RuntimeError(f"Cremona row {ordinal}: reviewed malformed identifier changed from {reviewed!r}")
    if strict and fiscal and len(strict) == 1 and len(fiscal) == 1 and len(tokens) == 2:
        return "strict_11_plus_fiscal16", strict + fiscal
    if len(strict) == 1 and not fiscal and len(tokens) == 1:
        return "strict_11_only", strict
    raise RuntimeError(f"Cremona row {ordinal}: unsupported identifier structure {tokens!r}")


def _sections(cells: list[str], ordinal: int) -> list[str]:
    if len(cells) != 10:
        raise RuntimeError(f"Cremona row {ordinal}: expected ten section cells, got {len(cells)}")
    out: list[str] = []
    for code, raw in zip(_SECTION_CODES, cells, strict=True):
        value = _clean(raw)
        if value not in ("", "X", "x"):
            raise RuntimeError(f"Cremona row {ordinal}: unsupported section marker {raw!r}")
        if value:
            out.append(f"Sezione {code}")
    if not out:
        raise RuntimeError(f"Cremona row {ordinal}: no positively marked White List section")
    return out


def _status(note_raw: str, listing_raw: str, expiry_raw: str, ordinal: int) -> tuple[str, str, str]:
    note = _clean(note_raw)
    upper = note.upper()
    if bool(listing_raw) != bool(expiry_raw):
        raise RuntimeError(
            f"Cremona row {ordinal}: asymmetric listing/expiry fields {listing_raw!r} / {expiry_raw!r}"
        )
    if upper == _PENDING_MARKER:
        if listing_raw or expiry_raw:
            raise RuntimeError(f"Cremona row {ordinal}: applicant-in-istruttoria marker carries listing dates")
        return "pending", "", ""
    initial = _INITIAL_APPLICATION.fullmatch(upper)
    if initial:
        if listing_raw or expiry_raw:
            raise RuntimeError(f"Cremona row {ordinal}: initial-application marker carries listing dates")
        return "pending", initial.group(1), ""
    renewal = _RENEWAL.fullmatch(upper)
    if renewal:
        return "renewal_update_in_progress", "", renewal.group(1) or ""
    if note:
        raise RuntimeError(f"Cremona row {ordinal}: unsupported NOTE value {note_raw!r}")
    if listing_raw and expiry_raw:
        return "listed", "", ""
    raise RuntimeError(f"Cremona row {ordinal}: no positive status evidence")


def _validate_cfg(cfg: dict[str, Any]) -> None:
    if cfg.get("source_key") != _SOURCE_KEY:
        raise RuntimeError(f"Cremona parser/source mismatch: {cfg.get('source_key')!r} != {_SOURCE_KEY!r}")
    if cfg.get("authority_key") != _AUTHORITY_KEY:
        raise RuntimeError("Cremona parser bound to a non-Cremona authority")
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(
            f"Cremona reference-date drift: {cfg.get('reference_date')!r} != {_REFERENCE_DATE!r}"
        )


def _table_rows(path: Path) -> tuple[list[list[Any]], list[int]]:
    rows: list[list[Any]] = []
    page_rows: list[int] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _EXPECTED_PAGES:
            raise RuntimeError(f"Cremona page-count drift: {len(pdf.pages)} != {_EXPECTED_PAGES}")
        for page_number, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if len(tables) != 1:
                raise RuntimeError(f"Cremona page {page_number}: expected one table, found {len(tables)}")
            table = tables[0]
            if page_number == 1:
                if len(table) < 2:
                    raise RuntimeError("Cremona first-page table lost its two-row header")
                first = [_clean(cell) for cell in table[0]]
                second = [_clean(cell) for cell in table[1]]
                if first[:7] != ["N.", "Ragione Sociale", "Sede legale", "Codice Fiscale", "Data iscrizione", "", "N O T E"]:
                    raise RuntimeError(f"Cremona first header row drift: {first[:7]!r}")
                if second[:7] != ["", "", "", "Partita IVA", "", "", ""]:
                    raise RuntimeError(f"Cremona second header row drift: {second[:7]!r}")
                table = table[2:]
            data = [row for row in table if any(_clean(cell) for cell in row)]
            page_rows.append(len(data))
            rows.extend(data)
    return rows, page_rows


def parse_cremona_combined(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg)
    rows, page_rows = _table_rows(path)
    if page_rows != _EXPECTED_PAGE_ROWS:
        raise RuntimeError(f"Cremona page-row drift: {page_rows!r} != {_EXPECTED_PAGE_ROWS!r}")
    if len(rows) != _EXPECTED_RECORDS:
        raise RuntimeError(f"Cremona row-count drift: {len(rows)} != {_EXPECTED_RECORDS}")

    records: list[dict[str, Any]] = []
    statuses: Counter[str] = Counter()
    id_kinds: Counter[str] = Counter()
    for ordinal, row in enumerate(rows, 1):
        if len(row) != 17:
            raise RuntimeError(f"Cremona row {ordinal}: expected 17 table cells, got {len(row)}")
        number, name, office, identifier_raw, listing_raw, expiry_raw, note_raw, *section_cells = [
            _clean(cell) for cell in row
        ]
        if number != str(ordinal):
            raise RuntimeError(f"Cremona row sequence drift at ordinal {ordinal}: source number={number!r}")
        if not name or not office:
            raise RuntimeError(f"Cremona row {ordinal}: blank company name or legal-seat locality")

        id_kind, structured_identifiers = _identifier_kind(identifier_raw, ordinal)
        activities = _sections(section_cells, ordinal)
        status, application_raw, renewal_raw = _status(note_raw, listing_raw, expiry_raw, ordinal)
        listing_date = _source_date(listing_raw, field="listing", ordinal=ordinal)
        expiry_date = _source_date(expiry_raw, field="expiry", ordinal=ordinal)
        application_date = _source_date(application_raw, field="application", ordinal=ordinal)
        renewal_date = _source_date(renewal_raw, field="renewal-request", ordinal=ordinal)

        source_fields: dict[str, Any] = {
            "sections": [item.removeprefix("Sezione ") for item in activities],
            "registered_office_variants": [office],
            "listing_date_raw_variants": [listing_raw] if listing_raw else [],
            "expiry_date_raw_variants": [expiry_raw] if expiry_raw else [],
            "application_date_raw_variants": [application_raw] if application_raw else [],
            "normalised_listing_date_variants": [listing_date] if listing_date else [],
            "normalised_expiry_date_variants": [expiry_date] if expiry_date else [],
            "date_conflict_fields": [],
            "malformed_date_pairs": [],
            "requested_activities_source": " ".join(
                f"{index + 1}:{_clean(value) or '-'}" for index, value in enumerate(section_cells)
            ),
        }
        if status == "renewal_update_in_progress":
            source_fields["in_aggiornamento"] = note_raw
        source_fields["outcome"] = {
            "status": status,
            "observed_listing_date": listing_date,
            "observed_expiry_date": expiry_date,
            "renewal_requested": status == "renewal_update_in_progress",
            "update_in_progress": status == "renewal_update_in_progress",
            "dates": (
                [{"raw_value": renewal_raw, "date": renewal_date, "parenthesized": False}]
                if renewal_raw
                else []
            ),
        }

        record = _record(
            cfg,
            ordinal,
            name=name,
            office=office,
            identifier_raw=identifier_raw,
            activities=activities,
            status=status,
            outcome_raw=note_raw,
            application_date=application_date,
            listing_date=listing_date,
            expiry_date=expiry_date,
            primary_date_label="Data iscrizione" if listing_date else ("Data presentazione istanza" if application_date else ""),
            source_fields=source_fields,
        )
        record["identifiers"] = structured_identifiers
        records.append(record)
        statuses[status] += 1
        id_kinds[id_kind] += 1

    if dict(statuses) != _EXPECTED_STATUS_COUNTS:
        raise RuntimeError(f"Cremona status-count drift: {dict(statuses)!r} != {_EXPECTED_STATUS_COUNTS!r}")
    if dict(id_kinds) != _EXPECTED_IDENTIFIER_KIND_COUNTS:
        raise RuntimeError(
            f"Cremona identifier-kind drift: {dict(id_kinds)!r} != {_EXPECTED_IDENTIFIER_KIND_COUNTS!r}"
        )
    if sum(bool(record["identifiers"]) for record in records) != 183:
        raise RuntimeError("Cremona structured-identifier coverage drift")

    diagnostics = {
        "parser": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "pages": _EXPECTED_PAGES,
        "page_rows": page_rows,
        "source_rows": len(rows),
        "public_records": len(records),
        "status_counts": dict(statuses),
        "identifier_kind_counts": dict(id_kinds),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "reviewed_malformed_identifier_rows": sorted(_REVIEWED_MALFORMED_IDENTIFIERS),
    }
    return ParsedBatch(records, diagnostics)


PARSERS = {"cremona_combined": parse_cremona_combined}
