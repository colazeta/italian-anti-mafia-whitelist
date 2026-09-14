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
_LISTED_REFERENCE_DATE = "2026-09-11"
_APPLICANT_REFERENCE_DATE = "2026-09-10"
_LISTED_SHA256 = "b831570c01220b8709ebf9c4dbdfe856aba37a21c46353cf7bc9eedb5965c8af"
_APPLICANT_SHA256 = "9f36797e3e11834c979f9b5f5d58d693e19fa2456c69ce5859628d4e56a056c0"

_LISTED_PAGES = 289
_APPLICANT_PAGES = 22
_LISTED_PHYSICAL_ROWS = 3208
_APPLICANT_PHYSICAL_ROWS = 117
_LISTED_SECTION_ROWS = 3020
_LISTED_RECORDS = 1366
_APPLICANT_RECORDS = 98

_EXPECTED_SECTION_ROWS = {
    "I": 571,
    "II": 198,
    "III": 499,
    "IV": 322,
    "V": 700,
    "VI": 308,
    "VII": 9,
    "VIII": 17,
    "IX": 105,
    "X": 291,
}
_EXPECTED_LISTED_SOURCE_STATUS_COUNTS = {
    "listed": 1507,
    "renewal_update_in_progress": 1513,
}
_EXPECTED_LISTED_STATUS_COUNTS = {"listed": 699, "renewal_update_in_progress": 667}
_EXPECTED_APPLICANT_STATUS_COUNTS = {"pending": 98}
_EXPECTED_LISTED_RAW_WIDTHS = {7: 3169, 9: 39}
_EXPECTED_LISTED_TABLE_COUNTS = {0: 1, 1: 281, 2: 7}
_EXPECTED_GROUP_OCCURRENCES = {1: 696, 2: 234, 3: 160, 4: 114, 5: 91, 6: 37, 7: 29, 8: 5}
_EXPECTED_TEXT_VARIATION_GROUPS = 13

_TWO_TABLE_PAGES = {69, 116, 147, 244, 246, 248, 261}
_ZERO_TABLE_PAGES = {289}
_SECTION_STARTS = {
    (1, 1): "I",
    (50, 1): "II",
    (69, 2): "III",
    (116, 2): "IV",
    (147, 2): "V",
    (213, 1): "VI",
    (244, 2): "VII",
    (246, 2): "VIII",
    (248, 2): "IX",
    (261, 2): "X",
}
_HEADER_COORDS = {(page, table, 1) for page, table in _SECTION_STARTS}
_LISTED_BLANK_COORDS = {
    (44, 1, 1),
    (106, 1, 1),
    (148, 1, 1),
    (197, 1, 1),
    (237, 1, 1),
    (283, 1, 1),
}
_LISTED_CONTINUATION_PAGES = {
    5, 6, 7, 8, 9, 11, 15, 18, 20, 21, 25, 26, 29, 30, 31, 32, 34, 35,
    36, 37, 39, 40, 41, 42, 46, 48, 51, 52, 54, 58, 59, 60, 61, 63, 64, 65,
    66, 68, 69, 72, 73, 74, 75, 76, 79, 80, 81, 83, 84, 85, 87, 90, 91, 92,
    93, 94, 96, 97, 98, 99, 100, 102, 103, 105, 107, 108, 109, 111, 113, 114,
    115, 116, 117, 118, 119, 121, 123, 124, 125, 126, 127, 134, 137, 140, 141,
    142, 143, 144, 145, 146, 147, 150, 152, 153, 154, 157, 158, 162, 167, 168,
    171, 172, 174, 175, 178, 180, 181, 182, 184, 185, 187, 188, 189, 190, 191,
    192, 194, 195, 199, 200, 201, 203, 204, 207, 209, 210, 211, 212, 214, 216,
    217, 219, 220, 223, 225, 226, 229, 233, 239, 240, 242, 243, 246, 247, 248,
    249, 250, 251, 253, 254, 255, 256, 258, 260, 261, 262, 263, 264, 265, 266,
    267, 271, 274, 275, 278, 279, 280, 281, 284, 285, 286, 288,
}
_LISTED_CONTINUATIONS = {(page, 1, 1) for page in _LISTED_CONTINUATION_PAGES}

