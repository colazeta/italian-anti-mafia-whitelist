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
_REFERENCE_DATE = "2026-09-03"
_LISTED_SHA256 = "c9cd39452fb2f751c2b9e105c10ecf0b9e57569006138af7f766d6851748029f"
_APPLICANT_SHA256 = "003e2ee6614302b1a1f8a504baae2b0c5d38752c70cfb509f693e1b4c1374f14"

_LISTED_PAGES = 224
_APPLICANT_PAGES = 184
_LISTED_PHYSICAL_ROWS = 1909
_APPLICANT_PHYSICAL_ROWS = 1292
_LISTED_SECTION_ROWS = 1854
_LISTED_RECORDS = 1016
_APPLICANT_RECORDS = 1213

_EXPECTED_LISTED_STATUS_COUNTS = {"listed": 674, "renewal_update_in_progress": 342}
_EXPECTED_APPLICANT_STATUS_COUNTS = {"listed": 1036, "pending": 176, "other_or_unknown": 1}
_EXPECTED_SECTION_ROWS = {
    "I": 257,
    "II": 106,
    "III": 402,
    "IV": 138,
    "V": 441,
    "VI": 251,
    "VII": 12,
    "VIII": 9,
    "IX": 66,
    "X": 172,
}

_SECTION_STARTS = (
    (1, "I"),
    (30, "II"),
    (42, "III"),
    (89, "IV"),
    (106, "V"),
    (156, "VI"),
    (194, "VII"),
    (196, "VIII"),
    (198, "IX"),
    (205, "X"),
)
_HEADER_COORDS = {(page, 1) for page, _section in _SECTION_STARTS}
_LISTED_CONTINUATIONS = {
    (3, 1),
    (34, 1),
    (82, 1),
    (161, 1),
    (184, 1),
    (188, 1),
    (189, 1),
    (190, 1),
}
_APPLICANT_CONTINUATIONS = {
    (3, 1), (6, 1), (8, 1), (13, 1), (17, 1), (19, 1), (20, 1), (24, 1),
    (30, 1), (32, 1), (33, 1), (35, 1), (36, 1), (46, 1), (50, 1), (51, 1),
    (65, 1), (70, 1), (72, 1), (74, 1), (83, 1), (92, 1), (94, 1), (95, 1),
    (96, 1), (101, 1), (107, 1), (110, 1), (112, 1), (114, 1), (116, 1),
    (117, 1), (119, 1), (120, 1), (121, 1), (122, 1), (123, 1), (126, 1),
    (127, 1), (132, 1), (134, 1), (139, 1), (142, 1), (143, 1), (144, 1),
    (150, 1), (156, 1), (163, 1), (164, 1), (166, 1), (171, 1), (173, 1),
    (174, 1), (181, 1),
}
_APPLICANT_FORWARD_FRAGMENT = (6, 6)

_DATE = re.compile(r"^\d{1,2}[./]\d{1,2}[./]\d{4}$")
_STRICT_IDENTIFIER_11 = re.compile(r"^\d{11}$")
_STRICT_IDENTIFIER_16 = re.compile(r"^[A-Z0-9]{16}$")

_LISTED_DATE_EXCEPTIONS = {
    (17, 5): (
        "INNOCENZI FRANCO IMPRESA INDIVIDUALE",
        "19/11/2025",
        "1 8/11/2026",
        "",
    ),
    (37, 2): (
        "MARCA S.R.L.",
        "1°/10/2021",
        "30/09/2022",
        "SI",
    ),
    (66, 3): (
        "IMPRESA EDILE LONGARI DUE SAS DI LONGARI RICCARDO E ROBERTO",
        "13/11/20258",
        "12/11/2026",
        "",
    ),
    (104, 8): (
        "WILSIDER SPA",
        "07/04/2026/",
        "06/04/2027",
        "",
    ),
    (162, 5): (
        "BRUNELLI GIAN PAOLO S.R.L.",
        "01/04/2025",
        "BRUSTENGHI 31/03/2026",
        "SI",
    ),
    (184, 5): (
        "SCHIAVOLINI NATASCIA Impresa individuale",
        "Autotrasporto per conto di terzi",
        "02/10/2025",
        "01/10/2026",
    ),
    (199, 8): (
        "RISTORANTE ALBERGO LE MURA S.R.L.",
        "",
        "",
        "",
    ),
}
_LISTED_UNPARSED_LISTING = {(37, 2), (66, 3), (104, 8), (184, 5), (199, 8)}
_LISTED_UNPARSED_EXPIRY = {(17, 5), (162, 5), (184, 5), (199, 8)}
_LISTED_DATE_INVERSIONS = {
    (38, 1): ("P.B.M. – POLIMER BITUMEN MODIFIERS DI LEONARDO BACCARELLI E C. S.A.S.", "23/06/2025", "22/06/2025", "SI"),
    (103, 8): ("TECNOTADDEI S.R.L.", "23/06/2025", "22/06/2025", "SI"),
    (187, 1): ("SELLANI ALBERTO Impresa individuale", "23/06/2025", "22/06/2025", ""),
    (203, 12): ("SOPRA IL MURO SOCIETA’ COOPERATIVA SOCIALE", "07/07/2027", "06/07/2027", ""),
    (219, 7): ("R.B. S.R.L.", "12/11/2025", "11/11/2025", ""),
}

