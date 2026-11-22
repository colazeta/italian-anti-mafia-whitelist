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
from xml.parsers import expat
from zipfile import ZipFile

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
    cached_workbook = None
    try:
        # Excel's data_only view reads stored cached outcomes; it does not
        # evaluate formulae. Never log either formula text or cached values.
        cached_workbook = load_workbook(BytesIO(raw), read_only=True, data_only=True)
        if len(cached_workbook.worksheets) != len(workbook.worksheets):
            raise ValueError("Formula/cache worksheet geometry mismatch")
        if not 1 <= len(workbook.worksheets) <= MAX_SHEETS:
            raise ValueError("Unexpected number of XLSX worksheets")
        sheets = []
        total_cells = 0
        for index, (ws, cached_ws) in enumerate(
                zip(workbook.worksheets, cached_workbook.worksheets), 1):
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
            row_signals = Counter()
            formula_cache_counts = Counter({
                "formula_cells": 0,
                "formula_cells_with_cache": 0,
                "formula_cells_without_cache": 0,
                "rows_with_cached_formula": 0,
                "rows_with_uncached_formula": 0,
            })
            cached_rows = iter(cached_ws.iter_rows(values_only=True))
            observed_rows = 0
            observed_columns = 0
            for row in ws.iter_rows(values_only=True):
                cached_row = next(cached_rows, None)
                if cached_row is None or len(cached_row) != len(row):
                    raise ValueError("Formula/cache worksheet geometry mismatch")
                observed_rows += 1
                observed_columns = max(observed_columns, len(row))
                total_cells += len(row)
                if (observed_rows > MAX_ROWS or observed_columns > MAX_COLUMNS
                        or total_cells > MAX_CELLS):
                    raise ValueError("Observed worksheet dimensions exceed safe limits")
                present = 0
                row_shape_counts = Counter()
                row_has_cached_formula = False
                row_has_uncached_formula = False
                for value, cached_value in zip(row, cached_row):
                    kind = cell_shape(value)
                    shapes[kind] += 1
                    row_shape_counts[kind] += 1
                    if kind == "formula":
                        formula_cache_counts["formula_cells"] += 1
                        # A value's mere presence is not evidence that Excel
                        # recalculated it, nor that it is semantically correct.
                        has_cache = (cached_value is not None and
                                     (not isinstance(cached_value, str) or
                                      bool(cached_value.strip())))
                        formula_cache_counts[
                            "formula_cells_with_cache" if has_cache
                            else "formula_cells_without_cache"] += 1
                        row_has_cached_formula |= has_cache
                        row_has_uncached_formula |= not has_cache
                    if kind != "blank":
                        present += 1
                row_kinds["empty" if present == 0 else "single_cell" if present == 1 else "multi_cell"] += 1
                formula_cache_counts["rows_with_cached_formula"] += int(row_has_cached_formula)
                formula_cache_counts["rows_with_uncached_formula"] += int(row_has_uncached_formula)
                if present >= 2:
                    # Shape-only evidence for future physical-to-logical review.
                    # These text patterns are NOT confirmed company identifiers
                    # or record boundaries; Excel numeric/formula cells differ.
                    has_11 = row_shape_counts["eleven_digit_shape"] > 0
                    has_16 = row_shape_counts["sixteen_character_shape_privacy_review"] > 0
                    row_signals["multi_cell_with_11_digit_text"] += int(has_11)
                    row_signals["multi_cell_with_16_char_text"] += int(has_16)
                    row_signals["multi_cell_with_both_text_shapes"] += int(has_11 and has_16)
                    row_signals["multi_cell_with_neither_text_shape"] += int(not (has_11 or has_16))
                    row_signals["multi_cell_with_formula"] += int(row_shape_counts["formula"] > 0)
            if next(cached_rows, None) is not None:
                raise ValueError("Formula/cache worksheet geometry mismatch")
            if (formula_cache_counts["formula_cells_with_cache"] +
                    formula_cache_counts["formula_cells_without_cache"] !=
                    formula_cache_counts["formula_cells"]):
                raise ValueError("Formula/cache worksheet geometry mismatch")
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
                "row_signals": dict(row_signals),
                "formula_cache_counts": dict(formula_cache_counts),
                "cell_shapes": dict(shapes),
            })
        if not any(s["row_shapes"].get("multi_cell", 0) for s in sheets):
            raise ValueError("No multi-cell rows for source census")
        return {"worksheets": sheets, "sheet_count": len(sheets),
                "physically_scanned_cells": total_cells}
    finally:
        workbook.close()
        if cached_workbook is not None:
            cached_workbook.close()



