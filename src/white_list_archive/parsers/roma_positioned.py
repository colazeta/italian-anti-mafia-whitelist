from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-09-14"

_LISTED_SHA256 = "8a2bbdb210757a8e7bf1da74db4bd7440c4fc45b3198b09e225c0aee2e6ef4af"
_APPLICANT_SHA256 = "9bf34641f92b7480492646f0ab442b47305438a06547e1739dafd324c2b1b32a"
_LISTED_BYTES = 498_221
_APPLICANT_BYTES = 405_505
_LISTED_PAGES = 168
_APPLICANT_PAGES = 142
_LISTED_RECORDS = 2_169
_APPLICANT_RECORDS = 2_259

_LISTED_EXPECTED_STATUS_COUNTS = {
    "listed": 1_215,
    "renewal_update_in_progress": 954,
}
_APPLICANT_EXPECTED_STATUS_COUNTS = {
    "pending": 2_256,
    "renewal_update_in_progress": 3,
}

_LISTED_UPDATE_NOTES = {
    "AAGIORNAMENTO IN CORSO",
    "AGGIONAMENTO IN CORSO",
    "AGGIORNAMENTO IN CORO",
    "AGGIORNAMENTO IN CORSO",
    "AGGIORNAMENTO N CORSO",
    "AGIORNAMENTO IN CORSO",
    "GGIORNAMENTO IN CORSO",
    "IMPRESA IN FASE DI AGGIORNAMENTO",
    "IN AGGIORNAMENTO",
    "SOCIETA' IN AGGIORNAMENTO",
    "SOCIETÀ IN AGGIORNAMENTO",
}
_LISTED_OTHER_NOTES = {
    "IN AMMINISTRAZIONE",
    "IN LIQUIDAZIONE (SENTENZA N. 47/2023 DEL 30/11/2023-DEP. 22/12/2023)",
    "ISCRIZIONE VALIDA FINO AL PERMANERE DEL CONTROLLO GIUDIZIARIO",
    "ISCRIZIONE VALIDA FINO AL PERMANERE DEL CONTROLLO GIUDIZIARIO.",
    "ISCRIZIONE VALIDA FINO AL PERMANERE DELLA MISURA DELL'AMMINISTRAZIONE GIUDIZIARIA",
    "L' ISCRIZIONE E' VALIDA FINO AL PERMANERE DELL'AMMINISTRAZIONE GIUDIZIARIA.",
    "SOCIETÀ SOTTOPOSTA AD AMMINISTRAZIONE GIUDIZIARIA.",
}
_APPLICANT_UPDATE_NOTES = {"AGGIORNAMENTO IN CORSO"}
_LISTED_HEADER_NOTE_CONTAMINATION = "NOTE"

_REVIEWED_BAD_LISTED_DATES = {"28/01/205", "27/07/202"}
_REVIEWED_BAD_APPLICANT_DATES = {"10/12/215", "23/04/201"}
_LISTED_MISSING_CORE_IDS = {
    "00873570949", "08346661005", "08907651007", "12841291003", "FRNPLG69L30H501X",
    "13402991007", "PNTCLD83M06L719O", "05831720585", "05181511006",
}
_APPLICANT_MISSING_DATE_IDS = {
    "13380281009", "02374570584", "05699041009", "12600491000", "13922751006",
    "14399531004", "03825471000", "07615910580", "03952130981", "02701320216",
    "03641991009", "05697241007", "13049561007", "04307540874", "17231581004",
    "16162251009", "08539360589", "14365631002", "NL001194082B01", "14065041007",
}

_ROMAN = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}
_LISTED_PSEUDO_IDS = {"SEZIONE", "DI LAVORI", "2013) C.F./P.I."}
_APPLICANT_PSEUDO_IDS = {"SEZIONE", "NELL’ELENCO DEI C.F./P.I."}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text_in_band(words: list[dict[str, Any]], x_min: float, x_max: float, y_min: float, y_max: float) -> str:
    selected = [
        word for word in words
        if x_min <= float(word["x0"]) < x_max and y_min <= float(word["top"]) < y_max
    ]
    selected.sort(key=lambda word: (float(word["top"]), float(word["x0"])))
    return _clean(" ".join(str(word["text"]) for word in selected))


