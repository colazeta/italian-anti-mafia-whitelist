from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import openpyxl

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-08-31"
_SOURCE_KEY = "sassari-combined"
_SHA256 = "e5cf9776971e4c0b46b97c56e2764f906bd07e3d573ac07b59fcd6605ab9c370"
_BYTE_COUNT = 123745
_RECORD_COUNT = 478
_EXPECTED_STATUS_COUNTS = {
    "listed": 335,
    "pending": 129,
    "renewal_update_in_progress": 12,
    "expired_observed": 1,
    "other_or_unknown": 1,
}
_EXPECTED_IDENTIFIER_COVERAGE = 472
_EXPECTED_RAW_IDENTIFIER_ONLY = 6
_EXPECTED_WORKSHEETS = ("Foglio1", "Foglio2", "Foglio3", "Foglio4")
_EXPECTED_TABLE_SHEET = "Foglio1"
_EXPECTED_HEADER_ROW = 7

_REVIEWED_MALFORMED_IDENTIFIER_FIELDS = {
    "COOPERATIVA SO.LI.DA. SOCIETA' COOPERATIVA SOCIALE": "0267999099",
    "CROCE SARDA BONORVA SOCIETA' COOPERATIVA SOCIALE ONLUS": "0247890903",
    "DE.SCA.RI DEL GEOM. CALIA GIANLUCA": "OLBIA",
    "MEDITERRANEA AMBIENTE SRL": "2517630907",
    "SACCU DAVIDE": "SCCDVD85RA192Y",
    "SOLIMAS SRL": "0233440906",
}
_REVIEWED_COLUMN_SWAP = {
    "DE.SCA.RI DEL GEOM. CALIA GIANLUCA": ("CLAGLC74B11E736M", "OLBIA"),
}
_REVIEWED_MALFORMED_APPLICATION_DATE = {
    "M.I.A. SRL": "129.01.2025",
}
_REVIEWED_NONSTANDARD_STATUSES = {
    "AAC COOPERATIVA SOCIALE": "other_or_unknown",
    "ROMANO FRANCA": "expired_observed",
}

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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_cfg(cfg: dict[str, Any]) -> None:
    expected = {
        "source_key": _SOURCE_KEY,
        "authority_key": "sassari",
        "population_scope": "listed_and_applicant",
        "reference_date": _REFERENCE_DATE,
        "sha256": _SHA256,
    }
    for key, value in expected.items():
        if cfg.get(key) != value:
            raise RuntimeError(f"Sassari configuration drift for {key}: {cfg.get(key)!r} != {value!r}")


def _validate_file(path: Path) -> None:
    if path.stat().st_size != _BYTE_COUNT:
        raise RuntimeError(f"Sassari byte-length drift: {path.stat().st_size} != {_BYTE_COUNT}")
    actual = _sha256(path)
    if actual != _SHA256:
        raise RuntimeError(f"Sassari byte identity drift: {actual!r} != {_SHA256!r}")


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
        raise ValueError(f"expected one audited Sassari header, found {len(matches)}")
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


def _select_table(workbook: Any) -> tuple[Any, list[tuple[Any, ...]], int, list[str]]:
    candidates: list[tuple[Any, list[tuple[Any, ...]], int, list[str]]] = []
    diagnostics: list[str] = []
    for worksheet in workbook.worksheets:
        rows = list(worksheet.iter_rows(values_only=True))
        try:
            header_index, header = _find_header(rows)
        except ValueError as exc:
            diagnostics.append(f"{worksheet.title}: {exc}")
            continue
        candidates.append((worksheet, rows, header_index, header))
    if len(candidates) != 1:
        detail = "; ".join(diagnostics)
        names = [candidate[0].title for candidate in candidates]
        raise ValueError(
            f"Sassari workbook changed: expected exactly one worksheet matching the audited schema, "
            f"found {len(candidates)} ({names}); non-matches: {detail}"
        )
    return candidates[0]


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