_LISTED_DATE_EXCEPTIONS = {
    (274, 1, 8): (
        "F.I.R. S.A.S. DI F.I.R. SERVIZI S.R.L. SOCIETA’ BENEFIT",
        "14.04.206",
        "13.04.2026",
        "AGGIORNAMENTO IN CORSO",
    )
}
_LISTED_IDENTIFIER_EXCEPTIONS = {
    (221, 1, 13): ("BUTTERINI PIETRO TRASPORTI S.R.L.", "006281590229", ()),
    (250, 1, 6): (
        "ASSOCIAZIONE SCUOLA MATERNA ROMANI – DE MOLL DI NOMI ENTE DEL TERZO SETTORE "
        "(già ASSOCIAZIONE SCUOLA MATERNA ROMANI – DE MOLL DI NOMI ORGANIZZAZIONE DI VOLONTARIATO)",
        "P.IVA 02785350220 C.F.85000750225",
        ("02785350220", "85000750225"),
    ),
    (260, 1, 4): (
        "SCUOLA MATERNA DON VITTORIO PISONI",
        "C.F.84002830226 P.IVA 01157050228",
        ("84002830226", "01157050228"),
    ),
    (280, 1, 5): (
        "MODOLO IMPIANTI S.R.L.",
        "P.I. 01731370225 C.F. 01191130218",
        ("01731370225", "01191130218"),
    ),
}

_APPLICANT_BLANK_COORDS = {(19, 1, 1)}
_APPLICANT_HEADER_COORDS = {(1, 1, 1)}
_APPLICANT_CONTINUATION_PAGES = {
    2, 3, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18, 20, 21, 22,
}
_APPLICANT_CONTINUATIONS = {(page, 1, 1) for page in _APPLICANT_CONTINUATION_PAGES}
_APPLICANT_DATE_EXCEPTION = {
    (12, 1, 3): (
        "ROMANI DE MOLL S.R.L. IMPRESA SOCIALE",
        "29.06.2026 (integrata il 02.07.2026)",
        "29.06.2026",
        "02.07.2026",
    )
}
_EXPECTED_APPLICANT_ACTIVITY_SECTION_COUNTS = {
    "I": 34,
    "II": 10,
    "III": 16,
    "IV": 19,
    "V": 32,
    "VI": 12,
    "VIII": 3,
    "IX": 14,
    "X": 16,
}

_STRICT_IDENTIFIER_11 = re.compile(r"^\d{11}$")
_STRICT_IDENTIFIER_16 = re.compile(r"^[A-Z0-9]{16}$")
_EMBEDDED_IDENTIFIER_11 = re.compile(r"(?<!\d)\d{11}(?!\d)")
_EMBEDDED_IDENTIFIER_16 = re.compile(r"\b[A-Z0-9]{16}\b")
_DATE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
_SECTION_TOKEN = re.compile(r"\(Sezione\s+([IVX]+)\)", re.I)
_ACTIVITY_CHUNK = re.compile(r".+?\(Sezione\s+[IVX]+\)", re.I)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_cfg(
    cfg: dict[str, Any],
    *,
    source_key: str,
    population_scope: str,
    reference_date: str,
    sha256: str,
) -> None:
    expected = {
        "source_key": source_key,
        "authority_key": "trento",
        "population_scope": population_scope,
        "reference_date": reference_date,
        "sha256": sha256,
    }
    for key, value in expected.items():
        if cfg.get(key) != value:
            raise RuntimeError(
                f"Trento configuration drift for {source_key}: {key}={cfg.get(key)!r} != {value!r}"
            )


def _calendar_date(raw: str, *, context: str) -> str:
    value = _clean(raw)
    if not _DATE.fullmatch(value):
        raise RuntimeError(f"Trento unreviewed date typography ({context}): {value!r}")
    try:
        datetime.strptime(value, "%d.%m.%Y")
    except ValueError as exc:
        raise RuntimeError(f"Trento invalid calendar date ({context}): {value!r}") from exc
    return value


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