def _aligned_identifier(words: list[dict[str, Any]], top: float) -> str:
    selected = [
        word for word in words
        if 325 <= float(word["x0"]) < 426 and abs(float(word["top"]) - top) <= 1.6
    ]
    selected.sort(key=lambda word: float(word["x0"]))
    return _clean(" ".join(str(word["text"]) for word in selected))


def _row_starts(words: list[dict[str, Any]], *, listed: bool) -> tuple[list[float], Counter[str]]:
    candidates: list[float] = []
    for word in words:
        if not (0 <= float(word["x0"]) < 168 and 55 < float(word["top"]) < 540):
            continue
        top = float(word["top"])
        if _aligned_identifier(words, top):
            candidates.append(top)

    clustered: list[float] = []
    for top in sorted(candidates):
        if not clustered or abs(top - clustered[-1]) > 2.0:
            clustered.append(top)

    pseudo = Counter()
    keep: list[float] = []
    pseudo_ids = _LISTED_PSEUDO_IDS if listed else _APPLICANT_PSEUDO_IDS
    for top in clustered:
        identifier = _aligned_identifier(words, top).upper()
        if identifier in pseudo_ids or identifier.startswith("C.F"):
            pseudo[identifier] += 1
        else:
            keep.append(top)
    return keep, pseudo


def _strict_date(raw: str, *, reviewed_bad: set[str], source_key: str, page: int, row: int) -> str:
    value = _clean(raw)
    if not value:
        return ""
    if value in reviewed_bad:
        return ""
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
        raise RuntimeError(f"{source_key}: unreviewed date typography at page {page} row {row}: {raw!r}")
    day, month, year = map(int, value.split("/"))
    try:
        return date(year, month, day).isoformat()
    except ValueError as exc:
        raise RuntimeError(f"{source_key}: invalid calendar date at page {page} row {row}: {raw!r}") from exc


def _sections(raw: str) -> list[str]:
    tokens = [token for token in re.findall(r"\b(?:VIII|VII|VI|IV|IX|III|II|I|V|X)\b", _clean(raw).upper()) if token in _ROMAN]
    return [f"Sezione {token}" for token in tokens]


def _validate_common(path: Path, cfg: dict[str, Any], *, sha: str, size: int) -> None:
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"{cfg['source_key']}: unexpected reference date {cfg.get('reference_date')!r}")
    if cfg.get("sha256") != sha:
        raise RuntimeError(f"{cfg['source_key']}: unapproved configured SHA-256 {cfg.get('sha256')!r}")
    if path.stat().st_size != size:
        raise RuntimeError(f"{cfg['source_key']}: byte-size drift; expected {size}, got {path.stat().st_size}")
    actual = _sha256(path)
    if actual != sha:
        raise RuntimeError(f"{cfg['source_key']}: content SHA-256 drift; expected {sha}, got {actual}")


