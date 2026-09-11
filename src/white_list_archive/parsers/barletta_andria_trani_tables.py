from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _clean, _record

PARSER_VERSION = "1"
_REFERENCE_DATE = "2026-09-11"
_LISTED_PAGES = 211
_APPLICANT_PAGES = 15
_EXPECTED_SECTION_MARKERS = (
    (1, "I"), (32, "II"), (44, "III"), (86, "IV"), (104, "V"),
    (145, "VI"), (174, "VII"), (177, "VIII"), (181, "IX"), (188, "X"),
)
_EXPECTED_SECTOR_COUNTS = {
    "I": 148, "II": 68, "III": 211, "IV": 84, "V": 205,
    "VI": 136, "VII": 8, "VIII": 12, "IX": 23, "X": 118,
}
_EXPECTED_SECTOR_ROWS = 1013
_EXPECTED_SECTOR_STATUS_COUNTS = Counter({"listed": 883, "renewal_update_in_progress": 130})
_EXPECTED_APPLICANTS = 81
_ROMAN_TO_NUMBER = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
}
_SECTION_RE = re.compile(r"\bSezione\s+([IVX]+)\b", re.I)
_STRICT_IDENTIFIER = re.compile(r"(?<![A-Za-z0-9])(?:\d{11}|[A-Za-z0-9]{16})(?![A-Za-z0-9])", re.I)
_VALID_DATE = re.compile(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{4})$")
_ACTIVITY_TOKEN = re.compile(r"\b(VIII|VII|VI|IV|IX|III|II|I|V|X)\b", re.I)
_REVIEWED_BAD_DATES = {
    "14/072026",
    "21/05/20259",
    "30/06 /2027",
    "17/11/20255",
    "17/07/202 6",
    "01/09/20267",
    "2/6/09/2025",
}
_REVIEWED_EMBEDDED_STATUS_DATE = "31/07/2026 Aggiornamento in corso"
_ADMIN_TOKENS = (
    "denominazio", "ragione sociale", "elenco fornitori", "elenco delle imprese",
    "p.i./cf", "iscrizione nelle white", "provvediment", "sezione",
)
_REVIEWED_APPLICANT_LEADING_CONTINUATIONS = {(11, "PETROLIFERI"), (13, "GREGORIO")}


def _strict_identifiers(text: str) -> list[str]:
    values: list[str] = []
    for match in _STRICT_IDENTIFIER.finditer(_clean(text)):
        value = match.group(0).upper()
        if value not in values:
            values.append(value)
    return values


def _parse_source_date(raw: str, *, source_key: str, page: int, row: int) -> str:
    value = _clean(raw)
    if not value:
        return ""
    if value == _REVIEWED_EMBEDDED_STATUS_DATE:
        value = "31/07/2026"
    match = _VALID_DATE.fullmatch(value)
    if match:
        day, month, year = map(int, match.groups())
        try:
            return date(year, month, day).isoformat()
        except ValueError as exc:
            raise RuntimeError(f"{source_key}: invalid calendar date at page {page} row {row}: {raw!r}") from exc
    if _clean(raw) in _REVIEWED_BAD_DATES:
        return ""
    raise RuntimeError(f"{source_key}: unreviewed date typography at page {page} row {row}: {raw!r}")


def _date_fields(row: list[str]) -> list[str]:
    values: list[str] = []
    for value in row[3:]:
        value = _clean(value)
        if not value:
            continue
        if _VALID_DATE.fullmatch(value) or value in _REVIEWED_BAD_DATES or value == _REVIEWED_EMBEDDED_STATUS_DATE:
            values.append(value)
    return values


def _is_admin(row: list[str]) -> bool:
    folded = " | ".join(row).casefold()
    return any(token in folded for token in _ADMIN_TOKENS)


def _is_repeated_artifact(row: list[str]) -> bool:
    nonempty = [_clean(value) for value in row if _clean(value)]
    return len(nonempty) >= 4 and len(set(nonempty)) == 1


