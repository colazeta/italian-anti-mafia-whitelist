from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

import pdfplumber


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\u00a0", " ")).strip()


def inspect(label: str, path: Path) -> None:
    rows = []
    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            tables = page.find_tables()
            text = page.extract_text() or ""
            sections = [clean(line) for line in text.splitlines() if "SEZIONE" in line.upper()]
            if sections or len(tables) != 1:
                print("PAGE", label, page_number, "TABLES", len(tables), "SECTIONS", json.dumps(sections, ensure_ascii=False))
                for table_number, table in enumerate(tables, 1):
                    extracted = table.extract() or []
                    print("TABLE", label, page_number, table_number, "ROWS", len(extracted), "WIDTHS", dict(collections.Counter(len(r or []) for r in extracted)))
                    for row in extracted[:3]:
                        print("HEAD", label, page_number, table_number, json.dumps([clean(x) for x in row], ensure_ascii=False))
            for table_number, table in enumerate(tables, 1):
                for row_number, raw in enumerate(table.extract() or [], 1):
                    values = [clean(x) for x in raw]
                    if not values or not any(values) or "ragione sociale" in " ".join(values).casefold():
                        continue
                    if len(values) >= 4 and values[0] and values[1] and re.fullmatch(r"(?:\d{11}|[A-Za-z0-9]{16})", values[3] or ""):
                        rows.append((page_number, table_number, row_number, values))
    by_id: dict[str, list] = collections.defaultdict(list)
    for row in rows:
        by_id[row[3][3]].append(row)
    print("STRICT_ROWS", label, len(rows), "WIDTHS", dict(collections.Counter(len(r[3]) for r in rows)))
    print("UNIQUE_IDS", label, len(by_id), "MULTIPLICITIES", sorted(collections.Counter(len(v) for v in by_id.values()).items()))
    conflicts = []
    for identifier, items in by_id.items():
        suffixes = collections.Counter(tuple(item[3][4:]) for item in items)
        if len(suffixes) > 1:
            conflicts.append((identifier, len(items), list(suffixes.items())))
    print("SUFFIX_CONFLICTS", label, len(conflicts), json.dumps(conflicts[:80], ensure_ascii=False))
    repeated = []
    for identifier, items in by_id.items():
        if len(items) > 1:
            repeated.append((identifier, len(items), [[x[0], x[1], x[2], x[3]] for x in items[:12]]))
    print("REPEATED", label, json.dumps(repeated[:40], ensure_ascii=False))


if __name__ == "__main__":
    inspect(sys.argv[1], Path(sys.argv[2]))