def parse_roma_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_common(path, cfg, sha=_LISTED_SHA256, size=_LISTED_BYTES)
    records: list[dict[str, Any]] = []
    pseudo_total: Counter[str] = Counter()
    bad_dates: Counter[str] = Counter()
    missing_core: set[str] = set()
    reviewed_header_note_overlaps = 0

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGES:
            raise RuntimeError(f"{cfg['source_key']}: page-count drift; expected {_LISTED_PAGES}, got {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, 1):
            words = page.extract_words(x_tolerance=1, y_tolerance=2, keep_blank_chars=False, use_text_flow=False)
            starts, pseudo = _row_starts(words, listed=True)
            pseudo_total.update(pseudo)
            for index, top in enumerate(starts):
                y_min = top - 3
                y_max = starts[index + 1] - 3 if index + 1 < len(starts) else 540
                row_number = index + 1
                name = _text_in_band(words, 0, 168, y_min, y_max)
                office = _text_in_band(words, 168, 264, y_min, y_max)
                secondary = _text_in_band(words, 264, 325, y_min, y_max)
                identifier_raw = _text_in_band(words, 325, 426, y_min, y_max)
                listing_raw = _text_in_band(words, 426, 486, y_min, y_max)
                protocol_raw = _text_in_band(words, 486, 582, y_min, y_max)
                expiry_raw = _text_in_band(words, 582, 648, y_min, y_max)
                sections_raw = _text_in_band(words, 648, 723, y_min, y_max)
                note_raw = _text_in_band(words, 723, 850, y_min, y_max)
                reviewed_header_overlap = (
                    page_number == 1 and row_number == 1 and note_raw == _LISTED_HEADER_NOTE_CONTAMINATION
                )
                if reviewed_header_overlap:
                    reviewed_header_note_overlaps += 1
                    note = ""
                else:
                    note = note_raw
                if not name or not identifier_raw:
                    raise RuntimeError(
                        f"{cfg['source_key']}: unresolved name/identifier at page {page_number} row {row_number}: "
                        f"name={name!r}, identifier={identifier_raw!r}"
                    )
                if note and note not in _LISTED_UPDATE_NOTES and note not in _LISTED_OTHER_NOTES:
                    raise RuntimeError(
                        f"{cfg['source_key']}: unreviewed note at page {page_number} row {row_number}: "
                        f"{note!r}; name={name!r}; identifier={identifier_raw!r}"
                    )
                listing_date = _strict_date(
                    listing_raw, reviewed_bad=_REVIEWED_BAD_LISTED_DATES,
                    source_key=cfg["source_key"], page=page_number, row=row_number,
                )
                expiry_date = _strict_date(
                    expiry_raw, reviewed_bad=_REVIEWED_BAD_LISTED_DATES,
                    source_key=cfg["source_key"], page=page_number, row=row_number,
                )
                for raw, parsed in ((listing_raw, listing_date), (expiry_raw, expiry_date)):
                    if raw in _REVIEWED_BAD_LISTED_DATES and not parsed:
                        bad_dates[raw] += 1
                if not listing_raw and not protocol_raw and not expiry_raw:
                    missing_core.add(identifier_raw)
                updating = note in _LISTED_UPDATE_NOTES
                status = "renewal_update_in_progress" if updating else "listed"
                activities = _sections(sections_raw)
                records.append(_record(
                    cfg,
                    len(records) + 1,
                    name=name,
                    office=office,
                    secondary=secondary,
                    identifier_raw=identifier_raw,
                    activities=activities,
                    status=status,
                    outcome_raw=note,
                    listing_date=listing_date,
                    expiry_date=expiry_date,
                    primary_date_label="Data iscrizione" if listing_date else "",
                    source_fields={
                        "source_page": page_number,
                        "source_row_on_page": row_number,
                        "listing_date_raw": listing_raw,
                        "registration_protocol_raw": protocol_raw,
                        "expiry_date_raw": expiry_raw,
                        "sections_raw": sections_raw,
                        "note_raw": note_raw,
                        "reviewed_header_note_contamination": reviewed_header_overlap,
                    },
                ))

    if len(records) != _LISTED_RECORDS:
        raise RuntimeError(f"{cfg['source_key']}: denominator drift; expected {_LISTED_RECORDS}, got {len(records)}")
    if pseudo_total != Counter({"SEZIONE": 5, "DI LAVORI": 1, "2013) C.F./P.I.": 1}):
        raise RuntimeError(f"{cfg['source_key']}: reviewed header/legend geometry drift: {dict(pseudo_total)!r}")
    if reviewed_header_note_overlaps != 1:
        raise RuntimeError(
            f"{cfg['source_key']}: reviewed first-page NOTE overlap drift: {reviewed_header_note_overlaps}"
        )
    if bad_dates != Counter({"28/01/205": 1, "27/07/202": 1}):
        raise RuntimeError(f"{cfg['source_key']}: reviewed malformed-date set drift: {dict(bad_dates)!r}")
    if missing_core != _LISTED_MISSING_CORE_IDS:
        raise RuntimeError(f"{cfg['source_key']}: reviewed missing core-date/protocol set drift: {sorted(missing_core)!r}")
    status_counts = Counter(record["source_status"] for record in records)
    if dict(status_counts) != _LISTED_EXPECTED_STATUS_COUNTS:
        raise RuntimeError(f"{cfg['source_key']}: status-count drift: {dict(status_counts)!r}")
    return ParsedBatch(records, {
        "parser": "roma_positioned_listed",
        "public_records": len(records),
        "status_counts": dict(status_counts),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "identifier_raw_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "reviewed_malformed_dates": dict(bad_dates),
        "reviewed_missing_core_rows": len(missing_core),
        "reviewed_header_note_overlaps": reviewed_header_note_overlaps,
    })


def parse_roma_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_common(path, cfg, sha=_APPLICANT_SHA256, size=_APPLICANT_BYTES)
    records: list[dict[str, Any]] = []
    pseudo_total: Counter[str] = Counter()
    bad_dates: Counter[str] = Counter()
    missing_dates: set[str] = set()

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGES:
            raise RuntimeError(f"{cfg['source_key']}: page-count drift; expected {_APPLICANT_PAGES}, got {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, 1):
            words = page.extract_words(x_tolerance=1, y_tolerance=2, keep_blank_chars=False, use_text_flow=False)
            starts, pseudo = _row_starts(words, listed=False)
            pseudo_total.update(pseudo)
            for index, top in enumerate(starts):
                y_min = top - 3
                y_max = starts[index + 1] - 3 if index + 1 < len(starts) else 540
                row_number = index + 1
                name = _text_in_band(words, 0, 168, y_min, y_max)
                office = _text_in_band(words, 168, 264, y_min, y_max)
                secondary = _text_in_band(words, 264, 325, y_min, y_max)
                identifier_raw = _text_in_band(words, 325, 426, y_min, y_max)
                application_raw = _text_in_band(words, 426, 492, y_min, y_max)
                sections_raw = _text_in_band(words, 492, 564, y_min, y_max)
                note = _text_in_band(words, 564, 850, y_min, y_max)
                if not name or not identifier_raw:
                    raise RuntimeError(
                        f"{cfg['source_key']}: unresolved name/identifier at page {page_number} row {row_number}: "
                        f"name={name!r}, identifier={identifier_raw!r}"
                    )
                if note and note not in _APPLICANT_UPDATE_NOTES:
                    raise RuntimeError(
                        f"{cfg['source_key']}: unreviewed applicant note at page {page_number} row {row_number}: "
                        f"{note!r}; name={name!r}; identifier={identifier_raw!r}"
                    )
                application_date = _strict_date(
                    application_raw, reviewed_bad=_REVIEWED_BAD_APPLICANT_DATES,
                    source_key=cfg["source_key"], page=page_number, row=row_number,
                )
                if application_raw in _REVIEWED_BAD_APPLICANT_DATES and not application_date:
                    bad_dates[application_raw] += 1
                if not application_raw:
                    missing_dates.add(identifier_raw)
                updating = note in _APPLICANT_UPDATE_NOTES
                status = "renewal_update_in_progress" if updating else "pending"
                activities = _sections(sections_raw)
                records.append(_record(
                    cfg,
                    len(records) + 1,
                    name=name,
                    office=office,
                    secondary=secondary,
                    identifier_raw=identifier_raw,
                    activities=activities,
                    status=status,
                    outcome_raw=note,
                    application_date=application_date,
                    primary_date_label="Data presentazione istanza" if application_date else "",
                    source_fields={
                        "source_page": page_number,
                        "source_row_on_page": row_number,
                        "application_date_raw": application_raw,
                        "sections_raw": sections_raw,
                        "note_raw": note,
                    },
                ))

    if len(records) != _APPLICANT_RECORDS:
        raise RuntimeError(f"{cfg['source_key']}: denominator drift; expected {_APPLICANT_RECORDS}, got {len(records)}")
    if pseudo_total != Counter({"SEZIONE": 5, "NELL’ELENCO DEI C.F./P.I.": 1}):
        raise RuntimeError(f"{cfg['source_key']}: reviewed header/legend geometry drift: {dict(pseudo_total)!r}")
    if bad_dates != Counter({"10/12/215": 1, "23/04/201": 1}):
        raise RuntimeError(f"{cfg['source_key']}: reviewed malformed-date set drift: {dict(bad_dates)!r}")
    if missing_dates != _APPLICANT_MISSING_DATE_IDS:
        raise RuntimeError(f"{cfg['source_key']}: reviewed missing application-date set drift: {sorted(missing_dates)!r}")
    status_counts = Counter(record["source_status"] for record in records)
    if dict(status_counts) != _APPLICANT_EXPECTED_STATUS_COUNTS:
        raise RuntimeError(f"{cfg['source_key']}: status-count drift: {dict(status_counts)!r}")
    return ParsedBatch(records, {
        "parser": "roma_positioned_applicants",
        "public_records": len(records),
        "status_counts": dict(status_counts),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "identifier_raw_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "reviewed_malformed_dates": dict(bad_dates),
        "reviewed_missing_application_dates": len(missing_dates),
    })


PARSERS = {
    "roma_positioned_listed": parse_roma_listed,
    "roma_positioned_applicants": parse_roma_applicants,
}