_APPLICANT_EMPTY_APPLICATION_ORDINALS = {8, 149, 387, 650, 766, 900, 1196}
_APPLICANT_UNPARSED_APPLICATION = {
    689: ("LR MEAT & COOKING S.R.L.", "0389625054 9"),
    790: ("COLFIORITANA TRASPORTI S.R.L.", "07/03/20225"),
    810: ("EDILIZIA DOMAX S.R.L.S.", "1°/04/2025"),
    811: ("YES! ENGINEERING S.C.R.L.", "1°/04/2025"),
    812: ("VEGA TECNO SERVICE S.R.L.", "1°/04/2025"),
}
_APPLICANT_MISSING_DECISION_DATES = {
    73: ("F.LLI TENERINI SERGIO & ALVARO S.R.L.", "Rinnovo iscrizione in data"),
    413: ("MARCA S.R.L.", "Iscritta in data 1°/10/2021"),
    951: ("DREAM GARDEN VLB S.R.L.S.", "Iscritta in data 1°/12/2025"),
}
_APPLICANT_BLANK_NAME = {
    1052: (
        "Perugia, Via Gregorovius n. 56",
        "03522900541",
        "Noli a freddo di macchinari; Noli a caldo",
        "04/02/2026",
        "",
    )
}
_APPLICANT_BARE_OUTCOME = {1026: ("BORGIONI PREFABBRICATI S.R.L.", "25/03/2026")}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_cfg(cfg: dict[str, Any], *, source_key: str, population_scope: str, sha256: str) -> None:
    if cfg.get("source_key") != source_key:
        raise RuntimeError(f"Perugia source-key drift: {cfg.get('source_key')!r} != {source_key!r}")
    if cfg.get("authority_key") != "perugia":
        raise RuntimeError("Perugia parser bound to a non-Perugia authority")
    if cfg.get("population_scope") != population_scope:
        raise RuntimeError(
            f"Perugia population-scope drift for {source_key}: "
            f"{cfg.get('population_scope')!r} != {population_scope!r}"
        )
    if cfg.get("sha256") != sha256:
        raise RuntimeError(
            f"Perugia configured SHA-256 drift for {source_key}: {cfg.get('sha256')!r} != {sha256!r}"
        )
    if cfg.get("reference_date") != _REFERENCE_DATE:
        raise RuntimeError(
            f"Perugia reference-date drift for {source_key}: "
            f"{cfg.get('reference_date')!r} != {_REFERENCE_DATE!r}"
        )


def _strict_identifier(raw: str) -> str:
    token = re.sub(r"\s+", "", _clean(raw)).upper()
    if _STRICT_IDENTIFIER_11.fullmatch(token) or _STRICT_IDENTIFIER_16.fullmatch(token):
        return token
    return ""


def _calendar_date(raw: str, *, context: str) -> str:
    value = _clean(raw)
    if not _DATE.fullmatch(value):
        raise RuntimeError(f"Perugia unreviewed date typography ({context}): {value!r}")
    fmt = "%d/%m/%Y" if "/" in value else "%d.%m.%Y"
    try:
        datetime.strptime(value, fmt)
    except ValueError as exc:
        raise RuntimeError(f"Perugia invalid calendar date ({context}): {value!r}") from exc
    return value