def _normalise_listed_cells(raw: list[Any], *, coord: tuple[int, int, int]) -> tuple[str, ...]:
    cells = [_clean(value) for value in (raw or [])]
    if len(cells) == 7:
        return tuple(cells)
    if len(cells) != 9:
        raise RuntimeError(f"Trento unreviewed listed width at {coord!r}: {len(cells)}")
    if cells[6]:
        raise RuntimeError(f"Trento unreviewed split-date slot at {coord!r}: {cells!r}")
    date_parts = [value for value in cells[4:7] if value]
    if len(date_parts) > 1:
        raise RuntimeError(f"Trento ambiguous split registration date at {coord!r}: {cells!r}")
    return (
        cells[0],
        cells[1],
        cells[2],
        cells[3],
        date_parts[0] if date_parts else "",
        cells[7],
        cells[8],
    )


def _append_fragment(base: list[str], fragment: tuple[str, ...]) -> list[str]:
    if len(base) != 7 or len(fragment) != 7:
        raise RuntimeError("Trento continuation width drift")
    for index, value in enumerate(fragment):
        if value:
            base[index] = _clean(f"{base[index]} {value}")
    return base


def _listed_source_rows(path: Path) -> list[dict[str, Any]]:
    physical = 0
    raw_widths: Counter[int] = Counter()
    table_counts: Counter[int] = Counter()
    blanks: set[tuple[int, int, int]] = set()
    headers: set[tuple[int, int, int]] = set()
    continuations: set[tuple[int, int, int]] = set()
    rows: list[dict[str, Any]] = []
    current_section = ""

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGES:
            raise RuntimeError(f"Trento listed page-count drift: {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.find_tables()
            table_counts[len(tables)] += 1
            expected_tables = 0 if page_number in _ZERO_TABLE_PAGES else (
                2 if page_number in _TWO_TABLE_PAGES else 1
            )
            if len(tables) != expected_tables:
                raise RuntimeError(
                    f"Trento listed table-count drift page {page_number}: {len(tables)} != {expected_tables}"
                )
            for table_number, table in enumerate(tables, start=1):
                current_section = _SECTION_STARTS.get(
                    (page_number, table_number), current_section
                )
                if not current_section:
                    raise RuntimeError("Trento listed row precedes first reviewed section")
                for row_number, raw in enumerate(table.extract() or [], start=1):
                    physical += 1
                    raw_widths[len(raw or [])] += 1
                    coord = (page_number, table_number, row_number)
                    cells = _normalise_listed_cells(raw, coord=coord)
                    if not any(cells):
                        blanks.add(coord)
                        continue
                    if "ragione" in cells[0].casefold() and "social" in cells[0].casefold():
                        headers.add(coord)
                        continue
                    if coord in _LISTED_CONTINUATIONS:
                        if not rows:
                            raise RuntimeError(f"Trento orphan listed continuation {coord!r}")
                        rows[-1]["cells"] = tuple(
                            _append_fragment(list(rows[-1]["cells"]), cells)
                        )
                        rows[-1]["fragments"].append(
                            {
                                "page": page_number,
                                "table": table_number,
                                "row": row_number,
                                "cells": list(cells),
                            }
                        )
                        continuations.add(coord)
                        continue
                    positive = _positive_identifiers(cells[3])
                    if not (
                        positive
                        or _DATE.fullmatch(cells[4])
                        or _DATE.fullmatch(cells[5])
                        or coord in _LISTED_IDENTIFIER_EXCEPTIONS
                        or coord in _LISTED_DATE_EXCEPTIONS
                    ):
                        raise RuntimeError(f"Trento unreviewed listed row {coord!r}: {cells!r}")
                    rows.append(
                        {
                            "page": page_number,
                            "table": table_number,
                            "row": row_number,
                            "section": current_section,
                            "cells": cells,
                            "fragments": [],
                        }
                    )

    invariants = {
        "physical rows": (physical, _LISTED_PHYSICAL_ROWS),
        "raw widths": (dict(raw_widths), _EXPECTED_LISTED_RAW_WIDTHS),
        "table geometry": (dict(sorted(table_counts.items())), _EXPECTED_LISTED_TABLE_COUNTS),
        "blank rows": (blanks, _LISTED_BLANK_COORDS),
        "headers": (headers, _HEADER_COORDS),
        "continuations": (continuations, _LISTED_CONTINUATIONS),
        "logical section rows": (len(rows), _LISTED_SECTION_ROWS),
        "section denominators": (
            dict(Counter(row["section"] for row in rows)),
            _EXPECTED_SECTION_ROWS,
        ),
    }
    for label, (observed, expected) in invariants.items():
        if observed != expected:
            raise RuntimeError(f"Trento listed {label} drift: {observed!r} != {expected!r}")

    statuses: Counter[str] = Counter()
    date_exceptions: dict[tuple[int, int, int], tuple[str, str, str, str]] = {}
    id_exceptions: dict[tuple[int, int, int], tuple[str, str, tuple[str, ...]]] = {}
    inversions: dict[tuple[int, int, int], tuple[str, str, str]] = {}
    for row in rows:
        coord = (row["page"], row["table"], row["row"])
        c = row["cells"]
        marker = _clean(c[6]).upper()
        if marker == "AGGIORNAMENTO IN CORSO":
            status = "renewal_update_in_progress"
        elif not marker:
            status = "listed"
        else:
            raise RuntimeError(f"Trento unreviewed listed status at {coord!r}: {c[6]!r}")
        row["status"] = status
        statuses[status] += 1

        listing_ok = bool(_DATE.fullmatch(c[4]))
        expiry_ok = bool(_DATE.fullmatch(c[5]))
        if not (listing_ok and expiry_ok):
            date_exceptions[coord] = (c[0], c[4], c[5], c[6])
        if listing_ok:
            _calendar_date(c[4], context=f"listed {coord!r} registration")
        if expiry_ok:
            _calendar_date(c[5], context=f"listed {coord!r} expiry")
        if listing_ok and expiry_ok:
            if datetime.strptime(c[5], "%d.%m.%Y") < datetime.strptime(c[4], "%d.%m.%Y"):
                inversions[coord] = (c[0], c[4], c[5])

        whole = re.sub(r"\s+", "", _clean(c[3])).upper()
        if not (
            _STRICT_IDENTIFIER_11.fullmatch(whole)
            or _STRICT_IDENTIFIER_16.fullmatch(whole)
        ):
            id_exceptions[coord] = (c[0], c[3], tuple(_positive_identifiers(c[3])))

    if dict(statuses) != _EXPECTED_LISTED_SOURCE_STATUS_COUNTS:
        raise RuntimeError(f"Trento listed source-status drift: {dict(statuses)!r}")
    if date_exceptions != _LISTED_DATE_EXCEPTIONS:
        raise RuntimeError(f"Trento listed reviewed date-exception drift: {date_exceptions!r}")
    if inversions:
        raise RuntimeError(f"Trento listed chronology-inversion drift: {inversions!r}")
    if id_exceptions != _LISTED_IDENTIFIER_EXCEPTIONS:
        raise RuntimeError(f"Trento listed identifier-exception drift: {id_exceptions!r}")
    return rows


def _listed_dates(row: dict[str, Any]) -> tuple[str, str]:
    coord = (row["page"], row["table"], row["row"])
    c = row["cells"]
    if coord in _LISTED_DATE_EXCEPTIONS:
        if (c[0], c[4], c[5], c[6]) != _LISTED_DATE_EXCEPTIONS[coord]:
            raise RuntimeError(f"Trento reviewed date exception moved at {coord!r}")
        return "", _calendar_date(c[5], context=f"listed {coord!r} expiry")
    return (
        _calendar_date(c[4], context=f"listed {coord!r} registration"),
        _calendar_date(c[5], context=f"listed {coord!r} expiry"),
    )


def parse_trento_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(
        cfg,
        source_key="trento-listed",
        population_scope="listed",
        reference_date=_LISTED_REFERENCE_DATE,
        sha256=_LISTED_SHA256,
    )
    if _sha256(path) != _LISTED_SHA256:
        raise RuntimeError("Trento listed source bytes drift from approved SHA-256")

    rows = _listed_source_rows(path)
    groups: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        c = row["cells"]
        whole = re.sub(r"\s+", "", _clean(c[3])).upper()
        if _STRICT_IDENTIFIER_11.fullmatch(whole) or _STRICT_IDENTIFIER_16.fullmatch(whole):
            identity = whole
        else:
            identity = f"NAME:{_clean(c[0]).casefold()}"
        key = (identity, c[4], c[5], row["status"])
        group = groups.setdefault(
            key,
            {
                "first": row,
                "identifiers": [],
                "sections": [],
                "memberships": [],
                "names": [],
                "offices": [],
                "secondary": [],
                "identifier_raw": [],
            },
        )
        for identifier in _positive_identifiers(c[3]):
            if identifier not in group["identifiers"]:
                group["identifiers"].append(identifier)
        label = f"Sezione {row['section']}"
        if label not in group["sections"]:
            group["sections"].append(label)
        for bucket, value in (
            ("names", c[0]),
            ("offices", c[1]),
            ("secondary", c[2]),
            ("identifier_raw", c[3]),
        ):
            if value not in group[bucket]:
                group[bucket].append(value)
        group["memberships"].append(
            {
                "page": row["page"],
                "table": row["table"],
                "row": row["row"],
                "section": row["section"],
                "name_raw": c[0],
                "registered_office_raw": c[1],
                "secondary_office_raw": c[2],
                "identifier_raw": c[3],
                "listing_date_raw": c[4],
                "expiry_date_raw": c[5],
                "update_raw": c[6],
                "continuation_fragments": row["fragments"],
            }
        )

    if len(groups) != _LISTED_RECORDS:
        raise RuntimeError(f"Trento listed grouped-record drift: {len(groups)} != {_LISTED_RECORDS}")
    occurrence_counts = dict(Counter(len(group["memberships"]) for group in groups.values()))
    if occurrence_counts != _EXPECTED_GROUP_OCCURRENCES:
        raise RuntimeError(f"Trento listed group-occurrence drift: {occurrence_counts!r}")
    variations = sum(
        1
        for group in groups.values()
        if len(group["names"]) > 1 or len(group["offices"]) > 1 or len(group["secondary"]) > 1
    )
    if variations != _EXPECTED_TEXT_VARIATION_GROUPS:
        raise RuntimeError(f"Trento listed text-variation group drift: {variations}")

    records: list[dict[str, Any]] = []
    for ordinal, group in enumerate(groups.values(), start=1):
        first = group["first"]
        c = first["cells"]
        listing_date, expiry_date = _listed_dates(first)
        record = _record(
            cfg,
            ordinal,
            name=c[0],
            office=c[1],
            secondary=c[2],
            identifier_raw=c[3],
            activities=group["sections"],
            status=first["status"],
            outcome_raw=c[6],
            listing_date=listing_date,
            expiry_date=expiry_date,
            primary_date_label="Data iscrizione",
            source_fields={
                "sections": group["sections"],
                "source_memberships": group["memberships"],
                "name_variants": group["names"],
                "registered_office_variants": group["offices"],
                "secondary_office_variants": group["secondary"],
                "identifier_raw_variants": group["identifier_raw"],
                "listing_date_raw": c[4],
                "expiry_date_raw": c[5],
                "update_raw": c[6],
                "identifier_source_evidence": group["identifiers"],
                "reviewed_date_exception": (
                    first["page"], first["table"], first["row"]
                ) in _LISTED_DATE_EXCEPTIONS,
            },
        )
        record["identifiers"] = list(group["identifiers"])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(f"Trento listed public-status drift: {status_counts!r}")
    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "trento_listed",
            "parser_version": PARSER_VERSION,
            "source_pages": _LISTED_PAGES,
            "physical_rows": _LISTED_PHYSICAL_ROWS,
            "section_rows": _LISTED_SECTION_ROWS,
            "section_counts": _EXPECTED_SECTION_ROWS,
            "public_records": len(records),
            "status_counts": status_counts,
            "reviewed_continuations": len(_LISTED_CONTINUATIONS),
            "reviewed_date_exceptions": len(_LISTED_DATE_EXCEPTIONS),
            "reviewed_identifier_exceptions": len(_LISTED_IDENTIFIER_EXCEPTIONS),
            "group_occurrence_counts": occurrence_counts,
            "groups_with_source_text_variation": variations,
        },
    )


