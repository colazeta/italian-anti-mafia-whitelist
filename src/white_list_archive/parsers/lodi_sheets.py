from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-09-15"
_LISTED_SHA256 = "ad64ab8669084bc31b80938a384b41849be4db28b448e9b2c0ce199f6af1d6ec"
_APPLICANT_SHA256 = "55aeab7e809cb90cc1ebd1ad9c1f08db78e91648a2c2e1a2b603188c77846228"

_LISTED_PHYSICAL_ROWS = 324
_LISTED_SOURCE_ROWS = 291
_LISTED_RECORDS = 169
_APPLICANT_PHYSICAL_ROWS = 8
_APPLICANT_RECORDS = 4

_EXPECTED_SECTION_ROWS = {
    "I": 44,
    "II": 24,
    "III": 47,
    "IV": 18,
    "V": 55,
    "VI": 54,
    "VII": 6,
    "VIII": 1,
    "IX": 3,
    "X": 39,
}
_EXPECTED_LISTED_SOURCE_STATUS_COUNTS = {
    "listed": 254,
    "renewal_update_in_progress": 37,
}
_EXPECTED_LISTED_STATUS_COUNTS = {
    "listed": 146,
    "renewal_update_in_progress": 23,
}
_EXPECTED_GROUP_OCCURRENCES = {1: 108, 2: 32, 3: 14, 4: 5, 5: 6, 6: 2, 7: 1, 8: 1}
_EXPECTED_APPLICANT_STATUS_COUNTS = {
    "rejected_or_denied": 2,
    "pending": 2,
}

_LISTED_SECTION_ROWS = {
    3: "I",
    50: "II",
    77: "III",
    127: "IV",
    148: "V",
    206: "VI",
    263: "VII",
    272: "VIII",
    276: "IX",
    283: "X",
}
_LISTED_ACTIVITY_ROWS = {row + 1 for row in _LISTED_SECTION_ROWS}
_LISTED_HEADER_ROWS = {row + 2 for row in _LISTED_SECTION_ROWS}
_LISTED_TITLE_ROWS = {1, 2}
_LISTED_BLANK_ROWS = {282}
_SECTION_ACTIVITY = {
    "I": "Estrazione, fornitura e trasporto di terra e materiali inerti",
    "II": "Confezionamento, fornitura e trasporto calcestruzzo e bitume",
    "III": "Nolo a freddo di macchinari",
    "IV": "Fornitura di ferro lavorato",
    "V": "Noli a caldo",
    "VI": "Autotrasporto per conto terzi",
    "VII": "Guardiania ai cantieri",
    "VIII": "Servizi funerari e cimiteriali",
    "IX": "Ristorazione, gestione delle mense e catering",
    "X": (
        "Servizi ambientali, comprese le attività di raccolta, di trasporto nazionale e "
        "transfrontaliero, anche per conto di terzi, di trattamento e di smaltimento dei "
        "rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi "
        "connessi alla gestione dei rifiuti"
    ),
}
_APPLICANT_TITLE_ROWS = {1, 2}
_APPLICANT_BLANK_ROWS = {3}
_APPLICANT_HEADER_ROWS = {4}

