from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import openpyxl

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record


_DATE = re.compile(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$")
_REQUEST_ENROLMENT = re.compile(r"^RICHIESTA\s+ISCRIZ(?:IONE|ONE)$", re.I)
_REQUEST_RENEWAL = re.compile(r"^RICHIESTA\s+PERMANENZA$", re.I)

_ACTIVITY_HEADER_TOKENS = (
    "terra e materiali inerti",
    "calcestruzzo",
    "noli a freddo",
    "ferro lavorato",
    "noli a caldo",
    "autotrasporto",
    "guardiania",
    "funerari",
    "ristorazione",
    "servizi ambientali",
)


def _source_date(value: Any) -> str:
    """Normalise only source-explicit valid dates; never repair source digits."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raw = _clean(value)
    match = _DATE.fullmatch(raw)
    if not match:
        return ""
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def _is_identifier_like(value: str) -> bool:
    token = re.sub(r"[^A-Za-z0-9]", "", _clean(value)).upper()
    return bool((token.isdigit() and len(token) == 11) or (len(token) == 16 and token.isalnum()))


def _find_header(rows: list[tuple[Any, ...]]) -> tuple[int, list[str]]:
    matches: list[tuple[int, list[str]]] = []
    for index, row in enumerate(rows[:25]):
        values = [_clean(value) for value in row]
        folded = [value.casefold() for value in values]
        if len(folded) >= 18 and folded[0] == "impresa" and folded[1] == "sede legale":
            if "codice fiscale" in folded[2] and "partita iva" in folded[2]:
                matches.append((index, values))
    if len(matches) != 1:
        raise ValueError(f"Sassari workbook header changed: expected one audited header, found {len(matches)}")
    index, header = matches[0]
    if len(header) < 18:
        raise ValueError("Sassari workbook header has fewer than 18 audited columns")

    activity_headers = [value.casefold() for value in header[3:13]]
    for token, value in zip(_ACTIVITY_HEADER_TOKENS, activity_headers, strict=True):
        if token not in value:
            raise ValueError(f"Sassari activity header changed: expected token {token!r} in {value!r}")
    required_tail = (
        "data presentazione istanza",
        "data inizio iscrizione o permanenza",
        "data scadenza iscrizione o permanenza",
        "note",
        "scadenza iscrizione precedente",
    )
    for expected, value in zip(required_tail, [v.casefold() for v in header[13:18]], strict=True):
        if expected not in value:
            raise ValueError(f"Sassari status/date header changed: expected {expected!r} in {value!r}")
    return index, header


def _status(start_raw: str, note_raw: str) -> str:
    start = _clean(start_raw)
    note = _clean(note_raw)
    if "scaduta" in note.casefold():
        return "expired_observed"
    if _REQUEST_RENEWAL.fullmatch(start) or "aggiornamento" in note.casefold():
        return "renewal_update_in_progress"
    if _REQUEST_ENROLMENT.fullmatch(start):
        return "pending"
    if _source_date(start):
        return "listed"
    return "other_or_unknown"


def parse_sassari_combined(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    if len(workbook.worksheets) != 1:
        raise ValueError(f"Sassari workbook changed: expected one worksheet, got {len(workbook.worksheets)}")
    worksheet = workbook.worksheets[0]
    rows = list(worksheet.iter_rows(values_only=True))
    header_index, header = _find_header(rows)
    activity_labels = [_clean(value) for value in header[3:13]]

    records: list[dict[str, Any]] = []
    malformed_application_dates = 0
    malformed_start_dates = 0
    malformed_expiry_dates = 0
    malformed_previous_expiry_dates = 0
    office_identifier_like = 0
    identifier_not_identifier_like = 0
    source_rows = 0

    for physical_row, raw_row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        values = list(raw_row) + [None] * max(0, 18 - len(raw_row))
        values = values[:18]
        cleaned = [_clean(value) for value in values]
        if not any(cleaned):
            continue
        name, office, identifier_raw = cleaned[:3]
        if not name:
            raise ValueError(f"Sassari row {physical_row} has content but no company name")
        source_rows += 1

        activity_markers = cleaned[3:13]
        activities: list[str] = []
        for label, marker in zip(activity_labels, activity_markers, strict=True):
            if not marker:
                continue
            if marker.casefold() != "x":
                raise ValueError(
                    f"Sassari row {physical_row} has an unaudited activity marker {marker!r} for {label!r}"
                )
            activities.append(label)
        if not activities:
            raise ValueError(f"Sassari row {physical_row} has no source-explicit activity marker")

        application_raw, start_raw, expiry_raw, note_raw, previous_expiry_raw = cleaned[13:18]
        application_date = _source_date(values[13])
        listing_date = _source_date(values[14])
        expiry_date = _source_date(values[15])
        previous_expiry_date = _source_date(values[17])
        status = _status(start_raw, note_raw)

        if application_raw and not application_date:
            malformed_application_dates += 1
        if start_raw and not listing_date and not _REQUEST_ENROLMENT.fullmatch(start_raw) and not _REQUEST_RENEWAL.fullmatch(start_raw):
            malformed_start_dates += 1
        if expiry_raw and not expiry_date:
            malformed_expiry_dates += 1
        if previous_expiry_raw and not previous_expiry_date:
            malformed_previous_expiry_dates += 1
        if _is_identifier_like(office):
            office_identifier_like += 1
        if identifier_raw and not _is_identifier_like(identifier_raw):
            identifier_not_identifier_like += 1

        outcome_parts = [part for part in (start_raw if not listing_date else "", note_raw) if part]
        source_fields = {
            "source_sheet": worksheet.title,
            "source_row_number": physical_row,
            "activity_markers": activity_markers,
            "application_date_raw": application_raw,
            "start_or_request_raw": start_raw,
            "expiry_date_raw": expiry_raw,
            "note_raw": note_raw,
            "previous_expiry_raw": previous_expiry_raw,
        }
        if previous_expiry_date:
            source_fields["previous_expiry_date"] = previous_expiry_date

        records.append(
            _record(
                cfg,
                len(records) + 1,
                name=name,
                office=office,
                identifier_raw=identifier_raw,
                activities=activities,
                status=status,
                outcome_raw=" | ".join(outcome_parts),
                application_date=application_date,
                listing_date=listing_date,
                expiry_date=expiry_date,
                primary_date_label=("Data iscrizione" if listing_date else "Data presentazione istanza"),
                source_fields=source_fields,
            )
        )

    if not records or len(records) != source_rows:
        raise ValueError("Sassari parser failed to preserve the complete non-empty source-row population")

    return ParsedBatch(
        records,
        {
            "parser": "sassari_combined",
            "worksheet": worksheet.title,
            "header_row": header_index + 1,
            "source_rows": source_rows,
            "public_records": len(records),
            "status_counts": dict(Counter(record["source_status"] for record in records)),
            "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
            "raw_identifier_only": sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records),
            "malformed_application_dates_preserved": malformed_application_dates,
            "malformed_start_dates_preserved": malformed_start_dates,
            "malformed_expiry_dates_preserved": malformed_expiry_dates,
            "malformed_previous_expiry_dates_preserved": malformed_previous_expiry_dates,
            "office_identifier_like_rows": office_identifier_like,
            "identifier_not_identifier_like_rows": identifier_not_identifier_like,
        },
    )


PARSERS: dict[str, Callable[[Path, dict[str, Any]], ParsedBatch]] = {
    "sassari_combined": parse_sassari_combined,
}
