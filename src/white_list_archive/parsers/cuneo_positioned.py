from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import (
    ParsedBatch,
    _clean,
    _iso_date,
    _record,
)

_DATE_SLASH = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_DATE_DASH = re.compile(r"^\d{2}-\d{2}-\d{4}$")
_DOCUMENT_DATE = "martedì 15 settembre 2026"

_EXPECTED_LISTED_PAGE_ROWS = (
    2, 4, 4, 4, 4, 4, 3, 3, 3, 4, 4, 5, 4, 4, 2, 4, 3, 4, 2, 3, 3, 3, 3,
    4, 4, 3, 3, 4, 4, 3, 4, 4, 3, 3, 3, 2, 3, 3, 4, 4, 3, 3, 2, 3, 4, 2,
    4, 4, 3, 3, 3, 3, 4, 3, 3, 3, 3, 4, 4, 3, 4, 4, 4, 4, 4, 3, 4, 3, 3,
    3, 3, 3, 4, 4, 2, 4, 4, 3, 4, 2, 4, 4, 3, 3, 3, 4, 4, 4, 3, 4, 4, 4,
    4, 4, 4, 4, 3, 4, 3, 4, 4, 2, 4, 4, 2, 4, 3, 2, 4, 3, 3, 3, 3, 3, 2,
    3, 3, 3, 4, 4, 4, 4, 3, 4, 3, 3, 3, 4, 4, 4, 3, 5, 3, 3, 4, 3, 4,
)
_EXPECTED_APPLICANT_PAGE_ROWS = (5, 5, 4, 4, 5, 2, 3, 7, 2, 5, 2, 3, 1)
_EXPECTED_LISTED_STATUS = Counter(
    {
        "Iscritta": 398,
        "iscritta": 3,
        "Iscritto": 1,
        "Aggiornamento in corso": 64,
        "Aggiornamnto in corso": 1,
        "Aggiornamento in corso- Sottoposta a contr": 1,
    }
)
_EXPECTED_MALFORMED_IDENTIFIERS = {
    12: "0288370045",
    19: "0112458806",
    54: "0380870043",
    176: "0355860044",
    184: "027874310043",
    258: "0173970418",
    259: "0119734223",
    285: "0284720041",
    290: "033343570044",
    326: "0329755042",
    348: "0292930040",
}
_EXPECTED_DUPLICATE_STRICT_IDENTIFIERS = {
    "03491860049": 2,
    "02712230040": 2,
}


@dataclass
class _Line:
    page: int
    top: float
    bottom: float
    words: list[dict[str, Any]]
    text: str
    pos: int = -1


def _centre(word: dict[str, Any]) -> float:
    return (float(word["x0"]) + float(word["x1"])) / 2.0


def _lines(path: Path) -> tuple[list[_Line], list[str]]:
    lines: list[_Line] = []
    page_texts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_texts.append((page.extract_text() or "").casefold())
            words = page.extract_words(
                use_text_flow=False,
                keep_blank_chars=False,
                x_tolerance=2,
                y_tolerance=3,
            )
            groups: dict[int, list[dict[str, Any]]] = {}
            for word in words:
                groups.setdefault(round(float(word["top"]) / 3.0), []).append(word)
            for _key, group in sorted(groups.items()):
                group = sorted(group, key=lambda item: float(item["x0"]))
                lines.append(
                    _Line(
                        page=page_number,
                        top=min(float(item["top"]) for item in group),
                        bottom=max(float(item["bottom"]) for item in group),
                        words=group,
                        text=_clean(" ".join(str(item["text"]) for item in group)),
                    )
                )
    for pos, line in enumerate(lines):
        line.pos = pos
    return lines, page_texts


def _band(line: _Line, x_min: float, x_max: float) -> str:
    return _clean(
        " ".join(
            str(word["text"])
            for word in line.words
            if x_min <= _centre(word) < x_max
        )
    )


def _activity_text(lines: list[_Line], start: int, end: int, *, x_min: float, x_max: float) -> str:
    chunks: list[str] = []
    for line in lines[start:end]:
        text = _band(line, x_min, x_max)
        if not text:
            continue
        folded = text.casefold()
        if (
            folded.startswith("ministero dell")
            or folded.startswith("prefettura")
            or folded.startswith("elenco ")
            or folded.startswith("aggiornato al")
            or folded.startswith("martedì ")
            or folded.startswith("pagina ")
            or folded.startswith("ragione sociale")
            or folded == "attività"
        ):
            continue
        chunks.append(text)
    value = _clean(" ".join(chunks)).replace("(cid:9)", "")
    value = _clean(re.sub(r"\s+Attività$", "", value))
    return value


def _source_date(value: str) -> str:
    return _iso_date(_clean(value).replace("-", "/"))