def _date_obj(raw: str) -> datetime:
    fmt = "%d/%m/%Y" if "/" in raw else "%d.%m.%Y"
    return datetime.strptime(raw, fmt)


def _section_for_page(page: int) -> str:
    section = ""
    for start, candidate in _SECTION_STARTS:
        if page >= start:
            section = candidate
    if not section:
        raise RuntimeError(f"Perugia listed row before first section: page={page}")
    return section


def _append_fragment(base: list[str], fragment: tuple[str, ...], *, prepend: bool = False) -> list[str]:
    if len(base) != 7 or len(fragment) != 7:
        raise RuntimeError("Perugia continuation width drift")
    for index, value in enumerate(fragment):
        if not value:
            continue
        base[index] = _clean(
            f"{value} {base[index]}" if prepend else f"{base[index]} {value}"
        )
    return base


def _listed_source_rows(path: Path) -> list[dict[str, Any]]:
    physical = 0
    blanks = 0
    headers: set[tuple[int, int]] = set()
    continuations: set[tuple[int, int]] = set()
    rows: list[dict[str, Any]] = []

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _LISTED_PAGES:
            raise RuntimeError(f"Perugia listed page-count drift: {len(pdf.pages)} != {_LISTED_PAGES}")
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.find_tables()
            expected_tables = 0 if page_number == 193 else 1
            if len(tables) != expected_tables:
                raise RuntimeError(
                    f"Perugia listed table-count drift on page {page_number}: "
                    f"{len(tables)} != {expected_tables}"
                )
            if not tables:
                continue
            extracted = tables[0].extract() or []
            for row_number, raw in enumerate(extracted, start=1):
                physical += 1
                cells = tuple(_clean(value) for value in (raw or []))
                if len(cells) != 7:
                    raise RuntimeError(
                        f"Perugia listed table-width drift p{page_number} r{row_number}: {len(cells)} != 7"
                    )
                coord = (page_number, row_number)
                if not any(cells):
                    blanks += 1
                    continue
                if cells[0] == "Ragione Sociale":
                    headers.add(coord)
                    continue
                if coord in _LISTED_CONTINUATIONS:
                    if not rows:
                        raise RuntimeError(f"Perugia orphan listed continuation at {coord!r}")
                    rows[-1]["cells"] = tuple(
                        _append_fragment(list(rows[-1]["cells"]), cells)
                    )
                    rows[-1]["fragments"].append(
                        {"page": page_number, "row": row_number, "cells": list(cells)}
                    )
                    continuations.add(coord)
                    continue
                rows.append(
                    {
                        "page": page_number,
                        "row": row_number,
                        "section": _section_for_page(page_number),
                        "cells": cells,
                        "fragments": [],
                    }
                )

    if physical != _LISTED_PHYSICAL_ROWS:
        raise RuntimeError(f"Perugia listed physical-row drift: {physical} != {_LISTED_PHYSICAL_ROWS}")
    if blanks != 37:
        raise RuntimeError(f"Perugia listed blank-row drift: {blanks} != 37")
    if headers != _HEADER_COORDS:
        raise RuntimeError(
            f"Perugia listed header-boundary drift: {sorted(headers)!r} != {sorted(_HEADER_COORDS)!r}"
        )
    if continuations != _LISTED_CONTINUATIONS:
        raise RuntimeError(
            f"Perugia listed continuation population drift: "
            f"{sorted(continuations)!r} != {sorted(_LISTED_CONTINUATIONS)!r}"
        )
    if len(rows) != _LISTED_SECTION_ROWS:
        raise RuntimeError(
            f"Perugia listed section-row drift: {len(rows)} != {_LISTED_SECTION_ROWS}"
        )
    section_counts = dict(Counter(row["section"] for row in rows))
    if section_counts != _EXPECTED_SECTION_ROWS:
        raise RuntimeError(f"Perugia listed section-denominator drift: {section_counts!r}")

    si_count = sum(row["cells"][6] == "SI" for row in rows)
    unexpected_status = {
        (row["page"], row["row"]): row["cells"][6]
        for row in rows
        if row["cells"][6] and row["cells"][6] != "SI"
    }
    if si_count != 684 or unexpected_status != {(184, 5): "01/10/2026"}:
        raise RuntimeError(
            f"Perugia listed source-status typography drift: "
            f"SI={si_count}; unexpected={unexpected_status!r}"
        )

    observed_exceptions = {
        (row["page"], row["row"]): (
            row["cells"][0], row["cells"][4], row["cells"][5], row["cells"][6]
        )
        for row in rows
        if (row["page"], row["row"]) in _LISTED_DATE_EXCEPTIONS
    }
    if observed_exceptions != _LISTED_DATE_EXCEPTIONS:
        raise RuntimeError(
            f"Perugia listed reviewed date-exception drift: {observed_exceptions!r}"
        )

    inversions: dict[tuple[int, int], tuple[str, str, str, str]] = {}
    for row in rows:
        coord = (row["page"], row["row"])
        c = row["cells"]
        if coord in _LISTED_UNPARSED_LISTING or coord in _LISTED_UNPARSED_EXPIRY:
            continue
        listing = _calendar_date(c[4], context=f"listed p{row['page']} r{row['row']} registration")
        expiry = _calendar_date(c[5], context=f"listed p{row['page']} r{row['row']} expiry")
        if _date_obj(expiry) < _date_obj(listing):
            inversions[coord] = (c[0], c[4], c[5], c[6])
    if inversions != _LISTED_DATE_INVERSIONS:
        raise RuntimeError(f"Perugia listed chronology-inversion drift: {inversions!r}")

    strict_count = sum(bool(_strict_identifier(row["cells"][3])) for row in rows)
    empty_id_count = sum(not row["cells"][3] for row in rows)
    if strict_count != 1817 or empty_id_count != 3:
        raise RuntimeError(
            f"Perugia listed strict-identifier coverage drift: "
            f"strict={strict_count}; empty={empty_id_count}"
        )
    return rows


