from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

_LISTED_PAGES = 237
_APPLICANT_PAGES = 23
_LISTED_NOTES = Counter(
    {
        "": 96,
        "Istanza di mantenimento dell’iscrizione nella White List attualmente in istruttoria": 47,
        "Iscritta a seguito di istanza di mantenimento": 94,
    }
)
_APPLICANT_NOTES = Counter({"In Istruttoria": 23})
_LISTED_STATUS = Counter({"listed": 190, "renewal_update_in_progress": 47})
_APPLICANT_STATUS = Counter({"pending": 23})
_LISTED_SECTIONS = Counter(
    {"01": 94, "02": 35, "03": 99, "04": 33, "05": 98, "06": 78, "07": 4, "08": 4, "09": 7, "10": 76}
)
_APPLICANT_SECTIONS = Counter({"01": 5, "02": 2, "03": 6, "04": 6, "05": 6, "06": 10, "08": 1, "10": 5})
_EXPECTED_MALFORMED_LISTED_IDS = {"BNMGLC74C265C773P", "0226497056"}
_EXPECTED_LISTED_DUPLICATE_ACTIVITIES = ["96:05:Noli a caldo"]
_STRICT_ID = re.compile(r"^(?:\d{11}|[A-Z0-9]{16})$")
_DMY = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_SECTION = re.compile(
    r"\bSez\s+(\d{2})\s*-\s*(.*?)(?=(?:\n\s*Sez\s+\d{2}\s*-)|(?:\n\s*Ditta/Società\s+\d+\s+di\s+\d+)|\Z)",
    re.I | re.S,
)


def _words(page: Any) -> list[dict[str, Any]]:
    return page.extract_words(
        use_text_flow=False,
        keep_blank_chars=False,
        x_tolerance=1,
        y_tolerance=2,
    )


def _matching_words(words: list[dict[str, Any]], value: str) -> list[dict[str, Any]]:
    return [word for word in words if str(word["text"]).casefold() == value.casefold()]


def _unique(words: list[dict[str, Any]], value: str, page_number: int) -> dict[str, Any]:
    hits = _matching_words(words, value)
    if len(hits) != 1:
        raise RuntimeError(f"Viterbo page {page_number}: expected one {value!r} label, got {len(hits)}")
    return hits[0]


def _topmost(words: list[dict[str, Any]], value: str, page_number: int) -> dict[str, Any]:
    hits = _matching_words(words, value)
    if not hits:
        raise RuntimeError(f"Viterbo page {page_number}: missing {value!r} label")
    return min(hits, key=lambda word: float(word["top"]))


def _band(
    words: list[dict[str, Any]], *, x_min: float, x_max: float, y_min: float, y_max: float
) -> str:
    selected = [
        word
        for word in words
        if x_min <= float(word["x0"]) < x_max and y_min <= float(word["top"]) < y_max
    ]
    selected.sort(key=lambda word: (round(float(word["top"]), 1), float(word["x0"])))
    return _clean(" ".join(str(word["text"]) for word in selected))


def _activities(text: str, page_number: int) -> tuple[list[str], list[str], list[str]]:
    matches = list(_SECTION.finditer(text))
    if not matches:
        raise RuntimeError(f"Viterbo page {page_number}: no source activity sections found")
    sections: list[str] = []
    descriptions: list[str] = []
    by_section: dict[str, str] = {}
    duplicates: list[str] = []
    for match in matches:
        section = match.group(1)
        description = _clean(match.group(2))
        if not description:
            raise RuntimeError(f"Viterbo page {page_number}: empty section {section} description")
        if section in by_section:
            if by_section[section] != description:
                raise RuntimeError(
                    f"Viterbo page {page_number}: section {section} repeats with different text"
                )
            duplicates.append(f"{page_number}:{section}:{description}")
            continue
        by_section[section] = description
        sections.append(section)
        descriptions.append(f"Sez {section} - {description}")
    return sections, descriptions, duplicates


def _status(kind: str, note: str, page_number: int) -> str:
    if kind == "applicant":
        if note != "In Istruttoria":
            raise RuntimeError(f"Viterbo applicant page {page_number}: unapproved note {note!r}")
        return "pending"
    if not note or note == "Iscritta a seguito di istanza di mantenimento":
        return "listed"
    if note == "Istanza di mantenimento dell’iscrizione nella White List attualmente in istruttoria":
        return "renewal_update_in_progress"
    raise RuntimeError(f"Viterbo listed page {page_number}: unapproved note {note!r}")