def _listed_status(raw: str) -> str:
    if raw in {"Iscritta", "iscritta", "Iscritto"}:
        return "listed"
    if raw in {
        "Aggiornamento in corso",
        "Aggiornamnto in corso",
        "Aggiornamento in corso- Sottoposta a contr",
    }:
        return "renewal_update_in_progress"
    raise RuntimeError(f"cuneo_listed: unapproved source status {raw!r}")


def _ordered_unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def parse_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    lines, page_texts = _lines(path)
    if len(page_texts) != 137:
        raise RuntimeError(f"cuneo_listed: expected 137 pages, got {len(page_texts)}")
    if any(_DOCUMENT_DATE not in text for text in page_texts):
        raise RuntimeError("cuneo_listed: approved 15 September 2026 document marker missing")

    headers = [
        line
        for line in lines
        if "Ragione Sociale" in line.text
        and "Sede legale" in line.text
        and "Codice fiscale" in line.text
    ]
    statuses = [
        line for line in lines if "Attività" in line.text and "Data di iscrizione" in line.text
    ]
    page_rows = [sum(header.page == page for header in headers) for page in range(1, 138)]
    if tuple(page_rows) != _EXPECTED_LISTED_PAGE_ROWS:
        raise RuntimeError(f"cuneo_listed: page denominator drift: {page_rows}")
    if len(headers) != 468 or len(statuses) != 468:
        raise RuntimeError(
            f"cuneo_listed: expected 468 company/status headers, got {len(headers)}/{len(statuses)}"
        )

    raw_statuses = Counter(_band(line, 280.0, 575.0) for line in statuses)
    if raw_statuses != _EXPECTED_LISTED_STATUS:
        raise RuntimeError(f"cuneo_listed: source status vocabulary drift: {dict(raw_statuses)}")

    date_lines = [
        line
        for line in lines
        if any(
            _DATE_SLASH.fullmatch(str(word["text"])) and 550.0 <= _centre(word) < 680.0
            for word in line.words
        )
    ]
    if len(date_lines) != 1063:
        raise RuntimeError(f"cuneo_listed: expected 1063 sector rows, got {len(date_lines)}")

    records: list[dict[str, Any]] = []
    raw_identifiers: list[str] = []
    malformed: dict[int, str] = {}
    no_expiry = 0
    conflict_ordinals: list[int] = []

    for index, header in enumerate(headers):
        ordinal = index + 1
        end = headers[index + 1].pos if index + 1 < len(headers) else len(lines)
        matching_statuses = [line for line in statuses if header.pos < line.pos < end]
        if len(matching_statuses) != 1:
            raise RuntimeError(
                f"cuneo_listed: record {ordinal} has {len(matching_statuses)} status headers"
            )
        status_line = matching_statuses[0]
        identity_lines = lines[header.pos + 1 : status_line.pos]
        name = _clean(" ".join(_band(line, 0.0, 340.0) for line in identity_lines))
        office = _clean(" ".join(_band(line, 340.0, 630.0) for line in identity_lines))
        identifier_raw = _clean(" ".join(_band(line, 630.0, 841.9) for line in identity_lines))
        raw_status = _band(status_line, 280.0, 575.0)
        status = _listed_status(raw_status)

        if not name or not office or not re.fullmatch(r"\d{10,12}", identifier_raw):
            raise RuntimeError(
                f"cuneo_listed: incomplete identity at record {ordinal}: "
                f"name={name!r}, office={office!r}, identifier={identifier_raw!r}"
            )
        raw_identifiers.append(identifier_raw)
        if len(identifier_raw) != 11:
            malformed[ordinal] = identifier_raw

        activity_lines = [line for line in date_lines if status_line.pos < line.pos < end]
        if not activity_lines:
            raise RuntimeError(f"cuneo_listed: record {ordinal} has no source activity rows")

        activities: list[str] = []
        listing_raw: list[str] = []
        expiry_raw: list[str] = []
        for activity_index, activity_line in enumerate(activity_lines):
            activity_end = (
                activity_lines[activity_index + 1].pos
                if activity_index + 1 < len(activity_lines)
                else end
            )
            activity = _activity_text(
                lines,
                activity_line.pos,
                activity_end,
                x_min=40.0,
                x_max=570.0,
            )
            if not activity.startswith("SEZ"):
                raise RuntimeError(
                    f"cuneo_listed: unrecognised activity row at record {ordinal}: {activity!r}"
                )
            activities.append(activity)

            listing = [
                str(word["text"])
                for word in activity_line.words
                if _DATE_SLASH.fullmatch(str(word["text"]))
                and 550.0 <= _centre(word) < 680.0
            ]
            expiry = [
                str(word["text"])
                for word in activity_line.words
                if _DATE_SLASH.fullmatch(str(word["text"])) and _centre(word) >= 680.0
            ]
            if len(listing) != 1 or len(expiry) > 1:
                raise RuntimeError(
                    f"cuneo_listed: date-column drift at record {ordinal}: "
                    f"listing={listing}, expiry={expiry}"
                )
            listing_raw.extend(listing)
            expiry_raw.extend(expiry)

        listing_variants = _ordered_unique(listing_raw)
        expiry_variants = _ordered_unique(expiry_raw)
        if len(listing_variants) == 1:
            listing_date = _source_date(listing_variants[0])
        elif (
            ordinal == 71
            and name == "BAUDINO TRASPORTI S.r.l."
            and identifier_raw == "02905860041"
            and set(listing_variants) == {"07/01/2025", "07/01/2015"}
        ):
            listing_date = ""
            conflict_ordinals.append(ordinal)
        else:
            raise RuntimeError(
                f"cuneo_listed: unreviewed listing-date conflict at record {ordinal}: {listing_variants}"
            )
        if len(expiry_variants) > 1:
            raise RuntimeError(
                f"cuneo_listed: unreviewed expiry-date conflict at record {ordinal}: {expiry_variants}"
            )
        expiry_date = _source_date(expiry_variants[0]) if expiry_variants else ""
        if not expiry_variants:
            no_expiry += 1

        record = _record(
            cfg,
            ordinal,
            name=name,
            office=office,
            identifier_raw=identifier_raw,
            activities=activities,
            status=status,
            outcome_raw=raw_status,
            listing_date=listing_date,
            expiry_date=expiry_date,
            primary_date_label="Data iscrizione",
            source_fields={
                "physical_locator": f"page {header.page}; source record {ordinal}",
                "listing_date_raw_variants": listing_variants,
                "expiry_date_raw_variants": expiry_variants,
                "in_aggiornamento": raw_status if status == "renewal_update_in_progress" else "",
            },
        )
        records.append(record)

    if malformed != _EXPECTED_MALFORMED_IDENTIFIERS:
        raise RuntimeError(f"cuneo_listed: malformed identifier boundary drift: {malformed}")
    lengths = Counter(len(value) for value in raw_identifiers)
    if lengths != Counter({11: 457, 10: 9, 12: 2}):
        raise RuntimeError(f"cuneo_listed: identifier-shape drift: {dict(lengths)}")
    strict = [value for value in raw_identifiers if len(value) == 11]
    duplicates = {value: count for value, count in Counter(strict).items() if count > 1}
    if duplicates != _EXPECTED_DUPLICATE_STRICT_IDENTIFIERS:
        raise RuntimeError(f"cuneo_listed: strict identifier duplicate drift: {duplicates}")
    if no_expiry != 65 or conflict_ordinals != [71]:
        raise RuntimeError(
            f"cuneo_listed: reviewed date-exception boundary drift: "
            f"no_expiry={no_expiry}, conflicts={conflict_ordinals}"
        )

    status_counts = Counter(record["source_status"] for record in records)
    if status_counts != Counter({"listed": 402, "renewal_update_in_progress": 66}):
        raise RuntimeError(f"cuneo_listed: normalised status denominator drift: {dict(status_counts)}")

    diagnostics = {
        "parser": "cuneo_listed",
        "page_rows": page_rows,
        "positioned_rows": len(records),
        "sector_rows": len(date_lines),
        "public_records": len(records),
        "status_counts": dict(status_counts),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "name_coverage": sum(bool(record["name"]) for record in records),
        "office_coverage": sum(bool(record["registered_office"]) for record in records),
        "activities_coverage": sum(bool(record["requested_activities"]) for record in records),
        "listing_date_conflicts_preserved": conflict_ordinals,
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records, diagnostics)


