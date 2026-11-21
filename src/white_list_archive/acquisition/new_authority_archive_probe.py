"""Redacted read-only R2 workbook preflight for three unpublished White List authorities.

Original-byte SHA pins are frozen robot-discovery candidates, not source approvals.
No individual values, worksheet titles, URLs, source locators or storage coordinates
leave this protected step. This module never writes, publishes or infers dates.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from hashlib import sha256
from io import BytesIO
import json
import re

from openpyxl import load_workbook

from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for


# Exact 21 November 2026 robot-state@2890d347... archive candidate metadata.
# The November filename, HTTP Last-Modified or discovery timestamp is NOT an
# approved document edition date. Alternative Novara PDFs are separate evidence.
PINS = {
    "novara": (
        ("listed", "27a4514dcb0ddb77786c64faf186b7b855d9f616389ec8c3d4bec504bea771a2", 37187),
        ("applicant", "ef0486870ddb136fdf2e876a563e1b3c91e814bfcaf27a1d3a9baf10dd76cdcf", 32038),
    ),
    "rieti": (
        ("listed", "09386dcff207a094cfd796b9f040966d232dcd8967b293a8b5d66b99a45114f4", 50161),
        ("applicant", "e229ded9a6098d7f5ffea5ad6599cfdf46f146655676fe5a2288f3c79dca4a75", 46244),
    ),
    "vicenza": (
        ("listed", "f1af1fe0a99c8fafcf05537721b39a80c2072a4ea524f2c61b4b9f5466c43f50", 68748),
        ("applicant", "88c10b8aee68ec4359f33572dc72d7222195684f7a5b0ae392586d29c3975c9d", 11101),
    ),
}

MAX_SHEETS = 25
MAX_COLUMNS = 120
MAX_ROWS = 50000
MAX_CELLS = 500000
MAX_BYTES = 2500000


def cell_shape(value: object) -> str:
    """Only non-identifying shapes: no raw value or inferred entity type."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return "blank"
    if isinstance(value, (datetime, date)):
        return "date_typed_cell"
    if isinstance(value, str) and value.startswith("="):
        return "formula"
    if isinstance(value, str):
        val = value.strip()
        if re.fullmatch(r"[0-9]{11}", val):
            return "eleven_digit_shape"
        if re.fullmatch(r"[A-Za-z0-9]{16}", val):
            return "sixteen_character_shape_privacy_review"
    return "other_nonblank"


def workbook_structure(raw: bytes) -> dict:
    """Inspect all physical sheets, bounded, without returning source cells.

    This deliberately cannot estimate enterprise counts from spreadsheet rows
    or approve listed/applicant semantics. A second parser/census review is needed.
    """
    if not isinstance(raw, bytes) or not raw.startswith(b"PK") or len(raw) > MAX_BYTES:
        raise ValueError("Not a bounded original XLSX")
    workbook = load_workbook(BytesIO(raw), read_only=True, data_only=False)
    try:
        if not 1 <= len(workbook.worksheets) <= MAX_SHEETS:
            raise ValueError("Unexpected number of XLSX worksheets")
        sheets = []
        total_cells = 0
        for index, ws in enumerate(workbook.worksheets, 1):
            rows, cols = ws.max_row, ws.max_column
            if (not isinstance(rows, int) or not isinstance(cols, int)
                    or rows <= 0 or cols <= 0 or rows > MAX_ROWS
                    or cols > MAX_COLUMNS or rows * cols > MAX_CELLS
                    or total_cells + rows * cols > MAX_CELLS):
                raise ValueError("Unbounded or unknown worksheet dimensions")
            total_cells += rows * cols
            if ws.sheet_state not in ("visible", "hidden", "veryHidden"):
                raise ValueError("Unknown worksheet visibility")
            row_kinds = Counter()
            shapes = Counter()
            observed = 0
            for row in ws.iter_rows(values_only=True):
                present = 0
                for value in row:
                    kind = cell_shape(value)
                    shapes[kind] += 1
                    if kind != "blank":
                        present += 1
                row_kinds["empty" if present == 0 else "single_cell" if present == 1 else "multi_cell"] += 1
                observed += 1
                if observed > rows:
                    raise ValueError("Worksheet exceeds reported physical dimensions")
            if observed != rows:
                raise ValueError("Worksheet row dimensions are not reproducible")
            sheets.append({
                "sheet_index": index,
                "visibility": ws.sheet_state,
                "physical_rows": observed,
                "physical_columns": cols,
                "row_shapes": dict(row_kinds),
                "cell_shapes": dict(shapes),
            })
        if not any(s["row_shapes"].get("multi_cell", 0) for s in sheets):
            raise ValueError("No multi-cell rows for source census")
        return {"worksheets": sheets, "sheet_count": len(sheets),
                "bounded_cell_capacity": total_cells}
    finally:
        workbook.close()


def audit(store: EvidenceStore, pins: dict = PINS) -> dict:
    results = []
    for authority, pair in pins.items():
        if {p for p, _, _ in pair} != {"listed", "applicant"}:
            raise ValueError("Source pair completeness required")
        for population, digest, expected_bytes in pair:
            entry = {"authority": authority, "population": population,
                     "original_sha256": digest, "expected_bytes": expected_bytes}
            try:
                raw = store.read_digest_verified(digest)
                if len(raw) != expected_bytes or sha256(raw).hexdigest() != digest:
                    raise ValueError("Original failed exact size or digest check")
                entry["original_bytes_readback_verified"] = True
                entry["physical_workbook_structure"] = workbook_structure(raw)
            except Exception as exc:
                entry["error_type"] = type(exc).__name__
            results.append(entry)
    return {"review_only": True, "source_edition_approved": False,
            "listed_applicant_semantics_approved": False,
            "privacy_approved": False, "public_release_eligible": False,
            "originals_verified": sum("physical_workbook_structure" in r for r in results),
            "originals_expected": len(results), "results": results}


def main() -> int:
    config = StoreConfig.from_env()
    store = EvidenceStore(client_for(config), config)
    result = audit(store)
    print(json.dumps(result, sort_keys=True))
    return int(result["originals_verified"] != result["originals_expected"])


if __name__ == "__main__":
    raise SystemExit(main())