def _listed_dates(row: dict[str, Any]) -> tuple[str, str]:
    coord = (row["page"], row["row"])
    c = row["cells"]
    listing = "" if coord in _LISTED_UNPARSED_LISTING else _calendar_date(
        c[4], context=f"listed p{row['page']} r{row['row']} registration"
    )
    expiry = "" if coord in _LISTED_UNPARSED_EXPIRY else _calendar_date(
        c[5], context=f"listed p{row['page']} r{row['row']} expiry"
    )
    return listing, expiry


def parse_perugia_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(cfg, source_key="perugia-listed", population_scope="listed", sha256=_LISTED_SHA256)
    if _sha256(path) != _LISTED_SHA256:
        raise RuntimeError("Perugia listed source bytes drift from approved SHA-256")

    source_rows = _listed_source_rows(path)
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    for source_row in source_rows:
        c = source_row["cells"]
        strict_id = _strict_identifier(c[3])
        identity = strict_id if strict_id else f"NAME:{_clean(c[0]).casefold()}"
        status_raw = "SI" if c[6] == "SI" else ""
        key = (identity, c[4], c[5], status_raw)
        group = grouped.setdefault(
            key,
            {
                "first": source_row,
                "strict_id": strict_id,
                "sections": [],
                "memberships": [],
                "names": [],
                "offices": [],
                "secondary_offices": [],
                "identifier_raw_values": [],
            },
        )
        section_label = f"Sezione {source_row['section']}"
        if section_label not in group["sections"]:
            group["sections"].append(section_label)
        for field_name, value in (
            ("names", c[0]),
            ("offices", c[1]),
            ("secondary_offices", c[2]),
            ("identifier_raw_values", c[3]),
        ):
            if value and value not in group[field_name]:
                group[field_name].append(value)
        group["memberships"].append(
            {
                "page": source_row["page"],
                "row": source_row["row"],
                "section": source_row["section"],
                "name_raw": c[0],
                "registered_office_raw": c[1],
                "secondary_office_raw": c[2],
                "identifier_raw": c[3],
                "listing_date_raw": c[4],
                "expiry_date_raw": c[5],
                "update_raw": c[6],
                "continuation_fragments": source_row["fragments"],
            }
        )

    if len(grouped) != _LISTED_RECORDS:
        raise RuntimeError(f"Perugia listed grouped-record drift: {len(grouped)} != {_LISTED_RECORDS}")

    records: list[dict[str, Any]] = []
    for ordinal, group in enumerate(grouped.values(), start=1):
        first = group["first"]
        c = first["cells"]
        listing_date, expiry_date = _listed_dates(first)
        status = "renewal_update_in_progress" if c[6] == "SI" else "listed"
        record = _record(
            cfg,
            ordinal,
            name=c[0],
            office=c[1],
            secondary=c[2],
            identifier_raw=c[3],
            activities=group["sections"],
            status=status,
            outcome_raw=c[6],
            listing_date=listing_date,
            expiry_date=expiry_date,
            primary_date_label="Data iscrizione",
            source_fields={
                "sections": group["sections"],
                "source_memberships": group["memberships"],
                "name_variants": group["names"],
                "registered_office_variants": group["offices"],
                "secondary_office_variants": group["secondary_offices"],
                "identifier_raw_variants": group["identifier_raw_values"],
                "listing_date_raw": c[4],
                "expiry_date_raw": c[5],
                "update_raw": c[6],
                "reviewed_date_exception": (first["page"], first["row"]) in _LISTED_DATE_EXCEPTIONS,
                "reviewed_chronology_inversion": (first["page"], first["row"]) in _LISTED_DATE_INVERSIONS,
            },
        )
        record["identifiers"] = [group["strict_id"]] if group["strict_id"] else []
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_LISTED_STATUS_COUNTS:
        raise RuntimeError(f"Perugia listed grouped-status drift: {status_counts!r}")

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "perugia_listed",
            "parser_version": PARSER_VERSION,
            "source_pages": _LISTED_PAGES,
            "physical_rows": _LISTED_PHYSICAL_ROWS,
            "section_rows": _LISTED_SECTION_ROWS,
            "section_counts": _EXPECTED_SECTION_ROWS,
            "public_records": len(records),
            "status_counts": status_counts,
            "strict_identifier_section_rows": 1817,
            "reviewed_date_exceptions": len(_LISTED_DATE_EXCEPTIONS),
            "reviewed_chronology_inversions": len(_LISTED_DATE_INVERSIONS),
            "reviewed_continuations": len(_LISTED_CONTINUATIONS),
        },
    )


