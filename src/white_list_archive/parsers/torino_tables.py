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
_REFERENCE_DATE = "2026-09-11"

_LISTED_SOURCE_KEY = "torino-listed"
_APPLICANT_SOURCE_KEY = "torino-applicants"

_LISTED_SHA256 = "5c8341cd984de01f6472e049b9fa22569798ebc41761e6f85763796c8a90ba0d"
_APPLICANT_SHA256 = "f84d6da09090d557ba85cd216bc1e4962935f0f43ddb2614e77995b613ed2f51"
_LISTED_BYTES = 2967519
_APPLICANT_BYTES = 676216
_LISTED_PAGES = 37
_APPLICANT_PAGES = 7
_LISTED_RECORDS = 1501
_APPLICANT_RECORDS = 162

_LISTED_PAGE_COUNTS = (
    37, 42, 41, 40, 43, 38, 42, 40, 40, 41, 41, 40, 42, 40, 39, 41, 46, 42, 43,
    39, 42, 38, 39, 41, 40, 41, 43, 40, 41, 45, 42, 39, 43, 41, 42, 41, 26,
)
_APPLICANT_PAGE_COUNTS = (25, 27, 27, 26, 27, 27, 3)
_EXPECTED_LISTED_STATUS_COUNTS = {"listed": 1237, "renewal_update_in_progress": 264}
_EXPECTED_APPLICANT_STATUS_COUNTS = {"pending": 162}
_EXPECTED_LISTED_IDENTIFIER_COVERAGE = 1496
_EXPECTED_APPLICANT_IDENTIFIER_COVERAGE = 162
_EXPECTED_LISTED_APPLICATION_DATE_COVERAGE = 260
_EXPECTED_LISTED_LISTING_DATE_COVERAGE = 1500
_EXPECTED_LISTED_EXPIRY_DATE_COVERAGE = 1501

_RENEWAL_OUTCOME = "In corso istruttoria per rinnovo iscrizione"
_APPLICANT_OUTCOME = "In corso istruttoria per iscrizione"
_REVIEWED_NOTES = {
    "“iscrizione ai sensi dell’art.34 bis del d.lgs. n.159/2011”",
    '"iscrizione ai sensi dell’art. 94 bis d.lgs. 159/2011"',
}
_REVIEWED_ACTIVITY_TYPOGRAPHY = {
    "DUAL SRL": "I - III - V-VI-X",
    "EDIL VIO SAS": "I--II-III-V",
}
_REVIEWED_MALFORMED_LISTED_IDENTIFIER_FIELDS = {
    "BENA SNC": "0526550017",
    "CAL.E.S.A. SRL": "6197640011",
    "EDIL TRIVAL SRLS": "1228500019",
    "G.V. TRASPORTI DI GALVAGNO VITTORIO": "GLVVTR77S12L219-08560640016",
    "ORIGLIA SERGIO AZIENDA AGRICOLA": "RGLSRG67C31777X-07050560015",
    "PICCO BARTOLOMEO SRL": "1280650050",
    "SOCIETA’ COOPERATIVA EUROPA": "9800980014",
}

_LISTED_HEADER = (
    "Ragione sociale",
    "Sede legale",
    "Sede secondaria con rappresentanza stabile in Italia",
    "Codice Fiscale - Partita IVA",
    "Attività per cui è richiesta l'iscrizione",
    "Data di presentazione dell'istanza",
    "Esito",
    "Data di iscrizione",
    "Data di scadenza iscrizione",
    "Annotazioni",
)
_APPLICANT_HEADER = _LISTED_HEADER[:7]

_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_IDENTIFIER = re.compile(r"(?<![A-Z0-9])(?:\d{11}|[A-Z]{6}[0-9A-Z]{10})(?![A-Z0-9])")
_CANONICAL_ACTIVITY = re.compile(
    r"^(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI)(?:-(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI))*$"
)
_ALLOWED_SECTION_TOKENS = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_cfg(cfg: dict[str, Any], *, source_key: str, population_scope: str, sha256: str) -> None:
    expected = {
        "source_key": source_key,
        "authority_key": "torino",
        "population_scope": population_scope,
        "reference_date": _REFERENCE_DATE,
        "sha256": sha256,
    }
    for key, value in expected.items():
        if cfg.get(key) != value:
            raise RuntimeError(f"Torino configuration drift for {key}: {cfg.get(key)!r} != {value!r}")