def _identifier_raw(rows: list[list[str]]) -> str:
    parts: list[str] = []
    for row in rows:
        for value in row[2:]:
            value = _clean(value)
            if not value or value in _date_fields(row):
                continue
            folded = value.casefold().replace(" ", "")
            digit_count = sum(character.isdigit() for character in value)
            if (
                "p.iva" in folded or "p.iva" in folded.replace(".", "")
                or "c.f." in folded or "cod.fisc" in folded
                or _strict_identifiers(value) or digit_count >= 10
            ) and value not in parts:
                parts.append(value)
    return " · ".join(parts)


def _continuation_allowed(row: list[str]) -> bool:
    if not any(_clean(value) for value in row):
        return False
    if _is_admin(row) or _is_repeated_artifact(row):
        return False
    return len(" ".join(_clean(value) for value in row)) > 5


def _listed_candidate(row: list[str]) -> bool:
    if not row or not _clean(row[0]):
        return False
    dates = _date_fields(row)
    identifiers = _strict_identifiers(" | ".join(row[2:]))
    return bool((identifiers and dates) or len(dates) >= 2)


def _listed_sector_rows(path: Path, source_key: str) -> tuple[list[dict[str, Any]], tuple[tuple[int, str], ...]]:
    logical: list[dict[str, Any]] = []
    seen_markers: list[tuple[int, str]] = []
    current_section: str | None = None
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGES:
            raise RuntimeError(f"{source_key}: page-count drift; expected {_LISTED_PAGES}, got {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, 1):
            page_text = _clean(page.extract_text() or "")
            marker = _SECTION_RE.search(page_text)
            new_section = marker.group(1).upper() if marker else None
            if new_section:
                seen_markers.append((page_number, new_section))
            rows: list[list[str]] = []
            for table in page.find_tables():
                rows.extend([
                    [_clean(cell) for cell in raw]
                    for raw in (table.extract() or [])
                    if any(_clean(cell) for cell in raw)
                ])
            candidate_indices = [index for index, row in enumerate(rows) if _listed_candidate(row)]
            first_candidate = min(candidate_indices) if candidate_indices else None
            if logical and first_candidate is not None and (new_section is None or new_section == current_section):
                for row in rows[:first_candidate]:
                    if _continuation_allowed(row):
                        logical[-1]["continuations"].append(row)
            if new_section:
                current_section = new_section
            for index, row in enumerate(rows):
                if not _listed_candidate(row):
                    continue
                if current_section is None:
                    raise RuntimeError(f"{source_key}: missing section at page {page_number} row {index + 1}")
                item = {
                    "page": page_number,
                    "row": index + 1,
                    "section": current_section,
                    "base": row,
                    "continuations": [],
                }
                next_index = index + 1
                while next_index < len(rows) and not _listed_candidate(rows[next_index]):
                    if _continuation_allowed(rows[next_index]):
                        item["continuations"].append(rows[next_index])
                    next_index += 1
                logical.append(item)
    return logical, tuple(seen_markers)


def _row_name(item: dict[str, Any]) -> str:
    parts = [_clean(item["base"][0])]
    parts.extend(_clean(row[0]) for row in item["continuations"] if row and _clean(row[0]))
    return _clean(" ".join(parts))


def _row_office(item: dict[str, Any]) -> str:
    base = item["base"]
    parts = [_clean(base[1]) if len(base) > 1 else ""]
    parts.extend(_clean(row[1]) for row in item["continuations"] if len(row) > 1 and _clean(row[1]))
    return _clean(" ".join(parts))


def _semantic_date_key(raw: str, *, source_key: str, page: int, row: int) -> str:
    parsed = _parse_source_date(raw, source_key=source_key, page=page, row=row)
    return f"ISO:{parsed}" if parsed else f"RAW:{_clean(raw)}"


def parse_barletta_andria_trani_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"{cfg['source_key']}: unexpected reference date {cfg.get('reference_date')!r}")
    logical, markers = _listed_sector_rows(path, cfg["source_key"])
    if markers != _EXPECTED_SECTION_MARKERS:
        raise RuntimeError(f"{cfg['source_key']}: section-marker drift: {markers!r}")
    if len(logical) != _EXPECTED_SECTOR_ROWS:
        raise RuntimeError(f"{cfg['source_key']}: sector denominator drift; expected {_EXPECTED_SECTOR_ROWS}, got {len(logical)}")
    sector_counts = Counter(item["section"] for item in logical)
    if dict(sector_counts) != _EXPECTED_SECTOR_COUNTS:
        raise RuntimeError(f"{cfg['source_key']}: section denominator drift: {dict(sector_counts)}")

    reviewed: list[dict[str, Any]] = []
    malformed = Counter()
    for item in logical:
        source_rows = [item["base"], *item["continuations"]]
        raw_dates: list[str] = []
        for row in source_rows:
            for raw_date in _date_fields(row):
                if raw_date not in raw_dates:
                    raw_dates.append(raw_date)
        if not raw_dates:
            raise RuntimeError(
                f"{cfg['source_key']}: missing source date fields at page {item['page']} row {item['row']}"
            )
        note_raw = _clean(item["base"][-1]) if len(item["base"]) >= 8 else ""
        extra_note_dates = raw_dates[2:]
        if any(value not in note_raw for value in extra_note_dates):
            raise RuntimeError(
                f"{cfg['source_key']}: unreviewed extra source date at page {item['page']} row {item['row']}: {raw_dates!r}"
            )
        listing_raw = raw_dates[0]
        expiry_raw = raw_dates[1] if len(raw_dates) >= 2 else ""
        listing_date = _parse_source_date(listing_raw, source_key=cfg["source_key"], page=item["page"], row=item["row"])
        expiry_date = _parse_source_date(expiry_raw, source_key=cfg["source_key"], page=item["page"], row=item["row"]) if expiry_raw else ""
        for raw, parsed in ((listing_raw, listing_date), (expiry_raw, expiry_date)):
            if raw and not parsed:
                malformed[raw] += 1
        row_text = _clean(" ".join(" ".join(row) for row in source_rows))
        status = "renewal_update_in_progress" if ("aggiornamento" in row_text.casefold() or "aggiornament o" in row_text.casefold()) else "listed"
        identifier_raw = _identifier_raw(source_rows)
        identifiers = _strict_identifiers(identifier_raw)
        name = _row_name(item)
        if not name:
            raise RuntimeError(f"{cfg['source_key']}: unresolved legal name at page {item['page']} row {item['row']}")
        identity: tuple[Any, ...]
        if identifiers:
            identity = ("id", *sorted(identifiers))
        else:
            identity = ("name", name.casefold())
        date_key = (
            _semantic_date_key(listing_raw, source_key=cfg["source_key"], page=item["page"], row=item["row"]),
            _semantic_date_key(expiry_raw, source_key=cfg["source_key"], page=item["page"], row=item["row"]) if expiry_raw else "",
        )
        reviewed.append({
            "identity": identity,
            "group_key": (*identity, *date_key, status, note_raw.casefold()),
            "name": name,
            "office": _row_office(item),
            "identifier_raw": identifier_raw,
            "identifiers": identifiers,
            "listing_raw": listing_raw,
            "expiry_raw": expiry_raw,
            "listing_date": listing_date,
            "expiry_date": expiry_date,
            "status": status,
            "note_raw": note_raw,
            "section": item["section"],
            "page": item["page"],
            "row": item["row"],
        })

    sector_statuses = Counter(item["status"] for item in reviewed)
    if sector_statuses != _EXPECTED_SECTOR_STATUS_COUNTS:
        raise RuntimeError(f"{cfg['source_key']}: sector status drift: {dict(sector_statuses)}")

    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in reviewed:
        group = grouped.setdefault(item["group_key"], {
            "items": [], "sections": [], "identifiers": [],
            "listing_raw": [], "expiry_raw": [],
        })
        group["items"].append(item)
        if item["section"] not in group["sections"]:
            group["sections"].append(item["section"])
        for identifier in item["identifiers"]:
            if identifier not in group["identifiers"]:
                group["identifiers"].append(identifier)
        if item["listing_raw"] and item["listing_raw"] not in group["listing_raw"]:
            group["listing_raw"].append(item["listing_raw"])
        if item["expiry_raw"] and item["expiry_raw"] not in group["expiry_raw"]:
            group["expiry_raw"].append(item["expiry_raw"])

    records: list[dict[str, Any]] = []
    for ordinal, group in enumerate(grouped.values(), 1):
        items = group["items"]
        representative = items[0]
        name = max((item["name"] for item in items), key=len)
        office = max((item["office"] for item in items), key=len)
        identifier_raw = max((item["identifier_raw"] for item in items), key=len, default="")
        sections = [f"Sezione {_ROMAN_TO_NUMBER[roman]}" for roman in group["sections"]]
        source_fields = {
            "sections": sections,
            "listing_date_raw_variants": group["listing_raw"],
            "expiry_date_raw_variants": group["expiry_raw"],
            "in_aggiornamento": representative["note_raw"] if ("aggiornamento" in representative["note_raw"].casefold() or "aggiornament o" in representative["note_raw"].casefold()) else "",
        }
        record = _record(
            cfg,
            ordinal,
            name=name,
            office=office,
            identifier_raw=identifier_raw,
            activities=sections,
            status=representative["status"],
            outcome_raw=representative["note_raw"],
            listing_date=representative["listing_date"],
            expiry_date=representative["expiry_date"],
            primary_date_label="Data iscrizione" if representative["listing_date"] else "",
            source_fields=source_fields,
        )
        record["identifiers"] = group["identifiers"]
        records.append(record)

    statuses = Counter(record["source_status"] for record in records)
    return ParsedBatch(records, {
        "parser": "barletta_andria_trani_listed",
        "sector_rows": len(reviewed),
        "public_records": len(records),
        "sector_counts": dict(sector_counts),
        "sector_status_counts": dict(sector_statuses),
        "status_counts": dict(statuses),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "reviewed_malformed_dates": dict(malformed),
        "dropped_date_rows": 0,
    })


