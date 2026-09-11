from __future__ import annotations

import hashlib
import json
import re
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

import pdfplumber

URL = "https://prefettura.interno.gov.it/sites/default/files/104/2026-09/white-list-prefettura-di-barletta-andria-trani_1.pdf"
SHA = "d3c0e61942cbdefd03cfa7d99f71b2abbfc430f25ff86b8693d44ef14de07e13"
SECTION = re.compile(r"\bSezione\s+([IVX]+)\b", re.I)
STRICT_ID = re.compile(r"(?<![A-Za-z0-9])(?:\d{11}|[A-Za-z0-9]{16})(?![A-Za-z0-9])", re.I)
DATE_FIELDISH = re.compile(r"(?=.*\d)(?=.*[/.-]).+")
VALID_DATE = re.compile(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{4})$")
ADMIN = ("denominazio", "ragione sociale", "elenco fornitori", "p.i./cf", "iscrizione nelle white", "provvediment")


def clean(v: object) -> str:
    return " ".join(str(v or "").replace("\u00a0", " ").split())


def strict_ids(text: str) -> list[str]:
    return [m.group(0).upper() for m in STRICT_ID.finditer(clean(text))]


def normalized_date(raw: str) -> str | None:
    value = clean(raw)
    m = VALID_DATE.fullmatch(value)
    if not m:
        return None
    day, month, year = map(int, m.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def main() -> None:
    req = Request(URL, headers={"User-Agent": "ItalianAntiMafiaWhitelistArchive/1.0 date-field-audit"})
    with urlopen(req, timeout=90) as response:
        body = response.read()
    assert hashlib.sha256(body).hexdigest() == SHA

    rows = []
    current_section = None
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(body); tmp.flush()
        with pdfplumber.open(tmp.name) as pdf:
            assert len(pdf.pages) == 211
            for pno, page in enumerate(pdf.pages, 1):
                text = clean(page.extract_text() or "")
                marker = SECTION.search(text)
                if marker:
                    current_section = marker.group(1).upper()
                for table in page.find_tables():
                    for ridx, raw in enumerate(table.extract() or [], 1):
                        row = [clean(cell) for cell in raw]
                        if not any(row):
                            continue
                        joined = " | ".join(row)
                        if any(token in joined.casefold() for token in ADMIN):
                            continue
                        ids = strict_ids(" | ".join(row[2:]))
                        fieldish = [(idx, value) for idx, value in enumerate(row[2:], 2) if value and DATE_FIELDISH.fullmatch(value)]
                        # A company sector row has a legal name and at least one identifier/date signal.
                        if not row[0] or not (ids or fieldish):
                            continue
                        # Date fields are after the identifier area. Addresses live in col 1 and are excluded.
                        # Keep date-looking cells only; protocol numbers contain no slash/dot and therefore never enter.
                        candidates = [(idx, value) for idx, value in fieldish if idx >= 3]
                        if not candidates:
                            continue
                        rows.append({
                            "page": pno,
                            "row": ridx,
                            "section": current_section,
                            "name": row[0],
                            "ids": ids,
                            "cells": row,
                            "date_field_candidates": candidates,
                        })

    # The reviewed sector denominator is 1,013; audit only those with date-field signals.
    # Select the final one/two date-looking values from the post-identifier cells, because intermediary
    # protocol/reference columns can contain non-date numbers but not slash/dot date text.
    selected = []
    bad = []
    valid_raw = Counter()
    for rec in rows:
        values = [value for _idx, value in rec["date_field_candidates"]]
        # Known source schema has two dates for ordinary listed rows; a few malformed/extraction rows expose one.
        chosen = values[-2:] if len(values) >= 2 else values
        parsed = []
        for value in chosen:
            norm = normalized_date(value)
            parsed.append({"raw": value, "normalized": norm})
            if norm is None:
                bad.append({"page": rec["page"], "row": rec["row"], "section": rec["section"], "name": rec["name"], "raw": value, "cells": rec["cells"]})
            else:
                valid_raw[value] += 1
        selected.append({"page": rec["page"], "row": rec["row"], "section": rec["section"], "name": rec["name"], "dates": parsed})

    out = {
        "source_sha256": SHA,
        "rows_with_date_fields": len(selected),
        "rows_with_one_selected_date": sum(len(x["dates"]) == 1 for x in selected),
        "rows_with_two_selected_dates": sum(len(x["dates"]) == 2 for x in selected),
        "invalid_date_field_occurrences": len(bad),
        "invalid_date_field_values": dict(Counter(x["raw"] for x in bad)),
        "invalid_date_fields": bad,
        "dot_format_valid_values": {k: v for k, v in valid_raw.items() if "." in k},
    }
    Path("tmp/barletta-andria-trani-date-fields.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("rows_with_date_fields", "rows_with_one_selected_date", "rows_with_two_selected_dates", "invalid_date_field_occurrences", "invalid_date_field_values", "dot_format_valid_values")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