def _validate_file(path: Path, *, source_key: str, sha256: str, byte_count: int) -> None:
    if path.stat().st_size != byte_count:
        raise RuntimeError(f"Torino byte-length drift for {source_key}: {path.stat().st_size} != {byte_count}")
    actual = _sha256(path)
    if actual != sha256:
        raise RuntimeError(f"Torino byte identity drift for {source_key}: {actual!r} != {sha256!r}")


def _strict_date(raw: str, *, source_key: str, locator: str, required: bool = False) -> str:
    value = _clean(raw)
    if not value:
        if required:
            raise RuntimeError(f"Torino required date is blank for {source_key} at {locator}")
        return ""
    if not _DATE.fullmatch(value):
        raise RuntimeError(f"Torino unreviewed date typography for {source_key} at {locator}: {value!r}")
    try:
        return datetime.strptime(value, "%d/%m/%Y").date().isoformat()
    except ValueError as exc:
        raise RuntimeError(f"Torino invalid calendar date for {source_key} at {locator}: {value!r}") from exc


def _strict_identifiers(raw: str) -> list[str]:
    value = _clean(raw).upper()
    return list(dict.fromkeys(_IDENTIFIER.findall(value)))


def _identifier_residue(raw: str) -> str:
    value = _clean(raw).upper()
    value = _IDENTIFIER.sub("", value)
    return re.sub(r"[\s/\-]+", "", value)


def _activities(raw: str, *, name: str, source_key: str, locator: str) -> list[str]:
    value = _clean(raw)
    if not value:
        raise RuntimeError(f"Torino blank activity field for {source_key} at {locator}")
    if not _CANONICAL_ACTIVITY.fullmatch(value):
        if _REVIEWED_ACTIVITY_TYPOGRAPHY.get(name) != value:
            raise RuntimeError(f"Torino unreviewed activity typography for {source_key} at {locator}: {value!r}")
    tokens = [part for part in re.split(r"\s*-+\s*", value) if part]
    if not tokens or any(token not in _ALLOWED_SECTION_TOKENS for token in tokens):
        raise RuntimeError(f"Torino unparsed activity field for {source_key} at {locator}: {value!r}")
    return [f"Sezione {token}" for token in tokens]


def _rows(path: Path, *, source_key: str, pages: int, page_counts: tuple[int, ...], header: tuple[str, ...]) -> list[tuple[int, int, list[str]]]:
    output: list[tuple[int, int, list[str]]] = []
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != pages:
            raise RuntimeError(f"Torino page-count drift for {source_key}: {len(pdf.pages)} != {pages}")
        observed_counts: list[int] = []
        for page_number, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if len(tables) != 1:
                raise RuntimeError(f"Torino table-count drift for {source_key} page {page_number}: {len(tables)}")
            rows = [[_clean(cell) for cell in row] for row in tables[0]]
            if page_number == 1:
                if not rows or tuple(rows[0]) != header:
                    raise RuntimeError(f"Torino header drift for {source_key}")
                rows = rows[1:]
            elif rows and tuple(rows[0]) == header:
                raise RuntimeError(f"Torino unexpected repeated header for {source_key} page {page_number}")
            if any(len(row) != len(header) for row in rows):
                raise RuntimeError(f"Torino column-width drift for {source_key} page {page_number}")
            observed_counts.append(len(rows))
            for row_number, row in enumerate(rows, 1):
                output.append((page_number, row_number, row))
    if tuple(observed_counts) != page_counts:
        raise RuntimeError(f"Torino per-page denominator drift for {source_key}: {tuple(observed_counts)!r} != {page_counts!r}")
    return output