# Diagnostic-only limits, independent of the release parser's stricter
# physical worksheet acceptance bounds. Never use these to approve a source.
MAX_COORDINATE_XML_BYTES = 24_000_000
MAX_TOTAL_COORDINATE_XML_BYTES = 48_000_000
MAX_COORDINATE_CELL_ELEMENTS = 600_000
MAX_COORDINATE_ROW_ELEMENTS = 150_000
_CELL_REFERENCE = re.compile(r"([A-Z]{1,3})([1-9][0-9]{0,6})\Z")


def _coordinate_numbers(value: str) -> tuple[int, int]:
    """Decode a cell reference, without returning or logging the locator."""
    match = _CELL_REFERENCE.fullmatch(value)
    if match is None:
        raise ValueError("Invalid worksheet coordinate metadata")
    column = 0
    for letter in match.group(1):
        column = column * 26 + ord(letter) - ord("A") + 1
    row = int(match.group(2))
    if not 1 <= column <= 16384 or not 1 <= row <= 1048576:
        raise ValueError("Invalid worksheet coordinate metadata")
    return row, column


def workbook_coordinate_diagnostic(raw: bytes) -> dict:
    """Inspect only bounded XLSX worksheet XML *geometry*, not its values.

    This is for reviewing unexpectedly large declared XLSX dimensions: XML
    encoded cell/row tags are not business records, and sparse formatting can
    make worksheet declared dimensions larger than actual semantic content.
    No source cell strings, individual coordinates, sheet names or XML paths
    are included in output. No published/source approval can result.
    """
    if not isinstance(raw, bytes) or not raw.startswith(b"PK") or len(raw) > MAX_BYTES:
        raise ValueError("Not a bounded original XLSX")
    parts = []
    total_xml_bytes = 0
    with ZipFile(BytesIO(raw)) as archive:
        sheet_members = [item for item in archive.infolist()
                         if re.fullmatch(r"xl/worksheets/sheet[0-9]+\.xml", item.filename)]
        if not 1 <= len(sheet_members) <= MAX_SHEETS:
            raise ValueError("Unexpected worksheet XML part count")
        for item in sheet_members:
            total_xml_bytes += item.file_size
            if (item.file_size > MAX_COORDINATE_XML_BYTES or
                    total_xml_bytes > MAX_TOTAL_COORDINATE_XML_BYTES):
                raise ValueError("Worksheet XML exceeds diagnostic limits")
            counters = {"encoded_row_elements": 0, "encoded_cell_elements": 0,
                        "cells_without_coordinates": 0, "rows_without_coordinates": 0,
                        "greatest_encoded_row": 0, "greatest_encoded_column": 0,
                        "declared_rows": None, "declared_columns": None,
                        "out_of_policy_explicit_row_elements": 0,
                        "out_of_policy_cell_elements": 0,
                        "out_of_policy_cell_with_payload_marker": 0,
                        "out_of_policy_cell_without_payload_marker": 0,
                        "out_of_policy_formula_cell_elements": 0,
                        "unlocated_cell_with_payload_marker": 0,
                        "greatest_payload_marker_row": 0,
                        "greatest_payload_marker_column": 0}
            parser = expat.ParserCreate(namespace_separator="}")
            # Presence of an XLSX value/formula/inline-string XML element is
            # only a *potential* data marker, not an interpreted cell value.
            # Keep no cell strings, references or individual locations.
            current_cell = None

            def prohibit_doctype(*_args):
                raise ValueError("Prohibited worksheet XML doctype")

            def start_element(name, attributes):
                nonlocal current_cell
                tag = name.rsplit("}", 1)[-1]
                if tag == "dimension":
                    reference = attributes.get("ref", "")
                    if len(reference) > 30:
                        raise ValueError("Invalid worksheet coordinate metadata")
                    declared_row, declared_column = _coordinate_numbers(
                        reference.split(":")[-1])
                    counters["declared_rows"] = declared_row
                    counters["declared_columns"] = declared_column
                elif tag == "row":
                    counters["encoded_row_elements"] += 1
                    if counters["encoded_row_elements"] > MAX_COORDINATE_ROW_ELEMENTS:
                        raise ValueError("Worksheet XML exceeds diagnostic limits")
                    explicit_row = attributes.get("r")
                    if explicit_row is None:
                        counters["rows_without_coordinates"] += 1
                    else:
                        if not re.fullmatch(r"[1-9][0-9]{0,6}", explicit_row):
                            raise ValueError("Invalid worksheet coordinate metadata")
                        row_number = int(explicit_row)
                        if row_number > 1048576:
                            raise ValueError("Invalid worksheet coordinate metadata")
                        counters["greatest_encoded_row"] = max(
                            counters["greatest_encoded_row"], row_number)
                        if row_number > MAX_ROWS:
                            counters["out_of_policy_explicit_row_elements"] += 1
                elif tag == "c":
                    if current_cell is not None:
                        raise ValueError("Invalid worksheet coordinate metadata")
                    counters["encoded_cell_elements"] += 1
                    if counters["encoded_cell_elements"] > MAX_COORDINATE_CELL_ELEMENTS:
                        raise ValueError("Worksheet XML exceeds diagnostic limits")
                    reference = attributes.get("r")
                    coordinates = None
                    if reference is None:
                        counters["cells_without_coordinates"] += 1
                    else:
                        row, column = _coordinate_numbers(reference)
                        coordinates = (row, column)
                        counters["greatest_encoded_row"] = max(
                            counters["greatest_encoded_row"], row)
                        counters["greatest_encoded_column"] = max(
                            counters["greatest_encoded_column"], column)
                    current_cell = {"coordinates": coordinates,
                                    "potential_payload_marker": False,
                                    "formula_marker": False}
                elif current_cell is not None and tag in ("v", "f", "is"):
                    # Never inspect, retain or print element text or values.
                    current_cell["potential_payload_marker"] = True
                    if tag == "f":
                        current_cell["formula_marker"] = True

            def end_element(name):
                nonlocal current_cell
                if name.rsplit("}", 1)[-1] != "c":
                    return
                if current_cell is None:
                    raise ValueError("Invalid worksheet coordinate metadata")
                coordinates = current_cell["coordinates"]
                marked = current_cell["potential_payload_marker"]
                if coordinates is None:
                    if marked:
                        counters["unlocated_cell_with_payload_marker"] += 1
                else:
                    row, column = coordinates
                    if marked:
                        counters["greatest_payload_marker_row"] = max(
                            counters["greatest_payload_marker_row"], row)
                        counters["greatest_payload_marker_column"] = max(
                            counters["greatest_payload_marker_column"], column)
                    if row > MAX_ROWS or column > MAX_COLUMNS:
                        counters["out_of_policy_cell_elements"] += 1
                        counters["out_of_policy_cell_with_payload_marker" if marked
                                 else "out_of_policy_cell_without_payload_marker"] += 1
                        if current_cell["formula_marker"]:
                            counters["out_of_policy_formula_cell_elements"] += 1
                current_cell = None

            parser.StartElementHandler = start_element
            parser.EndElementHandler = end_element
            parser.StartDoctypeDeclHandler = prohibit_doctype
            consumed = 0
            with archive.open(item, "r") as stream:
                while True:
                    chunk = stream.read(65536)
                    if not chunk:
                        break
                    consumed += len(chunk)
                    if consumed > MAX_COORDINATE_XML_BYTES:
                        raise ValueError("Worksheet XML exceeds diagnostic limits")
                    parser.Parse(chunk, False)
                parser.Parse(b"", True)
            parts.append({"xml_part_index": len(parts) + 1, **counters})
    return {"diagnostic_only": True, "record_census": False,
            "source_edition_approved": False, "privacy_approved": False,
            "xml_parts": parts}


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
    "Formula/cache worksheet geometry mismatch": "formula_cache_geometry_mismatch",
    "Original failed exact size or digest check": "remote_byte_identity_mismatch",
    "Unexpected worksheet XML part count": "unexpected_worksheet_xml_parts",
    "Worksheet XML exceeds diagnostic limits": "diagnostic_xml_bounds_exceeded",
    "Invalid worksheet coordinate metadata": "invalid_coordinate_metadata",
    "Prohibited worksheet XML doctype": "prohibited_xml_doctype",
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
                # Diagnostic is read-only and cannot override rejected structure.
                # Attempt only on exact R2 originals with oversized dimensions.
                if (entry.get("original_bytes_readback_verified") is True and
                        entry["review_code"] == "declared_dimensions_out_of_bounds"):
                    try:
                        entry["redacted_coordinate_diagnostic"] = (
                            workbook_coordinate_diagnostic(raw))
                    except Exception as diagnostic_exc:
                        entry["coordinate_diagnostic_code"] = SAFE_STRUCTURE_ERROR_CODES.get(
                            str(diagnostic_exc), "unclassified_diagnostic_failure")
            results.append(entry)
    return {"review_only": True, "source_edition_approved": False,
            "listed_applicant_semantics_approved": False,
            "privacy_approved": False, "public_release_eligible": False,
            "source_bytes_verified": sum(r.get("original_bytes_readback_verified") is True for r in results),
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