def _applicant_source_rows(path: Path) -> list[dict[str, Any]]:
    physical = 0
    blanks = 0
    header_count = 0
    continuations: set[tuple[int, int]] = set()
    rows: list[dict[str, Any]] = []
    forward_fragment: tuple[str, ...] | None = None

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != _APPLICANT_PAGES:
            raise RuntimeError(
                f"Perugia applicant page-count drift: {len(pdf.pages)} != {_APPLICANT_PAGES}"
            )
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(
                    f"Perugia applicant table-count drift on page {page_number}: {len(tables)} != 1"
                )
            for row_number, raw in enumerate(tables[0].extract() or [], start=1):
                physical += 1
                cells = tuple(_clean(value) for value in (raw or []))
                if len(cells) != 7:
                    raise RuntimeError(
                        f"Perugia applicant table-width drift p{page_number} r{row_number}: "
                        f"{len(cells)} != 7"
                    )
                coord = (page_number, row_number)
                if not any(cells):
                    blanks += 1
                    continue
                if cells[0] == "Ragione Sociale":
                    header_count += 1
                    if coord != (1, 1):
                        raise RuntimeError(f"Perugia applicant header moved to {coord!r}")
                    continue
                if coord in _APPLICANT_CONTINUATIONS:
                    if not rows:
                        raise RuntimeError(f"Perugia orphan applicant continuation at {coord!r}")
                    rows[-1]["cells"] = tuple(
                        _append_fragment(list(rows[-1]["cells"]), cells)
                    )
                    rows[-1]["fragments"].append(
                        {"page": page_number, "row": row_number, "cells": list(cells)}
                    )
                    continuations.add(coord)
                    continue
                if coord == _APPLICANT_FORWARD_FRAGMENT:
                    if forward_fragment is not None:
                        raise RuntimeError("Perugia duplicate forward applicant fragment")
                    forward_fragment = cells
                    continue

                current = list(cells)
                fragments: list[dict[str, Any]] = []
                if forward_fragment is not None:
                    current = _append_fragment(current, forward_fragment, prepend=True)
                    fragments.append(
                        {
                            "page": _APPLICANT_FORWARD_FRAGMENT[0],
                            "row": _APPLICANT_FORWARD_FRAGMENT[1],
                            "cells": list(forward_fragment),
                            "direction": "following-row",
                        }
                    )
                    forward_fragment = None
                rows.append(
                    {
                        "page": page_number,
                        "row": row_number,
                        "cells": tuple(current),
                        "fragments": fragments,
                    }
                )

    if forward_fragment is not None:
        raise RuntimeError("Perugia unconsumed applicant forward fragment")
    if physical != _APPLICANT_PHYSICAL_ROWS:
        raise RuntimeError(
            f"Perugia applicant physical-row drift: {physical} != {_APPLICANT_PHYSICAL_ROWS}"
        )
    if blanks != 23 or header_count != 1:
        raise RuntimeError(
            f"Perugia applicant blank/header drift: blanks={blanks}; headers={header_count}"
        )
    if continuations != _APPLICANT_CONTINUATIONS:
        raise RuntimeError(
            f"Perugia applicant continuation population drift: "
            f"{sorted(continuations)!r} != {sorted(_APPLICANT_CONTINUATIONS)!r}"
        )
    if len(rows) != _APPLICANT_RECORDS:
        raise RuntimeError(
            f"Perugia applicant logical-row drift: {len(rows)} != {_APPLICANT_RECORDS}"
        )

    blank_names = {ordinal for ordinal, row in enumerate(rows, start=1) if not row["cells"][0]}
    if blank_names != set(_APPLICANT_BLANK_NAME):
        raise RuntimeError(f"Perugia applicant blank-name population drift: {blank_names!r}")
    for ordinal, expected in _APPLICANT_BLANK_NAME.items():
        c = rows[ordinal - 1]["cells"]
        observed = (c[1], c[3], c[4], c[5], c[6])
        if observed != expected:
            raise RuntimeError(
                f"Perugia applicant reviewed blank-name row drift at ordinal {ordinal}: {observed!r}"
            )

    empty_dates = {ordinal for ordinal, row in enumerate(rows, start=1) if not row["cells"][5]}
    if empty_dates != _APPLICANT_EMPTY_APPLICATION_ORDINALS:
        raise RuntimeError(
            f"Perugia applicant empty application-date population drift: {empty_dates!r}"
        )

    strict_count = sum(bool(_strict_identifier(row["cells"][3])) for row in rows)
    if strict_count != 1186:
        raise RuntimeError(
            f"Perugia applicant strict-identifier coverage drift: {strict_count} != 1186"
        )
    return rows