def _activity_sections(raw: str, *, source_key: str, page: int, row: int) -> list[str]:
    tokens: list[str] = []
    for match in _ACTIVITY_TOKEN.finditer(_clean(raw).upper()):
        token = match.group(1).upper()
        if token not in tokens:
            tokens.append(token)
    if not tokens:
        raise RuntimeError(f"{source_key}: unresolved applicant activity at page {page} row {row}: {raw!r}")
    return [f"Sezione {_ROMAN_TO_NUMBER[token]}" for token in tokens]


def _applicant_candidate(row: list[str]) -> bool:
    if not row or not _clean(row[0]):
        return False
    dates = [value for value in row[3:] if _VALID_DATE.fullmatch(_clean(value))]
    activity = any(_ACTIVITY_TOKEN.search(_clean(value).upper()) for value in row[3:])
    return len(dates) == 1 and activity


def parse_barletta_andria_trani_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(f"{cfg['source_key']}: unexpected reference date {cfg.get('reference_date')!r}")
    source_rows: list[dict[str, Any]] = []
    seen_leading: set[tuple[int, str]] = set()
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGES:
            raise RuntimeError(f"{cfg['source_key']}: page-count drift; expected {_APPLICANT_PAGES}, got {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, 1):
            rows: list[list[str]] = []
            for table in page.find_tables():
                rows.extend([
                    [_clean(cell) for cell in raw]
                    for raw in (table.extract() or [])
                    if any(_clean(cell) for cell in raw)
                ])
            candidate_indices = [index for index, row in enumerate(rows) if _applicant_candidate(row)]
            first_candidate = min(candidate_indices) if candidate_indices else None
            if source_rows and first_candidate is not None:
                for row in rows[:first_candidate]:
                    fragment = _clean(row[0]) if row else ""
                    if not fragment or _is_admin(row):
                        continue
                    key = (page_number, fragment)
                    if key not in _REVIEWED_APPLICANT_LEADING_CONTINUATIONS:
                        raise RuntimeError(f"{cfg['source_key']}: unreviewed leading continuation at page {page_number}: {row!r}")
                    source_rows[-1]["name"] = _clean(source_rows[-1]["name"] + " " + fragment)
                    seen_leading.add(key)
            for index, row in enumerate(rows):
                if not _applicant_candidate(row):
                    continue
                dates = [_clean(value) for value in row[3:] if _VALID_DATE.fullmatch(_clean(value))]
                application_raw = dates[0]
                application_date = _parse_source_date(application_raw, source_key=cfg["source_key"], page=page_number, row=index + 1)
                date_index = next(i for i, value in enumerate(row) if _clean(value) == application_raw)
                activity_candidates = [_clean(value) for value in row[3:date_index] if _ACTIVITY_TOKEN.search(_clean(value).upper())]
                if len(activity_candidates) != 1:
                    raise RuntimeError(
                        f"{cfg['source_key']}: expected one applicant activity field at page {page_number} row {index + 1}, got {activity_candidates!r}"
                    )
                activity_raw = activity_candidates[0]
                id_raw_parts = [
                    _clean(value) for value in row[2:date_index]
                    if _clean(value) and _clean(value) != activity_raw and (
                        _strict_identifiers(_clean(value))
                        or "p.iva" in _clean(value).casefold().replace(" ", "")
                        or "c.f." in _clean(value).casefold()
                        or sum(character.isdigit() for character in _clean(value)) >= 10
                    )
                ]
                identifier_raw = " · ".join(dict.fromkeys(id_raw_parts))
                source_rows.append({
                    "page": page_number,
                    "row": index + 1,
                    "name": _clean(row[0]),
                    "office": _clean(row[1]) if len(row) > 1 else "",
                    "identifier_raw": identifier_raw,
                    "identifiers": _strict_identifiers(identifier_raw),
                    "activity_raw": activity_raw,
                    "sections": _activity_sections(activity_raw, source_key=cfg["source_key"], page=page_number, row=index + 1),
                    "application_raw": application_raw,
                    "application_date": application_date,
                })
    if seen_leading != _REVIEWED_APPLICANT_LEADING_CONTINUATIONS:
        raise RuntimeError(f"{cfg['source_key']}: applicant continuation drift: {seen_leading!r}")
    if len(source_rows) != _EXPECTED_APPLICANTS:
        raise RuntimeError(f"{cfg['source_key']}: applicant denominator drift; expected {_EXPECTED_APPLICANTS}, got {len(source_rows)}")

    records: list[dict[str, Any]] = []
    for ordinal, item in enumerate(source_rows, 1):
        source_fields = {
            "sections": item["sections"],
            "application_date_raw_variants": [item["application_raw"]],
            "requested_activities_source": item["activity_raw"],
        }
        record = _record(
            cfg,
            ordinal,
            name=item["name"],
            office=item["office"],
            identifier_raw=item["identifier_raw"],
            activities=item["sections"],
            status="pending",
            outcome_raw="richiedente iscrizione",
            application_date=item["application_date"],
            primary_date_label="Data presentazione istanza",
            source_fields=source_fields,
        )
        record["identifiers"] = item["identifiers"]
        records.append(record)
    return ParsedBatch(records, {
        "parser": "barletta_andria_trani_applicants",
        "public_records": len(records),
        "status_counts": {"pending": len(records)},
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "dropped_date_rows": 0,
    })


PARSERS = {
    "barletta_andria_trani_listed": parse_barletta_andria_trani_listed,
    "barletta_andria_trani_applicants": parse_barletta_andria_trani_applicants,
}
