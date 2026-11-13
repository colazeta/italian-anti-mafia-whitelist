"""Exact-source Perugia 5 November 2026 PDF adapter.

The September parser and its exception populations remain immutable. This
adapter shares only stateless cell/date helpers; it never patches legacy globals.
All source rows and cross-page stitching are fingerprinted before projection.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import pdfplumber

from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch, _record
from white_list_archive.parsers.perugia_tables import (
    _append_fragment, _calendar_date, _clean, _date_obj, _sha256, _strict_identifier,
)

PARSER_VERSION = "2"
_REFERENCE_DATE = "2026-11-05"
_PINS = {
    "listed": "d8dd83ac23e8fd1fa3b3913423d0b08ff5b1bc12a964738d4ff1a8499fa274f8",
    "applicants": "c049e8ec3d94f3a87ec7e6749cdd5f88b769c318156d38a51bba07b777762e77",
}
_PROFILE = {'listed': {'pages': 225,
            'physical': 1921,
            'blanks': 38,
            'headers': [[1, 1],
                        [30, 1],
                        [42, 1],
                        [89, 1],
                        [107, 1],
                        [157, 1],
                        [195, 1],
                        [197, 1],
                        [199, 1],
                        [206, 1]],
            'previous': [[58, 1], [68, 1], [120, 1], [152, 1], [162, 1], [175, 1]],
            'no_tables': [194],
            'logical_rows': 1867,
            'row_digest': '69d0b1f633e2329c84bd121ef34d82268dc5f2df11ed3afb07f352c68f4dee0f'},
 'applicants': {'pages': 187,
                'physical': 1316,
                'blanks': 17,
                'headers': [[1, 1]],
                'previous': [[3, 1],
                             [6, 1],
                             [8, 1],
                             [13, 1],
                             [17, 1],
                             [19, 1],
                             [20, 1],
                             [24, 1],
                             [30, 1],
                             [35, 1],
                             [36, 1],
                             [46, 1],
                             [50, 1],
                             [51, 1],
                             [59, 1],
                             [62, 1],
                             [70, 1],
                             [72, 1],
                             [74, 1],
                             [75, 1],
                             [79, 1],
                             [81, 1],
                             [83, 1],
                             [97, 1],
                             [99, 1],
                             [103, 1],
                             [104, 1],
                             [106, 1],
                             [107, 1],
                             [115, 1],
                             [116, 1],
                             [118, 1],
                             [121, 1],
                             [123, 1],
                             [126, 1],
                             [128, 1],
                             [130, 1],
                             [131, 1],
                             [137, 1],
                             [140, 1],
                             [141, 1],
                             [142, 1],
                             [148, 1],
                             [154, 1],
                             [161, 1],
                             [162, 1],
                             [164, 1],
                             [168, 1],
                             [169, 1],
                             [171, 1],
                             [172, 1],
                             [179, 1],
                             [181, 1],
                             [184, 1]],
                'no_tables': [187],
                'logical_rows': 1243,
                'row_digest': '550446e98df532e539e2a193cdaa3df68fac6141cfc853bc6f24ad22cbdcc39c'}}
_SECTIONS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")
_SECTION_COUNTS = {"I": 256, "II": 108, "III": 404, "IV": 145, "V": 442,
                   "VI": 252, "VII": 12, "VIII": 8, "IX": 68, "X": 172}
_COUNTS = {"listed": 1020, "applicants": 1243}
_STATUSES = {
    "listed": {"listed": 642, "renewal_update_in_progress": 378},
    "applicants": {"listed": 1038, "pending": 204, "other_or_unknown": 1},
}
_LISTED_RAW_DATES = {(17, 4, 5), (37, 2, 4), (66, 7, 4), (105, 7, 4),
                     (163, 5, 5), (200, 8, 4), (200, 8, 5)}
_APPLICANT_RAW_DATES = {(2, 5, 5), (35, 5, 5), (68, 5, 5), (105, 4, 5),
                        (110, 2, 5), (123, 3, 5), (126, 4, 5), (126, 5, 5),
                        (126, 6, 5), (138, 3, 5), (178, 4, 5)}
_MISSING_DECISION = {(18, 1), (72, 5), (146, 1)}
_BARE_OUTCOME = (185, 2)
_FORWARD = (6, 6)
_INVERSIONS = {(38, 1), (104, 7), (188, 3), (205, 3), (220, 7)}


def _digest(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _validate(path: Path, cfg: dict[str, Any], label: str) -> None:
    expected = {"authority_key": "perugia", "register_key": "perugia-ordinary",
                "source_key": f"perugia-{label}", "reference_date": _REFERENCE_DATE,
                "population_scope": "listed" if label == "listed" else "applicant",
                "sha256": _PINS[label], "parser": f"perugia_{label}_2026_11"}
    if any(cfg.get(k) != v for k, v in expected.items()):
        raise RuntimeError("Perugia November source configuration drift")
    if _sha256(path) != _PINS[label]:
        raise RuntimeError("Perugia November original SHA-256 drift")


def _source_rows(path: Path, label: str) -> list[dict[str, Any]]:
    profile = _PROFILE[label]
    previous = {tuple(c) for c in profile["previous"]}
    headers = {tuple(c) for c in profile["headers"]}
    rows: list[dict[str, Any]] = []
    seen_headers = set()
    seen_previous = set()
    physical = blanks = 0
    forward = None
    section = ""
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != profile["pages"]:
            raise RuntimeError("Perugia November page-count drift")
        for pno, page in enumerate(pdf.pages, 1):
            tables = page.find_tables()
            if len(tables) != (0 if pno in profile["no_tables"] else 1):
                raise RuntimeError(f"Perugia November table-layout drift p{pno}")
            for table in tables:
                for rno, raw in enumerate(table.extract() or [], 1):
                    physical += 1
                    cells = tuple(_clean(v) for v in raw)
                    coord = (pno, rno)
                    if len(cells) != 7:
                        raise RuntimeError("Perugia November column-count drift")
                    if not any(cells):
                        blanks += 1
                        continue
                    if coord in headers:
                        if cells[0] != "Ragione Sociale":
                            raise RuntimeError("Perugia November header drift")
                        seen_headers.add(coord)
                        if label == "listed":
                            section = _SECTIONS[profile["headers"].index(list(coord))]
                        continue
                    if cells[0] == "Ragione Sociale":
                        raise RuntimeError("Perugia November unreviewed repeated header")
                    if label == "applicants" and coord == _FORWARD:
                        if forward is not None:
                            raise RuntimeError("Perugia November repeated forward fragment")
                        forward = cells
                        continue
                    if coord in previous:
                        if not rows or rows[-1]["section"] != section:
                            raise RuntimeError("Perugia November orphan/cross-section continuation")
                        rows[-1]["cells"] = tuple(_append_fragment(list(rows[-1]["cells"]), cells))
                        rows[-1]["fragments"].append({"page": pno, "row": rno, "cells": list(cells)})
                        seen_previous.add(coord)
                        continue
                    fragments = []
                    if forward is not None:
                        cells = tuple(_append_fragment(list(cells), forward, prepend=True))
                        fragments = [{"page": _FORWARD[0], "row": _FORWARD[1],
                                      "cells": list(forward), "direction": "following-row"}]
                        forward = None
                    rows.append({"page": pno, "row": rno, "cells": cells,
                                 "fragments": fragments, "section": section})
    if (forward is not None or physical != profile["physical"] or blanks != profile["blanks"]
            or seen_headers != headers or seen_previous != previous
            or len(rows) != profile["logical_rows"] or _digest(rows) != profile["row_digest"]):
        raise RuntimeError("Perugia November finite source-row/stitching contract drift")
    if label == "listed" and dict(Counter(r["section"] for r in rows)) != _SECTION_COUNTS:
        raise RuntimeError("Perugia November statutory-section denominator drift")
    return rows


def _date(row: dict, col: int, label: str) -> str:
    coord = (row["page"], row["row"], col)
    raw_dates = _LISTED_RAW_DATES if label == "listed" else _APPLICANT_RAW_DATES
    if coord in raw_dates:
        return ""
    return _calendar_date(row["cells"][col], context="November reviewed source")


def _outcome(row: dict) -> tuple[str, str]:
    value = row["cells"][6]
    coord = (row["page"], row["row"])
    if not value:
        return "pending", ""
    if coord == _BARE_OUTCOME:
        return "other_or_unknown", ""
    if not value.casefold().startswith(("rinnovo", "iscritta", "iscrizione")):
        raise RuntimeError("Perugia November unreviewed outcome typography")
    if coord in _MISSING_DECISION:
        return "listed", ""
    matches = re.findall(r"\b\d{1,2}[./]\d{1,2}[./]\d{4}\b", value)
    if len(matches) != 1:
        raise RuntimeError("Perugia November unreviewed decision-date typography")
    return "listed", _calendar_date(matches[0], context="November labelled outcome")


def _listed(rows: list[dict], cfg: dict) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    inversions = set()
    for row in rows:
        c = row["cells"]
        listing, expiry = _date(row, 4, "listed"), _date(row, 5, "listed")
        if listing and expiry and _date_obj(expiry) < _date_obj(listing):
            inversions.add((row["page"], row["row"]))
        if c[6] not in ("", "SI"):
            raise RuntimeError("Perugia November unreviewed update marker")
        strict = _strict_identifier(c[3])
        identity = strict or f"NAME:{_clean(c[0]).casefold()}"
        key = (identity, c[4], c[5], c[6])
        group = grouped.setdefault(key, {"first": row, "strict": strict, "sections": [],
                                         "memberships": [], "names": [], "offices": [],
                                         "secondary": [], "identifiers": []})
        section = f"Sezione {row['section']}"
        if section not in group["sections"]:
            group["sections"].append(section)
        for k, v in (("names", c[0]), ("offices", c[1]), ("secondary", c[2]), ("identifiers", c[3])):
            if v and v not in group[k]:
                group[k].append(v)
        group["memberships"].append({"page": row["page"], "row": row["row"], "section": row["section"],
            "name_raw": c[0], "registered_office_raw": c[1], "secondary_office_raw": c[2],
            "identifier_raw": c[3], "listing_date_raw": c[4], "expiry_date_raw": c[5],
            "update_raw": c[6], "continuation_fragments": row["fragments"]})
    if inversions != _INVERSIONS:
        raise RuntimeError("Perugia November chronology exception population drift")
    records = []
    for ordinal, g in enumerate(grouped.values(), 1):
        row = g["first"]; c = row["cells"]; coord = (row["page"], row["row"])
        record = _record(cfg, ordinal, name=c[0], office=c[1], secondary=c[2], identifier_raw=c[3],
            activities=g["sections"], status="renewal_update_in_progress" if c[6] == "SI" else "listed",
            outcome_raw=c[6], listing_date=_date(row, 4, "listed"), expiry_date=_date(row, 5, "listed"),
            primary_date_label="Data iscrizione", source_fields={
                "sections": g["sections"], "source_memberships": g["memberships"],
                "name_variants": g["names"], "registered_office_variants": g["offices"],
                "secondary_office_variants": g["secondary"], "identifier_raw_variants": g["identifiers"],
                "listing_date_raw": c[4], "expiry_date_raw": c[5], "update_raw": c[6],
                "reviewed_date_exception": any((*coord, col) in _LISTED_RAW_DATES for col in (4, 5)),
                "reviewed_chronology_inversion": coord in _INVERSIONS})
        record["identifiers"] = [g["strict"]] if g["strict"] else []
        records.append(record)
    return records


def _applicants(rows: list[dict], cfg: dict) -> list[dict]:
    records = []
    for ordinal, row in enumerate(rows, 1):
        c = row["cells"]; coord = (row["page"], row["row"])
        status, decision = _outcome(row)
        record = _record(cfg, ordinal, name=c[0], office=c[1], secondary=c[2], identifier_raw=c[3],
            activities=[_clean(a) for a in c[4].split(";") if _clean(a)], status=status,
            outcome_raw=c[6], application_date=_date(row, 5, "applicants"), decision_date=decision,
            primary_date_label="Data presentazione istanza", source_fields={
                "activities_raw": c[4], "application_date_raw": c[5], "outcome_raw": c[6],
                "source_page": row["page"], "source_table_row": row["row"],
                "continuation_fragments": row["fragments"], "reviewed_blank_company_name": False,
                "reviewed_application_date_exception": (*coord, 5) in _APPLICANT_RAW_DATES,
                "reviewed_missing_decision_date": coord in _MISSING_DECISION,
                "reviewed_bare_outcome": coord == _BARE_OUTCOME})
        strict = _strict_identifier(c[3]); record["identifiers"] = [strict] if strict else []
        records.append(record)
    return records


def _parse(path: Path, cfg: dict, label: str) -> ParsedBatch:
    _validate(path, cfg, label)
    rows = _source_rows(path, label)
    expected_strict = 1829 if label == "listed" else 1215
    if sum(bool(_strict_identifier(r["cells"][3])) for r in rows) != expected_strict:
        raise RuntimeError("Perugia November strict-identifier denominator drift")
    records = _listed(rows, cfg) if label == "listed" else _applicants(rows, cfg)
    statuses = dict(Counter(r["source_status"] for r in records))
    if len(records) != _COUNTS[label] or statuses != _STATUSES[label] or any(not r["name"] for r in records):
        raise RuntimeError("Perugia November record/name/status denominator drift")
    if label == "applicants" and sum(bool(r["decision_date"]) for r in records) != 1035:
        raise RuntimeError("Perugia November labelled-decision denominator drift")
    return ParsedBatch(records=records, diagnostics={"parser": cfg["parser"],
        "parser_version": PARSER_VERSION, "source_pages": _PROFILE[label]["pages"],
        "physical_rows": _PROFILE[label]["physical"], "source_rows": len(rows),
        "public_records": len(records), "status_counts": statuses,
        "strict_identifier_source_rows": expected_strict,
        "reviewed_previous_row_continuations": len(_PROFILE[label]["previous"]),
        "reviewed_following_row_fragments": int(label == "applicants")})


def parse_perugia_listed(path: Path, cfg: dict) -> ParsedBatch:
    return _parse(path, cfg, "listed")


def parse_perugia_applicants(path: Path, cfg: dict) -> ParsedBatch:
    return _parse(path, cfg, "applicants")


PARSERS = {"perugia_listed_2026_11": parse_perugia_listed,
           "perugia_applicants_2026_11": parse_perugia_applicants}