def _validate_identifier_exceptions(records: list[dict[str, Any]]) -> None:
    observed: dict[str, str] = {}
    for record in records:
        raw = record["identifier_field_raw"]
        if raw and _identifier_residue(raw):
            observed[record["name"]] = raw
    if observed != _REVIEWED_MALFORMED_LISTED_IDENTIFIER_FIELDS:
        raise RuntimeError(f"Torino malformed identifier-field set drift: {observed!r}")


def parse_torino_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key=_LISTED_SOURCE_KEY, population_scope="listed", sha256=_LISTED_SHA256)
    _validate_file(path, source_key=_LISTED_SOURCE_KEY, sha256=_LISTED_SHA256, byte_count=_LISTED_BYTES)
    rows = _rows(
        path,
        source_key=_LISTED_SOURCE_KEY,
        pages=_LISTED_PAGES,
        page_counts=_LISTED_PAGE_COUNTS,
        header=_LISTED_HEADER,
    )
    records: list[dict[str, Any]] = []
    for ordinal, (page, row_number, row) in enumerate(rows, 1):
        name, office, secondary, identifier_raw, activity_raw, application_raw, outcome, listing_raw, expiry_raw, note = row
        locator = f"p{page}:r{row_number}"
        if not name or not office or not identifier_raw:
            raise RuntimeError(f"Torino required listed identity field is blank at {locator}")
        if outcome == "":
            status = "listed"
        elif outcome == _RENEWAL_OUTCOME:
            status = "renewal_update_in_progress"
        else:
            raise RuntimeError(f"Torino unreviewed listed outcome at {locator}: {outcome!r}")
        if note and note not in _REVIEWED_NOTES:
            raise RuntimeError(f"Torino unreviewed listed annotation at {locator}: {note!r}")
        application = _strict_date(application_raw, source_key=_LISTED_SOURCE_KEY, locator=locator)
        listing = _strict_date(listing_raw, source_key=_LISTED_SOURCE_KEY, locator=locator)
        expiry = _strict_date(expiry_raw, source_key=_LISTED_SOURCE_KEY, locator=locator, required=True)
        record = _record(
            cfg,
            ordinal,
            name=name,
            office=office,
            secondary=secondary,
            identifier_raw=identifier_raw,
            activities=_activities(activity_raw, name=name, source_key=_LISTED_SOURCE_KEY, locator=locator),
            status=status,
            outcome_raw=outcome,
            application_date=application,
            listing_date=listing,
            expiry_date=expiry,
            primary_date_label="Data iscrizione",
            source_fields={"physical_locator": locator, "notes": [note] if note else []},
        )
        record["identifiers"] = _strict_identifiers(identifier_raw)
        records.append(record)

    if len(records) != _LISTED_RECORDS:
        raise RuntimeError(f"Torino listed denominator drift: {len(records)} != {_LISTED_RECORDS}")
    statuses = dict(Counter(record["source_status"] for record in records))
    if statuses != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(f"Torino listed status drift: {statuses!r}")
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != _EXPECTED_LISTED_IDENTIFIER_COVERAGE:
        raise RuntimeError(f"Torino listed identifier coverage drift: {identifier_coverage}")
    _validate_identifier_exceptions(records)
    application_coverage = sum(bool(record["application_date"]) for record in records)
    listing_coverage = sum(bool(record["observed_listing_date"]) for record in records)
    expiry_coverage = sum(bool(record["observed_expiry_date"]) for record in records)
    expected_date_coverage = (
        _EXPECTED_LISTED_APPLICATION_DATE_COVERAGE,
        _EXPECTED_LISTED_LISTING_DATE_COVERAGE,
        _EXPECTED_LISTED_EXPIRY_DATE_COVERAGE,
    )
    if (application_coverage, listing_coverage, expiry_coverage) != expected_date_coverage:
        raise RuntimeError(
            "Torino listed date-coverage drift: "
            f"{(application_coverage, listing_coverage, expiry_coverage)!r} != {expected_date_coverage!r}"
        )
    note_counts = Counter(note for record in records for note in record["source_fields"]["notes"])
    if note_counts != Counter({
        "“iscrizione ai sensi dell’art.34 bis del d.lgs. n.159/2011”": 6,
        '"iscrizione ai sensi dell’art. 94 bis d.lgs. 159/2011"': 2,
    }):
        raise RuntimeError(f"Torino listed annotation denominator drift: {dict(note_counts)!r}")
    return ParsedBatch(records, {
        "parser": "torino_listed",
        "parser_version": PARSER_VERSION,
        "public_records": len(records),
        "status_counts": statuses,
        "identifier_coverage": identifier_coverage,
        "application_date_coverage": application_coverage,
        "listing_date_coverage": listing_coverage,
        "expiry_date_coverage": expiry_coverage,
        "reviewed_malformed_identifier_fields": len(_REVIEWED_MALFORMED_LISTED_IDENTIFIER_FIELDS),
        "reviewed_activity_typography": len(_REVIEWED_ACTIVITY_TYPOGRAPHY),
        "reviewed_annotations": sum(note_counts.values()),
    })


