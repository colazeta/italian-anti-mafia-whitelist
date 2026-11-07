"""Private structural diagnostics; never parser acceptance or edition approval.

Only fixed field names, bounded counts and booleans leave this module. Source
strings and exception messages are deliberately excluded, including on failure.
The caller must verify archived bytes before inspection.
"""
from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path
from typing import Any


def inspect_quarantined_structure(path: Path, parser_name: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": 1,
        "inspection_completed": False,
        "edition_approval": False,
        "parser_compatibility_approved": False,
        "source_reference_date": None,
    }
    try:
        if parser_name in {"lodi_listed", "lodi_applicants"}:
            result.update(_lodi(path, listed=parser_name == "lodi_listed"))
        elif parser_name == "milano_combined":
            result.update(_milano(path))
        else:
            result["supported_inspector"] = False
            return result
    except Exception:
        # CSV/HTML/encoding errors can quote source rows in their messages.
        # Failed inspection leaves the original quarantine intact.
        return result
    result["supported_inspector"] = True
    result["inspection_completed"] = True
    return result


def _lodi(path: Path, *, listed: bool) -> dict[str, Any]:
    from white_list_archive.parsers import lodi_sheets as reviewed

    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle, strict=True))
    widths = Counter(len(row) for row in rows)
    expected_rows = reviewed._LISTED_PHYSICAL_ROWS if listed else reviewed._APPLICANT_PHYSICAL_ROWS
    expected_headers = reviewed._LISTED_HEADER_ROWS if listed else reviewed._APPLICANT_HEADER_ROWS
    last_header_column = 4 if listed else 6
    last_header_marker = "data" if listed else "esito"
    header_matches = sum(
        0 < n <= len(rows)
        and len(rows[n - 1]) == 7
        and "ragione sociale" in rows[n - 1][0].casefold()
        and last_header_marker in rows[n - 1][last_header_column].casefold()
        for n in expected_headers
    )
    result = {
        "physical_rows": len(rows),
        "reviewed_physical_row_count_matches": len(rows) == expected_rows,
        "seven_column_rows": widths[7],
        "other_width_rows": sum(count for width, count in widths.items() if width != 7),
        "reviewed_header_positions": len(expected_headers),
        "reviewed_header_position_matches": header_matches,
        "section_marker_rows": sum(
            bool(re.fullmatch(r"Sezione\s+[IVX]+", " ".join(cell.split()), re.I))
            for row in rows for cell in row
        ),
    }
    if listed:
        result["reviewed_section_positions"] = len(reviewed._LISTED_SECTION_ROWS)
        result["reviewed_section_position_matches"] = sum(
            0 < n <= len(rows)
            and [" ".join(cell.split()) for cell in rows[n - 1] if cell.strip()] == [f"Sezione {section}"]
            for n, section in reviewed._LISTED_SECTION_ROWS.items()
        )
    return result


def _milano(path: Path) -> dict[str, Any]:
    from white_list_archive.parsers import milano_webapp as reviewed

    tables = reviewed._parse_tables(reviewed._decode(path))
    heading_matches = 0
    header_matches = 0
    data_rows = 0
    six_column_rows = 0
    for n, table in enumerate(tables):
        if n < len(reviewed._EXPECTED_SECTION_PREFIXES) and table and table[0]:
            heading_matches += reviewed._clean(table[0][0]) == reviewed._EXPECTED_SECTION_PREFIXES[n]
        if len(table) > 1:
            header_matches += tuple(reviewed._clean(cell) for cell in table[1]) == reviewed._HEADER
        for cells in table[2:]:
            if any(cell.strip() for cell in cells):
                data_rows += 1
                six_column_rows += len(cells) == 6
    return {
        "source_tables": len(tables),
        "reviewed_table_count_matches": len(tables) == reviewed._EXPECTED_TABLES,
        "reviewed_section_heading_matches": heading_matches,
        "reviewed_table_header_matches": header_matches,
        "nonblank_data_rows": data_rows,
        "six_column_data_rows": six_column_rows,
        "other_width_data_rows": data_rows - six_column_rows,
        "reviewed_sector_row_count_matches": data_rows == reviewed._EXPECTED_SECTOR_ROWS,
    }