def _parse(path: Path, cfg: dict[str, Any], kind: str) -> ParsedBatch:
    expected_pages = _LISTED_PAGES if kind == "listed" else _APPLICANT_PAGES
    records: list[dict[str, Any]] = []
    note_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    section_counts: Counter[str] = Counter()
    raw_ids: list[str] = []
    duplicate_activities: list[str] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != expected_pages:
            raise RuntimeError(f"Viterbo {kind}: expected {expected_pages} pages, got {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(layout=True, x_tolerance=1, y_tolerance=2) or ""
            marker = f"Ditta/Società {page_number} di {expected_pages}"
            if marker not in text:
                raise RuntimeError(f"Viterbo {kind}: source marker drift on page {page_number}")
            words = _words(page)
            ragione = _unique(words, "RagioneSociale", page_number)
            indirizzo = _unique(words, "Indirizzo", page_number)
            note_label = _unique(words, "Note", page_number)
            activity_label = _topmost(words, "Attività", page_number)
            if not (
                float(ragione["top"])
                < float(indirizzo["top"])
                < float(note_label["top"])
                < float(activity_label["top"])
            ):
                raise RuntimeError(f"Viterbo {kind}: label-order drift on page {page_number}")

            name = _band(
                words,
                x_min=float(ragione["x1"]) + 5,
                x_max=450.0,
                y_min=float(ragione["top"]) - 4,
                y_max=float(indirizzo["top"]) - 5,
            )
            office = _band(
                words,
                x_min=float(indirizzo["x1"]) + 5,
                x_max=450.0,
                y_min=float(indirizzo["top"]) - 4,
                y_max=float(activity_label["top"]) - 5,
            )
            note = _band(
                words,
                x_min=float(note_label["x1"]) + 5,
                x_max=835.0,
                y_min=float(note_label["top"]) - 4,
                y_max=float(activity_label["top"]) - 5,
            )
            if not name or not office:
                raise RuntimeError(f"Viterbo {kind}: incomplete identity fields on page {page_number}")

            id_match = re.search(
                r"Codice\s+Fiscale(?:\s+o\s+P\.I:|/pIVA)\s+([A-Z0-9]+)", text, re.I
            )
            if id_match is None:
                raise RuntimeError(f"Viterbo {kind}: identifier field unresolved on page {page_number}")
            identifier = _clean(id_match.group(1)).upper()
            raw_ids.append(identifier)

            sections, activities, page_duplicates = _activities(text, page_number)
            duplicate_activities.extend(page_duplicates)
            section_counts.update(sections)
            source_status = _status(kind, note, page_number)
            note_counts[note] += 1
            status_counts[source_status] += 1

            if kind == "listed":
                listing_match = re.search(
                    r"Data\s+Prima\s+Iscrizione\s+(\d{2}/\d{2}/\d{4})", text, re.I
                )
                expiry_match = re.search(r"Scadenza\s+(\d{2}/\d{2}/\d{4})", text, re.I)
                if listing_match is None or expiry_match is None:
                    raise RuntimeError(f"Viterbo listed: date field unresolved on page {page_number}")
                listing_raw = listing_match.group(1)
                expiry_raw = expiry_match.group(1)
                if not _DMY.fullmatch(listing_raw) or not _DMY.fullmatch(expiry_raw):
                    raise RuntimeError(f"Viterbo listed: date-shape drift on page {page_number}")
                record = _record(
                    cfg,
                    page_number,
                    name=name,
                    office=office,
                    identifier_raw=identifier,
                    activities=activities,
                    status=source_status,
                    outcome_raw=note,
                    listing_date=listing_raw,
                    expiry_date=expiry_raw,
                    primary_date_label="Data iscrizione",
                    source_fields={
                        "sections": [f"Sezione {section}" for section in sections],
                        "notes": [note] if note else [],
                        "listing_date_raw_variants": [listing_raw],
                        "expiry_date_raw_variants": [expiry_raw],
                    },
                )
            else:
                application_match = re.search(
                    r"Data\s+Richiesta\s+Iscrizione\s+(\d{2}/\d{2}/\d{4})", text, re.I
                )
                if application_match is None:
                    raise RuntimeError(
                        f"Viterbo applicant: application date unresolved on page {page_number}"
                    )
                application_raw = application_match.group(1)
                if not _DMY.fullmatch(application_raw):
                    raise RuntimeError(f"Viterbo applicant: date-shape drift on page {page_number}")
                record = _record(
                    cfg,
                    page_number,
                    name=name,
                    office=office,
                    identifier_raw=identifier,
                    activities=activities,
                    status=source_status,
                    outcome_raw=note,
                    application_date=application_raw,
                    primary_date_label="Data presentazione istanza",
                    source_fields={
                        "sections": [f"Sezione {section}" for section in sections],
                        "notes": [note],
                        "application_date_raw_variants": [application_raw],
                    },
                )
            records.append(record)

    expected_notes = _LISTED_NOTES if kind == "listed" else _APPLICANT_NOTES
    expected_status = _LISTED_STATUS if kind == "listed" else _APPLICANT_STATUS
    expected_sections = _LISTED_SECTIONS if kind == "listed" else _APPLICANT_SECTIONS
    expected_duplicates = _EXPECTED_LISTED_DUPLICATE_ACTIVITIES if kind == "listed" else []
    if note_counts != expected_notes:
        raise RuntimeError(f"Viterbo {kind}: note-count drift: {dict(note_counts)!r}")
    if status_counts != expected_status:
        raise RuntimeError(f"Viterbo {kind}: status-count drift: {dict(status_counts)!r}")
    if section_counts != expected_sections:
        raise RuntimeError(f"Viterbo {kind}: section-count drift: {dict(section_counts)!r}")
    if duplicate_activities != expected_duplicates:
        raise RuntimeError(
            f"Viterbo {kind}: duplicate-activity boundary drift: {duplicate_activities!r}"
        )
    duplicate_ids = [value for value, count in Counter(raw_ids).items() if value and count > 1]
    if duplicate_ids:
        raise RuntimeError(f"Viterbo {kind}: duplicate source identifiers: {duplicate_ids!r}")
    malformed = {value for value in raw_ids if not _STRICT_ID.fullmatch(value)}
    if kind == "listed" and malformed != _EXPECTED_MALFORMED_LISTED_IDS:
        raise RuntimeError(
            f"Viterbo listed: malformed identifier boundary drift: {sorted(malformed)!r}"
        )
    if kind == "applicant" and malformed:
        raise RuntimeError(
            f"Viterbo applicant: malformed identifier boundary drift: {sorted(malformed)!r}"
        )

    diagnostics = {
        "parser": f"viterbo_{kind}",
        "source_pages": expected_pages,
        "public_records": len(records),
        "status_counts": dict(status_counts),
        "note_counts": dict(note_counts),
        "section_counts": dict(section_counts),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "name_coverage": sum(bool(record["name"]) for record in records),
        "office_coverage": sum(bool(record["registered_office"]) for record in records),
        "activities_coverage": sum(bool(record["requested_activities"]) for record in records),
        "malformed_identifier_values": sorted(malformed),
        "duplicate_activity_rows": list(duplicate_activities),
    }
    expected_identifier_coverage = 235 if kind == "listed" else 23
    if len(records) != expected_pages or diagnostics["identifier_coverage"] != expected_identifier_coverage:
        raise RuntimeError(f"Viterbo {kind}: frozen record/identifier boundary drift: {diagnostics!r}")
    if diagnostics["name_coverage"] != expected_pages or diagnostics["office_coverage"] != expected_pages:
        raise RuntimeError(f"Viterbo {kind}: frozen identity coverage drift: {diagnostics!r}")
    if diagnostics["activities_coverage"] != expected_pages:
        raise RuntimeError(f"Viterbo {kind}: frozen activity coverage drift: {diagnostics!r}")
    return ParsedBatch(records, diagnostics)


def parse_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    return _parse(path, cfg, "listed")


def parse_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    return _parse(path, cfg, "applicant")


PARSERS = {
    "viterbo_listed": parse_listed,
    "viterbo_applicants": parse_applicants,
}
