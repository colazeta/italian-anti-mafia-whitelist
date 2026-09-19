from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

import pdfplumber


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\u00a0", " ")).strip()


def _is_header(values: list[str]) -> bool:
    joined = " ".join(values).casefold()
    return "ragione sociale" in joined


def _is_strict_data_row(values: list[str]) -> bool:
    return (
        len(values) >= 4
        and bool(values[0])
        and bool(values[1])
        and bool(re.fullmatch(r"(?:\d{11}|[A-Za-z0-9]{16})", values[3] or ""))
    )


def inspect(label: str, path: Path) -> None:
    rows = []
    physical_rows: list[tuple[int, int, int, list[str]]] = []
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
                    if not values or not any(values):
                        continue
                    physical_rows.append((page_number, table_number, row_number, values))
                    if _is_header(values):
                        continue
                    if _is_strict_data_row(values):
                        rows.append((page_number, table_number, row_number, values))

    if label == "applicants":
        anomalies = []
        for index, item in enumerate(physical_rows):
            page_number, table_number, row_number, values = item
            if _is_header(values) or _is_strict_data_row(values):
                continue
            previous = None
            for candidate in reversed(physical_rows[:index]):
                if _is_strict_data_row(candidate[3]):
                    previous = candidate
                    break
            following = None
            for candidate in physical_rows[index + 1 :]:
                if _is_strict_data_row(candidate[3]):
                    following = candidate
                    break
            anomalies.append(
                {
                    "page": page_number,
                    "table": table_number,
                    "row": row_number,
                    "values": values,
                    "previous_strict": None
                    if previous is None
                    else {
                        "page": previous[0],
                        "table": previous[1],
                        "row": previous[2],
                        "values": previous[3],
                    },
                    "next_strict": None
                    if following is None
                    else {
                        "page": following[0],
                        "table": following[1],
                        "row": following[2],
                        "values": following[3],
                    },
                }
            )
        print("APPLICANT_NONSTRICT_ROW_COUNT", len(anomalies))
        for item in anomalies:
            print("APPLICANT_NONSTRICT_ROW", json.dumps(item, ensure_ascii=False, sort_keys=True))

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
    if label == "listed":
        marker_sets = collections.Counter()
        marker_values = collections.Counter()
        mixed = []
        grouped_status = collections.Counter()
        for identifier, items in by_id.items():
            markers = []
            for item in items:
                values = item[3]
                marker = clean(values[6]) if len(values) >= 7 else ""
                markers.append(marker)
                marker_values[marker] += 1
            folded = {value.casefold() for value in markers if value}
            marker_sets[tuple(sorted(folded))] += 1
            nonblank = [value for value in markers if value]
            status = "renewal_update_in_progress" if nonblank else "listed"
            grouped_status[status] += 1
            if nonblank and any(not value for value in markers):
                mixed.append((identifier, markers))
        print("LISTED_MARKER_VALUES", json.dumps(marker_values.most_common(), ensure_ascii=False))
        print("LISTED_GROUPED_STATUS", json.dumps(grouped_status, ensure_ascii=False))
        print("LISTED_GROUP_MARKER_SETS", json.dumps([[list(k), v] for k, v in marker_sets.items()], ensure_ascii=False))
        print("LISTED_MIXED_BLANK_NONBLANK", len(mixed), json.dumps(mixed[:80], ensure_ascii=False))
    repeated = []
    for identifier, items in by_id.items():
        if len(items) > 1:
            repeated.append((identifier, len(items), [[x[0], x[1], x[2], x[3]] for x in items[:12]]))
    print("REPEATED", label, json.dumps(repeated[:20], ensure_ascii=False))


if __name__ == "__main__":
    inspect(sys.argv[1], Path(sys.argv[2]))