def parse_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    lines, page_texts = _lines(path)
    if len(page_texts) != 13:
        raise RuntimeError(f"cuneo_applicants: expected 13 pages, got {len(page_texts)}")
    if _DOCUMENT_DATE not in page_texts[0]:
        raise RuntimeError("cuneo_applicants: approved 15 September 2026 document marker missing")
    if "elenco delle ditte richiedenti l'iscrizione nella white list" not in page_texts[0].replace("’", "'").replace("‘", "'"):
        raise RuntimeError("cuneo_applicants: positive applicant-population title missing")

    anchors = [
        line
        for line in lines
        if "Data presentazione" in line.text and "istanza" in line.text
    ]
    page_rows = [sum(anchor.page == page for anchor in anchors) for page in range(1, 14)]
    if tuple(page_rows) != _EXPECTED_APPLICANT_PAGE_ROWS:
        raise RuntimeError(f"cuneo_applicants: page denominator drift: {page_rows}")
    if len(anchors) != 48:
        raise RuntimeError(f"cuneo_applicants: expected 48 record anchors, got {len(anchors)}")

    date_lines = [
        line
        for line in lines
        if any(
            _DATE_DASH.fullmatch(str(word["text"])) and _centre(word) >= 700.0
            for word in line.words
        )
    ]
    if len(date_lines) != 93:
        raise RuntimeError(f"cuneo_applicants: expected 93 activity rows, got {len(date_lines)}")

    records: list[dict[str, Any]] = []
    raw_identifiers: list[str] = []
    for index, anchor in enumerate(anchors):
        ordinal = index + 1
        end = anchors[index + 1].pos if index + 1 < len(anchors) else len(lines)
        activity_lines = [line for line in date_lines if anchor.pos < line.pos < end]
        if not activity_lines:
            raise RuntimeError(f"cuneo_applicants: record {ordinal} has no activity rows")
        first_activity = activity_lines[0].pos
        identity_lines = [
            line
            for line in lines[anchor.pos:first_activity]
            if line.page == anchor.page and "Attività" not in line.text
        ]
        name = _clean(" ".join(_band(line, 0.0, 196.0) for line in identity_lines))
        office = _clean(" ".join(_band(line, 196.0, 420.0) for line in identity_lines))
        identifier_context = _clean(" ".join(_band(line, 420.0, 600.0) for line in identity_lines))
        identifiers = re.findall(r"(?<!\d)\d{11}(?!\d)", identifier_context)
        if not name or not office or len(identifiers) != 1:
            raise RuntimeError(
                f"cuneo_applicants: incomplete identity at record {ordinal}: "
                f"name={name!r}, office={office!r}, id_context={identifier_context!r}"
            )
        identifier_raw = identifiers[0]
        raw_identifiers.append(identifier_raw)

        activities: list[str] = []
        application_raw: list[str] = []
        for activity_index, activity_line in enumerate(activity_lines):
            activity_end = (
                activity_lines[activity_index + 1].pos
                if activity_index + 1 < len(activity_lines)
                else end
            )
            activity = _activity_text(
                lines,
                activity_line.pos,
                activity_end,
                x_min=190.0,
                x_max=700.0,
            )
            if not activity.startswith("SEZ"):
                raise RuntimeError(
                    f"cuneo_applicants: unrecognised activity row at record {ordinal}: {activity!r}"
                )
            activities.append(activity)
            dates = [
                str(word["text"])
                for word in activity_line.words
                if _DATE_DASH.fullmatch(str(word["text"])) and _centre(word) >= 700.0
            ]
            if len(dates) != 1:
                raise RuntimeError(
                    f"cuneo_applicants: application-date column drift at record {ordinal}: {dates}"
                )
            application_raw.extend(dates)

        variants = _ordered_unique(application_raw)
        if len(variants) != 1:
            raise RuntimeError(
                f"cuneo_applicants: unreviewed application-date conflict at record {ordinal}: {variants}"
            )
        application_date = _source_date(variants[0])
        if not application_date:
            raise RuntimeError(
                f"cuneo_applicants: invalid source application date at record {ordinal}: {variants[0]!r}"
            )

        records.append(
            _record(
                cfg,
                ordinal,
                name=name,
                office=office,
                identifier_raw=identifier_raw,
                activities=activities,
                status="pending",
                application_date=application_date,
                primary_date_label="Data presentazione istanza",
                source_fields={
                    "physical_locator": f"page {anchor.page}; source record {ordinal}",
                    "application_date_raw_variants": variants,
                },
            )
        )

    if len(set(raw_identifiers)) != 48 or any(len(value) != 11 for value in raw_identifiers):
        raise RuntimeError("cuneo_applicants: strict identifier uniqueness/shape drift")
    if Counter(record["source_status"] for record in records) != Counter({"pending": 48}):
        raise RuntimeError("cuneo_applicants: applicant status denominator drift")

    diagnostics = {
        "parser": "cuneo_applicants",
        "page_rows": page_rows,
        "positioned_rows": len(records),
        "sector_rows": len(date_lines),
        "public_records": len(records),
        "status_counts": {"pending": 48},
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "raw_identifier_coverage": sum(bool(record["identifier_field_raw"]) for record in records),
        "name_coverage": sum(bool(record["name"]) for record in records),
        "office_coverage": sum(bool(record["registered_office"]) for record in records),
        "activities_coverage": sum(bool(record["requested_activities"]) for record in records),
        "dropped_date_rows": 0,
    }
    return ParsedBatch(records, diagnostics)


PARSERS = {
    "cuneo_listed": parse_listed,
    "cuneo_applicants": parse_applicants,
}