def parse_torino_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key=_APPLICANT_SOURCE_KEY, population_scope="applicant", sha256=_APPLICANT_SHA256)
    _validate_file(path, source_key=_APPLICANT_SOURCE_KEY, sha256=_APPLICANT_SHA256, byte_count=_APPLICANT_BYTES)
    rows = _rows(
        path,
        source_key=_APPLICANT_SOURCE_KEY,
        pages=_APPLICANT_PAGES,
        page_counts=_APPLICANT_PAGE_COUNTS,
        header=_APPLICANT_HEADER,
    )
    records: list[dict[str, Any]] = []
    for ordinal, (page, row_number, row) in enumerate(rows, 1):
        name, office, secondary, identifier_raw, activity_raw, application_raw, outcome = row
        locator = f"p{page}:r{row_number}"
        if not name or not office or not identifier_raw:
            raise RuntimeError(f"Torino required applicant identity field is blank at {locator}")
        if outcome != _APPLICANT_OUTCOME:
            raise RuntimeError(f"Torino unreviewed applicant outcome at {locator}: {outcome!r}")
        application = _strict_date(
            application_raw,
            source_key=_APPLICANT_SOURCE_KEY,
            locator=locator,
            required=True,
        )
        record = _record(
            cfg,
            ordinal,
            name=name,
            office=office,
            secondary=secondary,
            identifier_raw=identifier_raw,
            activities=_activities(activity_raw, name=name, source_key=_APPLICANT_SOURCE_KEY, locator=locator),
            status="pending",
            outcome_raw=outcome,
            application_date=application,
            primary_date_label="Data presentazione istanza",
            source_fields={"physical_locator": locator},
        )
        record["identifiers"] = _strict_identifiers(identifier_raw)
        records.append(record)

    if len(records) != _APPLICANT_RECORDS:
        raise RuntimeError(f"Torino applicant denominator drift: {len(records)} != {_APPLICANT_RECORDS}")
    statuses = dict(Counter(record["source_status"] for record in records))
    if statuses != _EXPECTED_APPLICANT_STATUS_COUNTS:
        raise RuntimeError(f"Torino applicant status drift: {statuses!r}")
    identifier_coverage = sum(bool(record["identifiers"]) for record in records)
    if identifier_coverage != _EXPECTED_APPLICANT_IDENTIFIER_COVERAGE:
        raise RuntimeError(f"Torino applicant identifier coverage drift: {identifier_coverage}")
    if any(_identifier_residue(record["identifier_field_raw"]) for record in records):
        raise RuntimeError("Torino applicant identifier-field residue detected")
    return ParsedBatch(records, {
        "parser": "torino_applicants",
        "parser_version": PARSER_VERSION,
        "public_records": len(records),
        "status_counts": statuses,
        "identifier_coverage": identifier_coverage,
        "application_date_coverage": sum(bool(record["application_date"]) for record in records),
    })