def _applicant_application_date(ordinal: int, row: dict[str, Any]) -> str:
    c = row["cells"]
    raw = c[5]
    if ordinal in _APPLICANT_EMPTY_APPLICATION_ORDINALS:
        if raw:
            raise RuntimeError(
                f"Perugia applicant reviewed empty application date drift at ordinal {ordinal}: {raw!r}"
            )
        return ""
    reviewed = _APPLICANT_UNPARSED_APPLICATION.get(ordinal)
    if reviewed is not None:
        expected_name, expected_raw = reviewed
        if c[0] != expected_name or raw != expected_raw:
            raise RuntimeError(
                f"Perugia applicant reviewed application-date exception drift at ordinal {ordinal}: "
                f"name={c[0]!r}; raw={raw!r}"
            )
        return ""
    return _calendar_date(raw, context=f"applicant ordinal {ordinal} application")


def _applicant_status_and_decision(ordinal: int, name: str, outcome: str) -> tuple[str, str]:
    value = _clean(outcome)
    if not value:
        return "pending", ""
    reviewed_bare = _APPLICANT_BARE_OUTCOME.get(ordinal)
    if reviewed_bare is not None:
        if (name, value) != reviewed_bare:
            raise RuntimeError(
                f"Perugia applicant reviewed bare outcome drift at ordinal {ordinal}: "
                f"{(name, value)!r}"
            )
        return "other_or_unknown", ""

    folded = value.casefold()
    if not (
        folded.startswith("rinnovo")
        or folded.startswith("iscritta")
        or folded.startswith("iscrizione")
    ):
        raise RuntimeError(
            f"Perugia applicant unreviewed nonblank outcome at ordinal {ordinal}: {value!r}"
        )

    date_matches = re.findall(r"\b\d{1,2}[./]\d{1,2}[./]\d{4}\b", value)
    if len(date_matches) == 1:
        decision = _calendar_date(
            date_matches[0], context=f"applicant ordinal {ordinal} decision outcome"
        )
        return "listed", decision
    if len(date_matches) > 1:
        raise RuntimeError(
            f"Perugia applicant multiple decision dates at ordinal {ordinal}: {date_matches!r}"
        )

    reviewed_missing = _APPLICANT_MISSING_DECISION_DATES.get(ordinal)
    if reviewed_missing != (name, value):
        raise RuntimeError(
            f"Perugia applicant unreviewed positive outcome without decision date "
            f"at ordinal {ordinal}: {(name, value)!r}"
        )
    return "listed", ""