def _split_applicant_activities(raw: str) -> list[str]:
    value = _clean(raw)
    chunks = [_clean(match) for match in _ACTIVITY_CHUNK.findall(value)]
    if not chunks:
        raise RuntimeError(f"Trento applicant activity lacks a section marker: {value!r}")
    if _clean(" ".join(chunks)) != value:
        raise RuntimeError(f"Trento applicant activity split left unparsed text: {value!r}")
    if any(len(_SECTION_TOKEN.findall(chunk)) != 1 for chunk in chunks):
        raise RuntimeError(f"Trento applicant activity has ambiguous section markers: {value!r}")
    return chunks


def _applicant_source_rows(path: Path) -> list[dict[str, Any]]:
    physical = 0
    blanks: set[tuple[int, int, int]] = set()
    headers: set[tuple[int, int, int]] = set()
    continuations: set[tuple[int, int, int]] = set()
    rows: list[dict[str, Any]] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGES:
            raise RuntimeError(f"Trento applicant page-count drift: {len(pdf.pages)}")
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(f"Trento applicant table-count drift page {page_number}: {len(tables)}")
            for row_number, raw in enumerate(tables[0].extract() or [], start=1):
                physical += 1
                coord = (page_number, 1, row_number)
                cells = tuple(_clean(value) for value in (raw or []))
                if len(cells) != 7:
                    raise RuntimeError(f"Trento applicant width drift at {coord!r}: {len(cells)}")
                if not any(cells):
                    blanks.add(coord)
                    continue
                if "ragione" in cells[0].casefold() and "social" in cells[0].casefold():
                    headers.add(coord)
                    continue
                if coord in _APPLICANT_CONTINUATIONS:
                    if not rows:
                        raise RuntimeError(f"Trento orphan applicant continuation {coord!r}")
                    rows[-1]["cells"] = tuple(
                        _append_fragment(list(rows[-1]["cells"]), cells)
                    )
                    rows[-1]["fragments"].append(
                        {"page": page_number, "table": 1, "row": row_number, "cells": list(cells)}
                    )
                    continuations.add(coord)
                    continue
                positive = _positive_identifiers(cells[3])
                if len(positive) != 1:
                    raise RuntimeError(
                        f"Trento applicant row lacks exactly one positive identifier at {coord!r}: {cells[3]!r}"
                    )
                rows.append(
                    {
                        "page": page_number,
                        "table": 1,
                        "row": row_number,
                        "cells": cells,
                        "fragments": [],
                    }
                )

    invariants = {
        "physical rows": (physical, _APPLICANT_PHYSICAL_ROWS),
        "blank rows": (blanks, _APPLICANT_BLANK_COORDS),
        "headers": (headers, _APPLICANT_HEADER_COORDS),
        "continuations": (continuations, _APPLICANT_CONTINUATIONS),
        "logical rows": (len(rows), _APPLICANT_RECORDS),
    }
    for label, (observed, expected) in invariants.items():
        if observed != expected:
            raise RuntimeError(f"Trento applicant {label} drift: {observed!r} != {expected!r}")

    identifiers = [_positive_identifiers(row["cells"][3])[0] for row in rows]
    if len(set(identifiers)) != _APPLICANT_RECORDS:
        raise RuntimeError("Trento applicant identifier uniqueness drift")
    outcomes = Counter(_clean(row["cells"][6]) for row in rows)
    if outcomes != Counter({"": _APPLICANT_RECORDS}):
        raise RuntimeError(f"Trento applicant outcome typography drift: {dict(outcomes)!r}")

    date_exceptions: dict[tuple[int, int, int], tuple[str, str, str, str]] = {}
    section_counts: Counter[str] = Counter()
    for row in rows:
        coord = (row["page"], row["table"], row["row"])
        c = row["cells"]
        reviewed = _APPLICANT_DATE_EXCEPTION.get(coord)
        if reviewed is not None:
            if c[0] != reviewed[0] or c[5] != reviewed[1]:
                raise RuntimeError(f"Trento applicant reviewed date exception moved at {coord!r}")
            date_exceptions[coord] = reviewed
            _calendar_date(reviewed[2], context=f"applicant {coord!r} application")
            _calendar_date(reviewed[3], context=f"applicant {coord!r} integration")
        else:
            _calendar_date(c[5], context=f"applicant {coord!r} application")
        tokens = [token.upper() for token in _SECTION_TOKEN.findall(c[4])]
        if not tokens:
            raise RuntimeError(f"Trento applicant row lacks source section at {coord!r}")
        section_counts.update(tokens)
        _split_applicant_activities(c[4])

    if date_exceptions != _APPLICANT_DATE_EXCEPTION:
        raise RuntimeError(f"Trento applicant date-exception drift: {date_exceptions!r}")
    if dict(section_counts) != _EXPECTED_APPLICANT_ACTIVITY_SECTION_COUNTS:
        raise RuntimeError(f"Trento applicant activity-section drift: {dict(section_counts)!r}")
    return rows