_STRICT_IDENTIFIER_11 = re.compile(r"^\d{11}$")
_STRICT_IDENTIFIER_16 = re.compile(r"^[A-Z0-9]{16}$")
_EMBEDDED_IDENTIFIER_11 = re.compile(r"(?<!\d)\d{11}(?!\d)")
_EMBEDDED_IDENTIFIER_16 = re.compile(r"\b[A-Z0-9]{16}\b")
_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_DENIAL = re.compile(
    r"^CHIUSA CON PROVV\. INTERDITTIVO DI DINIEGO DELL'ISCRIZIONE IN WHITE LIST IL (\d{2}/\d{2}/\d{4})$",
    re.I,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv(path: Path, *, expected_rows: int, label: str) -> list[tuple[str, ...]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = [tuple(_clean(cell) for cell in row) for row in csv.reader(handle)]
    if len(rows) != expected_rows:
        raise RuntimeError(f"Lodi {label} physical-row drift: {len(rows)} != {expected_rows}")
    widths = Counter(len(row) for row in rows)
    if widths != Counter({7: expected_rows}):
        raise RuntimeError(f"Lodi {label} row-width drift: {dict(widths)!r}")
    return rows


def _positive_identifiers(raw: str) -> list[str]:
    value = _clean(raw).upper()
    whole = re.sub(r"\s+", "", value)
    if _STRICT_IDENTIFIER_11.fullmatch(whole) or _STRICT_IDENTIFIER_16.fullmatch(whole):
        return [whole]
    values: list[str] = []
    for candidate in _EMBEDDED_IDENTIFIER_11.findall(value) + _EMBEDDED_IDENTIFIER_16.findall(value):
        candidate = candidate.upper()
        if candidate not in values:
            values.append(candidate)
    return values


def _calendar_date(raw: str, *, context: str) -> str:
    value = _clean(raw)
    if not _DATE.fullmatch(value):
        raise RuntimeError(f"Lodi unreviewed date typography ({context}): {value!r}")
    try:
        datetime.strptime(value, "%d/%m/%Y")
    except ValueError as exc:
        raise RuntimeError(f"Lodi invalid calendar date ({context}): {value!r}") from exc
    return value


def _validate_cfg(
    cfg: dict[str, Any],
    *,
    source_key: str,
    population_scope: str,
    sha256: str,
) -> None:
    expected = {
        "source_key": source_key,
        "authority_key": "lodi",
        "population_scope": population_scope,
        "reference_date": _REFERENCE_DATE,
        "sha256": sha256,
    }
    for key, value in expected.items():
        if cfg.get(key) != value:
            raise RuntimeError(
                f"Lodi configuration drift for {source_key}: {key}={cfg.get(key)!r} != {value!r}"
            )


def _listed_source_rows(path: Path) -> list[dict[str, Any]]:
    rows = _read_csv(path, expected_rows=_LISTED_PHYSICAL_ROWS, label="listed")
    source: list[dict[str, Any]] = []
    sections_seen: dict[int, str] = {}
    activities_seen: dict[str, str] = {}
    headers_seen: set[int] = set()
    titles_seen: set[int] = set()
    blanks_seen: set[int] = set()
    current_section = ""

    for row_number, cells in enumerate(rows, start=1):
        if row_number in _LISTED_TITLE_ROWS:
            if not cells[0] or any(cells[1:]):
                raise RuntimeError(f"Lodi listed title-row drift at row {row_number}: {cells!r}")
            titles_seen.add(row_number)
            continue
        if row_number in _LISTED_BLANK_ROWS:
            if any(cells):
                raise RuntimeError(f"Lodi listed reviewed blank row populated at {row_number}: {cells!r}")
            blanks_seen.add(row_number)
            continue
        if row_number in _LISTED_SECTION_ROWS:
            expected_section = _LISTED_SECTION_ROWS[row_number]
            nonblank = [_clean(value) for value in cells if _clean(value)]
            if nonblank != [f"Sezione {expected_section}"]:
                raise RuntimeError(f"Lodi listed section-row drift at {row_number}: {cells!r}")
            current_section = expected_section
            sections_seen[row_number] = current_section
            continue
        if row_number in _LISTED_ACTIVITY_ROWS:
            if not current_section:
                raise RuntimeError(f"Lodi activity row precedes section at {row_number}")
            nonblank = [_clean(value) for value in cells if _clean(value)]
            expected_activity = _SECTION_ACTIVITY[current_section]
            if nonblank != [expected_activity]:
                raise RuntimeError(
                    f"Lodi listed activity-label drift for section {current_section}: {nonblank!r}"
                )
            activities_seen[current_section] = expected_activity
            continue
        if row_number in _LISTED_HEADER_ROWS:
            if "ragione sociale" not in cells[0].casefold() or "data" not in cells[4].casefold():
                raise RuntimeError(f"Lodi listed table-header drift at {row_number}: {cells!r}")
            headers_seen.add(row_number)
            continue

        identifiers = _positive_identifiers(cells[3])
        if len(identifiers) != 1:
            raise RuntimeError(
                f"Lodi listed data row lacks exactly one positive identifier at {row_number}: {cells[3]!r}"
            )
        if not current_section:
            raise RuntimeError(f"Lodi listed data row precedes first section at {row_number}")
        listing = _calendar_date(cells[4], context=f"listed row {row_number} registration")
        expiry = _calendar_date(cells[5], context=f"listed row {row_number} expiry")
        if datetime.strptime(expiry, "%d/%m/%Y") < datetime.strptime(listing, "%d/%m/%Y"):
            raise RuntimeError(
                f"Lodi unreviewed listed chronology inversion at row {row_number}: {listing!r} -> {expiry!r}"
            )
        marker = _clean(cells[6])
        folded = marker.casefold()
        if not marker:
            status = "listed"
        elif folded.startswith("in aggiornamento"):
            status = "renewal_update_in_progress"
        else:
            raise RuntimeError(f"Lodi unreviewed listed status at row {row_number}: {marker!r}")
        source.append(
            {
                "row": row_number,
                "section": current_section,
                "cells": cells,
                "identifier": identifiers[0],
                "status": status,
            }
        )

    structural = {
        "titles": (titles_seen, _LISTED_TITLE_ROWS),
        "blank rows": (blanks_seen, _LISTED_BLANK_ROWS),
        "section rows": (sections_seen, _LISTED_SECTION_ROWS),
        "activity sections": (activities_seen, _SECTION_ACTIVITY),
        "headers": (headers_seen, _LISTED_HEADER_ROWS),
        "source rows": (len(source), _LISTED_SOURCE_ROWS),
        "section denominators": (
            dict(Counter(row["section"] for row in source)),
            _EXPECTED_SECTION_ROWS,
        ),
        "source status denominators": (
            dict(Counter(row["status"] for row in source)),
            _EXPECTED_LISTED_SOURCE_STATUS_COUNTS,
        ),
    }
    for label, (observed, expected) in structural.items():
        if observed != expected:
            raise RuntimeError(f"Lodi listed {label} drift: {observed!r} != {expected!r}")
    return source


def parse_lodi_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(
        cfg,
        source_key="lodi-listed",
        population_scope="listed",
        sha256=_LISTED_SHA256,
    )
    if _sha256(path) != _LISTED_SHA256:
        raise RuntimeError("Lodi listed source bytes drift from approved SHA-256")

    source = _listed_source_rows(path)
    groups: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in source:
        cells = row["cells"]
        key = (row["identifier"], cells[4], cells[5], row["status"])
        group = groups.setdefault(
            key,
            {
                "first": row,
                "sections": [],
                "memberships": [],
                "names": [],
                "offices": [],
                "secondary": [],
                "identifier_raw": [],
            },
        )
        if row["section"] not in group["sections"]:
            group["sections"].append(row["section"])
        for bucket, value in (
            ("names", cells[0]),
            ("offices", cells[1]),
            ("secondary", cells[2]),
            ("identifier_raw", cells[3]),
        ):
            if value not in group[bucket]:
                group[bucket].append(value)
        group["memberships"].append(
            {
                "source_row": row["row"],
                "section": row["section"],
                "name_raw": cells[0],
                "registered_office_raw": cells[1],
                "secondary_office_raw": cells[2],
                "identifier_raw": cells[3],
                "listing_date_raw": cells[4],
                "expiry_date_raw": cells[5],
                "update_raw": cells[6],
            }
        )

    if len(groups) != _LISTED_RECORDS:
        raise RuntimeError(f"Lodi listed grouped-record drift: {len(groups)} != {_LISTED_RECORDS}")
    occurrence_counts = dict(Counter(len(group["memberships"]) for group in groups.values()))
    if occurrence_counts != _EXPECTED_GROUP_OCCURRENCES:
        raise RuntimeError(f"Lodi listed group-occurrence drift: {occurrence_counts!r}")

    records: list[dict[str, Any]] = []
    for ordinal, group in enumerate(groups.values(), start=1):
        first = group["first"]
        cells = first["cells"]
        section_labels = [f"Sezione {section}" for section in group["sections"]]
        activities = [_SECTION_ACTIVITY[section] for section in group["sections"]]
        record = _record(
            cfg,
            ordinal,
            name=cells[0],
            office=cells[1],
            secondary=cells[2],
            identifier_raw=cells[3],
            activities=activities,
            status=first["status"],
            outcome_raw=cells[6],
            listing_date=cells[4],
            expiry_date=cells[5],
            primary_date_label="Data iscrizione",
            source_fields={
                "sections": section_labels,
                "source_memberships": group["memberships"],
                "name_variants": group["names"],
                "registered_office_variants": group["offices"],
                "secondary_office_variants": group["secondary"],
                "identifier_raw_variants": group["identifier_raw"],
                "listing_date_raw": cells[4],
                "expiry_date_raw": cells[5],
                "update_raw": cells[6],
            },
        )
        record["identifiers"] = [first["identifier"]]
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(f"Lodi listed public-status drift: {status_counts!r}")
    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "lodi_listed",
            "parser_version": PARSER_VERSION,
            "physical_rows": _LISTED_PHYSICAL_ROWS,
            "sector_rows": _LISTED_SOURCE_ROWS,
            "public_records": len(records),
            "source_status_counts": _EXPECTED_LISTED_SOURCE_STATUS_COUNTS,
            "status_counts": status_counts,
            "section_counts": _EXPECTED_SECTION_ROWS,
            "group_occurrence_counts": occurrence_counts,
        },
    )


