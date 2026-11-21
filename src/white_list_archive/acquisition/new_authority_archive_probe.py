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
    """Bound all *actual* worksheet rows/cells even if XLSX dimension tags are absent.

    A missing or misleading declared dimension is a review flag, not licence
    to skip the physical maximum. A declared dimension exceeding a limit still
    fails closed. No worksheet titles, cell values or private locators leave QA.
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
            declared_rows, declared_cols = ws.max_row, ws.max_column
            if ((declared_rows is not None and
                 (not isinstance(declared_rows, int) or declared_rows < 0 or declared_rows > MAX_ROWS))
                    or (declared_cols is not None and
                        (not isinstance(declared_cols, int) or declared_cols < 0 or declared_cols > MAX_COLUMNS))
                    or (declared_rows is not None and declared_cols is not None
                        and declared_rows * declared_cols > MAX_CELLS)):
                raise ValueError("Declared worksheet dimensions exceed safe limits")
            if ws.sheet_state not in ("visible", "hidden", "veryHidden"):
                raise ValueError("Unknown worksheet visibility")
            row_kinds = Counter()
            shapes = Counter()
            observed_rows = 0
            observed_columns = 0
            for row in ws.iter_rows(values_only=True):
                observed_rows += 1
                observed_columns = max(observed_columns, len(row))
                total_cells += len(row)
                if (observed_rows > MAX_ROWS or observed_columns > MAX_COLUMNS
                        or total_cells > MAX_CELLS):
                    raise ValueError("Observed worksheet dimensions exceed safe limits")
                present = 0
                for value in row:
                    kind = cell_shape(value)
                    shapes[kind] += 1
                    if kind != "blank":
                        present += 1
                row_kinds["empty" if present == 0 else "single_cell" if present == 1 else "multi_cell"] += 1
            if not observed_rows or not observed_columns:
                raise ValueError("Empty physical worksheet")
            if declared_rows is not None and observed_rows != declared_rows:
                raise ValueError("Declared worksheet row count mismatch")
            if declared_cols is not None and observed_columns > declared_cols:
                raise ValueError("Observed worksheet exceeds declared columns")
            sheets.append({
                "sheet_index": index,
                "visibility": ws.sheet_state,
                "physical_rows": observed_rows,
                "physical_columns": observed_columns,
                "declared_dimensions_present": declared_rows is not None and declared_cols is not None,
                "row_shapes": dict(row_kinds),
                "cell_shapes": dict(shapes),
            })
        if not any(s["row_shapes"].get("multi_cell", 0) for s in sheets):
            raise ValueError("No multi-cell rows for source census")
        return {"worksheets": sheets, "sheet_count": len(sheets),
                "physically_scanned_cells": total_cells}
    finally:
        workbook.close()


# Whitelist error text from this module only; never output library exception
# strings, potentially containing source cells or archive coordinates.
SAFE_STRUCTURE_ERROR_CODES = {
    "Not a bounded original XLSX": "invalid_or_oversized_xlsx",
    "Unexpected number of XLSX worksheets": "unexpected_sheet_count",
    "Declared worksheet dimensions exceed safe limits": "declared_dimensions_out_of_bounds",
    "Observed worksheet dimensions exceed safe limits": "physical_scan_bounds_exceeded",
    "Unknown worksheet visibility": "unexpected_visibility",
    "Empty physical worksheet": "empty_sheet",
    "Declared worksheet row count mismatch": "dimension_row_conflict",
    "Observed worksheet exceeds declared columns": "dimension_column_conflict",
    "No multi-cell rows for source census": "no_multi_cell_rows",
    "Original failed exact size or digest check": "remote_byte_identity_mismatch",
}


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
                entry["review_code"] = SAFE_STRUCTURE_ERROR_CODES.get(
                    str(exc), "unclassified_library_or_archive_failure")
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