def _applicant_dates(row: dict[str, Any]) -> tuple[str, str]:
    coord = (row["page"], row["table"], row["row"])
    c = row["cells"]
    reviewed = _APPLICANT_DATE_EXCEPTION.get(coord)
    if reviewed is None:
        return _calendar_date(c[5], context=f"applicant {coord!r} application"), ""
    if c[0] != reviewed[0] or c[5] != reviewed[1]:
        raise RuntimeError(f"Trento applicant reviewed date exception moved at {coord!r}")
    return (
        _calendar_date(reviewed[2], context=f"applicant {coord!r} application"),
        _calendar_date(reviewed[3], context=f"applicant {coord!r} integration"),
    )


def parse_trento_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(
        cfg,
        source_key="trento-applicants",
        population_scope="applicant",
        reference_date=_APPLICANT_REFERENCE_DATE,
        sha256=_APPLICANT_SHA256,
    )
    if _sha256(path) != _APPLICANT_SHA256:
        raise RuntimeError("Trento applicant source bytes drift from approved SHA-256")

    rows = _applicant_source_rows(path)
    records: list[dict[str, Any]] = []
    for ordinal, row in enumerate(rows, start=1):
        c = row["cells"]
        application_date, integration_date = _applicant_dates(row)
        record = _record(
            cfg,
            ordinal,
            name=c[0],
            office=c[1],
            secondary=c[2],
            identifier_raw=c[3],
            activities=_split_applicant_activities(c[4]),
            status="pending",
            outcome_raw=c[6],
            application_date=application_date,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "activities_raw": c[4],
                "application_date_raw": c[5],
                "integration_date_raw": integration_date,
                "outcome_raw": c[6],
                "source_page": row["page"],
                "source_table": row["table"],
                "source_table_row": row["row"],
                "continuation_fragments": row["fragments"],
                "reviewed_application_date_exception": (
                    row["page"], row["table"], row["row"]
                ) in _APPLICANT_DATE_EXCEPTION,
            },
        )
        record["identifiers"] = _positive_identifiers(c[3])
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_APPLICANT_STATUS_COUNTS:
        raise RuntimeError(f"Trento applicant public-status drift: {status_counts!r}")
    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "trento_applicants",
            "parser_version": PARSER_VERSION,
            "source_pages": _APPLICANT_PAGES,
            "physical_rows": _APPLICANT_PHYSICAL_ROWS,
            "public_records": len(records),
            "status_counts": status_counts,
            "strict_identifier_records": _APPLICANT_RECORDS,
            "reviewed_continuations": len(_APPLICANT_CONTINUATIONS),
            "reviewed_date_exceptions": len(_APPLICANT_DATE_EXCEPTION),
            "activity_section_counts": _EXPECTED_APPLICANT_ACTIVITY_SECTION_COUNTS,
        },
    )