def parse_lodi_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(
        cfg,
        source_key="lodi-applicants",
        population_scope="applicant",
        sha256=_APPLICANT_SHA256,
    )
    if _sha256(path) != _APPLICANT_SHA256:
        raise RuntimeError("Lodi applicant source bytes drift from approved SHA-256")

    rows = _read_csv(path, expected_rows=_APPLICANT_PHYSICAL_ROWS, label="applicant")
    records: list[dict[str, Any]] = []
    titles_seen: set[int] = set()
    blanks_seen: set[int] = set()
    headers_seen: set[int] = set()
    identifiers_seen: set[str] = set()

    for row_number, cells in enumerate(rows, start=1):
        if row_number in _APPLICANT_TITLE_ROWS:
            if not cells[0] or any(cells[1:]):
                raise RuntimeError(f"Lodi applicant title-row drift at {row_number}: {cells!r}")
            titles_seen.add(row_number)
            continue
        if row_number in _APPLICANT_BLANK_ROWS:
            if any(cells):
                raise RuntimeError(f"Lodi applicant reviewed blank row populated at {row_number}: {cells!r}")
            blanks_seen.add(row_number)
            continue
        if row_number in _APPLICANT_HEADER_ROWS:
            if "ragione sociale" not in cells[0].casefold() or "esito" not in cells[6].casefold():
                raise RuntimeError(f"Lodi applicant table-header drift at {row_number}: {cells!r}")
            headers_seen.add(row_number)
            continue

        identifiers = _positive_identifiers(cells[3])
        if len(identifiers) != 1:
            raise RuntimeError(
                f"Lodi applicant row lacks exactly one positive identifier at {row_number}: {cells[3]!r}"
            )
        identifier = identifiers[0]
        if identifier in identifiers_seen:
            raise RuntimeError(f"Lodi applicant identifier duplication drift at row {row_number}: {identifier}")
        identifiers_seen.add(identifier)
        application_date = _calendar_date(cells[5], context=f"applicant row {row_number} application")
        outcome = _clean(cells[6])
        decision_date = ""
        if outcome.casefold() == "in istruttoria":
            status = "pending"
        else:
            match = _DENIAL.fullmatch(outcome)
            if match is None:
                raise RuntimeError(f"Lodi unreviewed applicant outcome at row {row_number}: {outcome!r}")
            status = "rejected_or_denied"
            decision_date = _calendar_date(match.group(1), context=f"applicant row {row_number} decision")
            if datetime.strptime(decision_date, "%d/%m/%Y") < datetime.strptime(application_date, "%d/%m/%Y"):
                raise RuntimeError(f"Lodi applicant decision predates application at row {row_number}")

        record = _record(
            cfg,
            len(records) + 1,
            name=cells[0],
            office=cells[1],
            secondary=cells[2],
            identifier_raw=cells[3],
            activities=[cells[4]] if cells[4] else [],
            status=status,
            outcome_raw=outcome,
            application_date=application_date,
            decision_date=decision_date,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "source_row": row_number,
                "activities_raw": cells[4],
                "application_date_raw": cells[5],
                "outcome_raw": outcome,
            },
        )
        record["identifiers"] = [identifier]
        records.append(record)

    structural = {
        "titles": (titles_seen, _APPLICANT_TITLE_ROWS),
        "blank rows": (blanks_seen, _APPLICANT_BLANK_ROWS),
        "headers": (headers_seen, _APPLICANT_HEADER_ROWS),
        "records": (len(records), _APPLICANT_RECORDS),
        "identifier cardinality": (len(identifiers_seen), _APPLICANT_RECORDS),
    }
    for label, (observed, expected) in structural.items():
        if observed != expected:
            raise RuntimeError(f"Lodi applicant {label} drift: {observed!r} != {expected!r}")
    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_APPLICANT_STATUS_COUNTS:
        raise RuntimeError(f"Lodi applicant status drift: {status_counts!r}")
    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "lodi_applicants",
            "parser_version": PARSER_VERSION,
            "physical_rows": _APPLICANT_PHYSICAL_ROWS,
            "public_records": len(records),
            "status_counts": status_counts,
            "strict_identifier_records": len(identifiers_seen),
        },
    )


PARSERS = {
    "lodi_listed": parse_lodi_listed,
    "lodi_applicants": parse_lodi_applicants,
}