def _validate_reviewed_anomalies(records: list[dict[str, Any]]) -> None:
    malformed_ids = {
        record["name"]: record["identifier_field_raw"]
        for record in records
        if record["identifier_field_raw"] and not record["identifiers"]
    }
    if malformed_ids != _REVIEWED_MALFORMED_IDENTIFIER_FIELDS:
        raise RuntimeError(f"Sassari malformed identifier-field set drift: {malformed_ids!r}")

    swapped = {
        record["name"]: (record["registered_office"], record["identifier_field_raw"])
        for record in records
        if _is_identifier_like(record["registered_office"])
    }
    if swapped != _REVIEWED_COLUMN_SWAP:
        raise RuntimeError(f"Sassari reviewed column-swap set drift: {swapped!r}")

    malformed_dates = {
        record["name"]: record["source_fields"].get("application_date_raw", "")
        for record in records
        if record["source_fields"].get("application_date_raw") and not record["application_date"]
    }
    if malformed_dates != _REVIEWED_MALFORMED_APPLICATION_DATE:
        raise RuntimeError(f"Sassari malformed application-date set drift: {malformed_dates!r}")

    nonstandard = {
        record["name"]: record["source_status"]
        for record in records
        if record["source_status"] in {"expired_observed", "other_or_unknown"}
    }
    if nonstandard != _REVIEWED_NONSTANDARD_STATUSES:
        raise RuntimeError(f"Sassari nonstandard status set drift: {nonstandard!r}")


def parse_sassari_combined(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg)
    _validate_file(path)
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    worksheet, rows, header_index, header = _select_table(workbook)
    worksheet_names = tuple(sheet.title for sheet in workbook.worksheets)
    if worksheet_names != _EXPECTED_WORKSHEETS:
        raise RuntimeError(f"Sassari worksheet-name drift: {worksheet_names!r} != {_EXPECTED_WORKSHEETS!r}")
    if worksheet.title != _EXPECTED_TABLE_SHEET or header_index + 1 != _EXPECTED_HEADER_ROW:
        raise RuntimeError(
            f"Sassari table location drift: {(worksheet.title, header_index + 1)!r} != "
            f"{(_EXPECTED_TABLE_SHEET, _EXPECTED_HEADER_ROW)!r}"
        )
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
        notes: list[str] = []
        if note_raw:
            notes.append(f"NOTE: {note_raw}")
        if previous_expiry_raw:
            notes.append(f"SCADENZA ISCRIZIONE PRECEDENTE: {previous_expiry_raw}")
        marker_provenance = " | ".join(
            f"{label}={marker or '-'}" for label, marker in zip(activity_labels, activity_markers, strict=True)
        )
        source_fields = {
            "physical_locator": f"{worksheet.title}!{physical_row}",
            "application_date_raw": application_raw,
            "notes": notes,
            "requested_activities_source": marker_provenance,
        }

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

    if len(records) != _RECORD_COUNT or source_rows != _RECORD_COUNT:
        raise RuntimeError(f"Sassari denominator drift: records={len(records)}, source_rows={source_rows}, expected={_RECORD_COUNT}")
    statuses = dict(Counter(record["source_status"] for record in records))
    if statuses != _EXPECTED_STATUS_COUNTS:
        raise RuntimeError(f"Sassari status-count drift: {statuses!r} != {_EXPECTED_STATUS_COUNTS!r}")
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    raw_identifier_only = sum(bool(record["identifier_field_raw"]) and not record["identifiers"] for record in records)
    if identifier_coverage != _EXPECTED_IDENTIFIER_COVERAGE or raw_identifier_only != _EXPECTED_RAW_IDENTIFIER_ONLY:
        raise RuntimeError(
            f"Sassari identifier coverage drift: {(identifier_coverage, raw_identifier_only)!r} != "
            f"{(_EXPECTED_IDENTIFIER_COVERAGE, _EXPECTED_RAW_IDENTIFIER_ONLY)!r}"
        )
    if any((malformed_start_dates, malformed_expiry_dates, malformed_previous_expiry_dates)):
        raise RuntimeError(
            "Sassari unreviewed date anomaly: "
            f"start={malformed_start_dates}, expiry={malformed_expiry_dates}, previous_expiry={malformed_previous_expiry_dates}"
        )
    if malformed_application_dates != 1 or office_identifier_like != 1 or identifier_not_identifier_like != 6:
        raise RuntimeError(
            "Sassari reviewed anomaly denominator drift: "
            f"malformed_application={malformed_application_dates}, office_identifier_like={office_identifier_like}, "
            f"identifier_not_identifier_like={identifier_not_identifier_like}"
        )
    if len({record["record_locator"] for record in records}) != _RECORD_COUNT:
        raise RuntimeError("Sassari duplicate public observation locator")
    _validate_reviewed_anomalies(records)

    return ParsedBatch(
        records,
        {
            "parser": "sassari_combined",
            "workbook_sheet_count": len(workbook.worksheets),
            "worksheet_names": list(worksheet_names),
            "worksheet": worksheet.title,
            "header_row": header_index + 1,
            "source_rows": source_rows,
            "public_records": len(records),
            "status_counts": statuses,
            "identifier_coverage": identifier_coverage,
            "raw_identifier_only": raw_identifier_only,
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