def parse_perugia_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    _validate_cfg(
        cfg,
        source_key="perugia-applicants",
        population_scope="applicant",
        sha256=_APPLICANT_SHA256,
    )
    if _sha256(path) != _APPLICANT_SHA256:
        raise RuntimeError("Perugia applicant source bytes drift from approved SHA-256")

    source_rows = _applicant_source_rows(path)
    records: list[dict[str, Any]] = []
    for ordinal, row in enumerate(source_rows, start=1):
        c = row["cells"]
        application_date = _applicant_application_date(ordinal, row)
        status, decision_date = _applicant_status_and_decision(ordinal, c[0], c[6])
        strict_id = _strict_identifier(c[3])
        activities = [_clean(item) for item in c[4].split(";") if _clean(item)]

        record = _record(
            cfg,
            ordinal,
            name=c[0],
            office=c[1],
            secondary=c[2],
            identifier_raw=c[3],
            activities=activities,
            status=status,
            outcome_raw=c[6],
            application_date=application_date,
            decision_date=decision_date,
            primary_date_label="Data presentazione istanza",
            source_fields={
                "activities_raw": c[4],
                "application_date_raw": c[5],
                "outcome_raw": c[6],
                "source_page": row["page"],
                "source_table_row": row["row"],
                "continuation_fragments": row["fragments"],
                "reviewed_blank_company_name": ordinal in _APPLICANT_BLANK_NAME,
                "reviewed_application_date_exception": (
                    ordinal in _APPLICANT_EMPTY_APPLICATION_ORDINALS
                    or ordinal in _APPLICANT_UNPARSED_APPLICATION
                ),
                "reviewed_missing_decision_date": ordinal in _APPLICANT_MISSING_DECISION_DATES,
                "reviewed_bare_outcome": ordinal in _APPLICANT_BARE_OUTCOME,
            },
        )
        record["identifiers"] = [strict_id] if strict_id else []
        records.append(record)

    status_counts = dict(Counter(record["source_status"] for record in records))
    if status_counts != _EXPECTED_APPLICANT_STATUS_COUNTS:
        raise RuntimeError(f"Perugia applicant status drift: {status_counts!r}")
    decision_count = sum(bool(record["decision_date"]) for record in records)
    if decision_count != 1033:
        raise RuntimeError(
            f"Perugia applicant normalised decision-date count drift: {decision_count} != 1033"
        )

    return ParsedBatch(
        records=records,
        diagnostics={
            "parser": "perugia_applicants",
            "parser_version": PARSER_VERSION,
            "source_pages": _APPLICANT_PAGES,
            "physical_rows": _APPLICANT_PHYSICAL_ROWS,
            "public_records": len(records),
            "status_counts": status_counts,
            "strict_identifier_records": 1186,
            "reviewed_previous_row_continuations": len(_APPLICANT_CONTINUATIONS),
            "reviewed_following_row_fragments": 1,
            "reviewed_empty_application_dates": len(_APPLICANT_EMPTY_APPLICATION_ORDINALS),
            "reviewed_unparsed_application_dates": len(_APPLICANT_UNPARSED_APPLICATION),
            "reviewed_missing_decision_dates": len(_APPLICANT_MISSING_DECISION_DATES),
            "reviewed_blank_company_names": len(_APPLICANT_BLANK_NAME),
            "normalised_decision_dates": decision_count,
        },
    )


PARSERS = {
    "perugia_listed": parse_perugia_listed,
    "perugia_applicants": parse_perugia_applicants,
}
