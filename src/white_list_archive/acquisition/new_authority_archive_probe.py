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
import pdfplumber

from white_list_archive.acquisition.verona_archive_preflight import row_shape_clues

from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for


# Exact candidate metadata from 21 November (Novara) and 23 November
# robot-state@d59c67677586b0b6cb373d69bcdcb1713fc0d1bd (Rieti/Vicenza).
# Earlier exact pins and receipts remain in Git history and the immutable archive.
# The November filename, HTTP Last-Modified or discovery timestamp is NOT an
# approved document edition date. Alternative Novara PDFs are separate evidence.
PINS = {
    "novara": (
        ("listed", "27a4514dcb0ddb77786c64faf186b7b855d9f616389ec8c3d4bec504bea771a2", 37187),
        ("applicant", "ef0486870ddb136fdf2e876a563e1b3c91e814bfcaf27a1d3a9baf10dd76cdcf", 32038),
    ),
    "rieti": (
        ("listed", "9ca5fcf9be4e7447c197f3dd94ba5b7f4a8b7656853aca0a7f2837159a4892f7", 50306),
        ("applicant", "8eed8bfc3b094c3750a5410063e9142365945e1a56a939177849e07f51c55b03", 46364),
    ),
    "vicenza": (
        ("listed", "f1af1fe0a99c8fafcf05537721b39a80c2072a4ea524f2c61b4b9f5466c43f50", 68748),
        ("applicant", "624d3b2214b3afae309d1f12787dc4957093d96e7bf0ccf3ff5c952ceb7385f4", 14695),
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



# Finite vocabulary for header clues; exact whole-cell matches only.
# This is not a parser binding and never returns raw cell text.
_HEADER_ALIASES = {
    "name": {"denominazione", "ragione sociale", "denominazione impresa", "impresa",
             "denominazione/ragione sociale", "denominazione / ragione sociale",
             "denominazione ditta", "ragione sociale / denominazione"},
    "identifier": {"codice fiscale", "partita iva", "codice fiscale partita iva",
                   "codice fiscale / partita iva", "c.f.", "p.iva", "c.f./p.iva",
                   "c.f. / p. iva", "codice fiscale/partita iva", "partita iva/codice fiscale",
                   "codice fiscale e partita iva", "c.f. e p.iva", "p. iva"},
    "address": {"sede legale", "indirizzo", "sede"},
    "sector": {"sezione", "settore", "settori", "attività"},
    "application_date": {"data istanza", "data richiesta", "data presentazione istanza",
                         "data di presentazione dell'istanza"},
    "listing_date": {"data iscrizione", "data di iscrizione"},
    "expiry_date": {"data scadenza", "data scadenza iscrizione"},
    "status": {"stato", "esito", "note", "annotazioni"},
}


def header_clues(row):
    clues = set()
    for value in row:
        if isinstance(value, str):
            token = " ".join(value.casefold().split())
            for role, labels in _HEADER_ALIASES.items():
                if token in labels:
                    clues.add(role)
    return clues


def _header_role_columns(row):
    roles = {}
    for i, value in enumerate(row):
        for role in header_clues((value,)):
            roles.setdefault(role, []).append(i)
    return roles


# Preserve the broad legacy role vocabulary. These exact label subtypes
# are independent evidence only: generic address and combined identifiers
# are never assigned a narrower role by position or shape.
_HEADER_SUBTYPES = {
    "registered_office": {"sede legale"},
    "generic_address": {"indirizzo", "sede"},
    "tax_code": {"codice fiscale", "c.f."},
    "vat_number": {"partita iva", "p.iva", "p. iva"},
    "combined_identifier": _HEADER_ALIASES["identifier"] - {
        "codice fiscale", "c.f.", "partita iva", "p.iva", "p. iva"},
}


def header_subtype_columns(row):
    result = {}
    for col, value in enumerate(row):
        if isinstance(value, str):
            token = " ".join(value.casefold().split())
            for subtype, aliases in _HEADER_SUBTYPES.items():
                if token in aliases:
                    result.setdefault(subtype, []).append(col)
    return result


def aligned_header_columns(row):
    """Finite column-role clues, never an approved logical schema."""
    roles = _header_role_columns(row)
    keys = set(roles)
    # The exact Rieti partial role combination was observed in the protected
    # 25-Nov run. Name remains unbound when it has no recognised header.
    partial = {"address", "expiry_date", "identifier", "listing_date", "status"}
    if not (header_row_role(row) or keys == partial):
        return {}
    # Duplicate roles remain explicitly unbound. This diagnostic can count
    # uniquely aligned fields without resolving the repeated header labels.
    return {role: columns[0] for role, columns in roles.items()
            if len(columns) == 1}


def header_row_role(row):
    clues = header_clues(row)
    # A single coincidental word never creates a header.
    return len(clues) >= 3 and "name" in clues and "identifier" in clues


def cached_shape(value):
    if isinstance(value, bool):
        return "other_nonblank"
    if isinstance(value, (int, float)) and 10**10 <= value < 10**11 and value == int(value):
        return "eleven_digit_numeric_shape"
    return cell_shape(value)


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
            header_roles = Counter()
            partial_header_combinations = Counter()
            unresolved_multicell_shapes = Counter()
            candidate_row_roles = Counter()
            cached_formula_shapes = Counter()
            header_seen = False
            alignment = {}
            aligned_rows = Counter()
            aligned_field_shapes = Counter()
            ambiguous_header_roles = Counter()
            ambiguous_header_rows = 0
            subtype_alignment = {}
            subtype_column_counts = Counter()
            repeated_subtype_counts = Counter()
            subtype_field_shapes = Counter()
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
                        cached_formula_shapes[cached_shape(cached_value)] += 1
                        row_has_cached_formula |= has_cache
                        row_has_uncached_formula |= not has_cache
                    if kind != "blank":
                        present += 1
                row_kinds["empty" if present == 0 else "single_cell" if present == 1 else "multi_cell"] += 1
                # Separate diagnostic partition; do not change the existing
                # recognised-header or row-role census. Never emit column
                # locators, formula text, cached values or field contents.
                new_alignment = aligned_header_columns(row)
                roles = _header_role_columns(row)
                strong_partial = {"address", "expiry_date", "identifier", "listing_date", "status"}
                candidate_anchor = header_row_role(row) or set(roles) == strong_partial
                if candidate_anchor:
                    alignment = new_alignment
                    subtypes = header_subtype_columns(row)
                    subtype_column_counts.update({k: len(v) for k, v in subtypes.items()})
                    repeated_subtype_counts.update({k: len(v) for k, v in subtypes.items() if len(v) > 1})
                    subtype_alignment = {k: v[0] for k, v in subtypes.items() if len(v) == 1}
                    repeated = {role: len(cols) for role, cols in roles.items() if len(cols) > 1}
                    if repeated:
                        ambiguous_header_rows += 1
                        ambiguous_header_roles.update(repeated)
                    aligned_rows["header_anchor"] += 1
                elif not present:
                    aligned_rows["empty"] += 1
                elif not alignment:
                    aligned_rows["before_anchor"] += 1
                else:
                    aligned_rows["after_anchor"] += 1
                    for role, col in alignment.items():
                        if col >= len(row):
                            aligned_field_shapes[role + ":missing_column"] += 1
                            continue
                        value = cached_row[col] if cell_shape(row[col]) == "formula" else row[col]
                        aligned_field_shapes[role + ":" + cached_shape(value)] += 1
                    for subtype, col in subtype_alignment.items():
                        if col >= len(row):
                            subtype_field_shapes[subtype + ":missing_column"] += 1
                            continue
                        value = cached_row[col] if cell_shape(row[col]) == "formula" else row[col]
                        subtype_field_shapes[subtype + ":" + cached_shape(value)] += 1
                clues = header_clues(row)
                if clues and not header_row_role(row):
                    # Finite vocabulary only: no raw heading, value or row locator.
                    partial_header_combinations["+".join(sorted(clues))] += 1
                if present == 0:
                    candidate_row_roles["empty"] += 1
                elif header_row_role(row):
                    header_seen = True
                    candidate_row_roles["header_clue"] += 1
                    header_roles.update(header_clues(row))
                elif not header_seen:
                    candidate_row_roles["before_recognised_header"] += 1
                    if present >= 2:
                        effective = [cached if cell_shape(v) == "formula" else v
                                     for v, cached in zip(row, cached_row)]
                        unresolved_multicell_shapes["before_header_with_identifier_clue" if any(
                            cached_shape(v) in {"eleven_digit_shape", "eleven_digit_numeric_shape",
                                                "sixteen_character_shape_privacy_review"}
                            for v in effective) else "before_header_without_identifier_clue"] += 1
                elif present < 2:
                    candidate_row_roles["post_header_single_cell"] += 1
                else:
                    effective = [cached if cell_shape(v) == "formula" else v
                                 for v, cached in zip(row, cached_row)]
                    identifier_clue = any(cached_shape(v) in {
                        "eleven_digit_shape", "eleven_digit_numeric_shape",
                        "sixteen_character_shape_privacy_review"} for v in effective)
                    candidate_row_roles[
                        "post_header_multicell_with_identifier_clue" if identifier_clue
                        else "post_header_multicell_without_identifier_clue"] += 1
                    if not identifier_clue:
                        unresolved_multicell_shapes["after_header_without_identifier_clue"] += 1
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
            if sum(aligned_rows.values()) != observed_rows:
                raise ValueError("Unreconciled aligned header diagnostic")
            if sum(candidate_row_roles.values()) != observed_rows:
                raise ValueError("Unreconciled row-role clues")
            sheets.append({
                "sheet_index": index,
                "visibility": ws.sheet_state,
                "physical_rows": observed_rows,
                "physical_columns": observed_columns,
                "declared_dimensions_present": declared_rows is not None and declared_cols is not None,
                "row_shapes": dict(row_kinds),
                "row_signals": dict(row_signals),
                "row_role_clues_not_record_census": dict(candidate_row_roles),
                "recognised_header_role_counts": dict(header_roles),
                "aligned_rows_not_record_census": dict(aligned_rows),
                "aligned_field_shapes_not_values": dict(aligned_field_shapes),
                "ambiguous_header_rows": ambiguous_header_rows,
                "header_subtype_column_clues": dict(subtype_column_counts),
                "repeated_header_subtype_columns_unbound": dict(repeated_subtype_counts),
                "header_subtype_field_shapes_not_values": dict(subtype_field_shapes),
                "ambiguous_header_role_column_occurrences": dict(ambiguous_header_roles),
                "partial_header_role_combinations": dict(partial_header_combinations),
                "unresolved_multicell_shape_counts": dict(unresolved_multicell_shapes),
                "cached_formula_value_shapes": dict(cached_formula_shapes),
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
                # Attempt only on exact R2 originals with a structural geometry
                # rejection. Empty auxiliary sheets are a possibility, not a
                # conclusion: diagnose all XML parts without accepting any.
                if (entry.get("original_bytes_readback_verified") is True and
                        entry["review_code"] in {"declared_dimensions_out_of_bounds", "empty_sheet"}):
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


# Separate exact PDF alternatives; preserve the old workbook audit and bounds.
NOVARA_PDF_PINS = (
    ("listed", "68bf14d684b39e04a434b56fbab239ad43de7a25f1ebc3113d04be4838c1d315", 1071220),
    ("applicant", "48a287404d1a4cd9824c5b7b2d4f9f9f460719df39d9e0339db2f6b203a8f4c7", 875632),
)
NOVARA_PDF_ROBOT_REVISION = "29c42da64d4d4f97725da4c2509ed8fafd08b981"
_PDF_EDITION_CUE = re.compile(
    r"\b(?:aggiornat[oaie]|aggiornamento|situazione)\s+(?:al|del|alla data del)\s+"
    r"(\d{1,2}[/.-]\d{1,2}[/.-]20\d{2})\b", re.I)
_PDF_POPULATION_CUES = {
    "listed": re.compile(r"\b(?:imprese|ditte|elenco)\b.{0,100}\biscritt[ei]\b", re.I),
    "applicant": re.compile(r"\b(?:richiest[ae]|richiedenti|istanze)\b", re.I),
}


def novara_pdf_pages(pages, population, *, authority="novara"):
    """Independent physical PDF census; date labels only, never record values."""
    if population not in _PDF_POPULATION_CUES:
        raise ValueError("Unknown population")
    if authority not in {"novara", "nuoro"}:
        raise ValueError("Unknown reviewed authority")
    counts, widths, shapes, dates = Counter(), Counter(), Counter(), Counter()
    anchor_counts, aligned_shapes, residual_alignment = Counter(), Counter(), Counter()
    for page in pages:
        counts["pages"] += 1
        if counts["pages"] > 250 or not (0 < page.width <= 5000 and 0 < page.height <= 5000):
            raise ValueError("PDF page bounds")
        header = page.crop((0, 0, page.width, page.height * .18)).extract_text() or ""
        if len(header) > 250000:
            raise ValueError("PDF header bounds")
        counts["authority_header_cue_pages"] += bool(re.search(r"\bprefettura\s+(?:di\s+)?" + re.escape(authority) + r"\b", header, re.I))
        counts["population_header_cue_pages"] += bool(_PDF_POPULATION_CUES[population].search(header))
        page_dates = set()
        for match in _PDF_EDITION_CUE.finditer(header):
            try:
                day, month, year = map(int, re.split(r"[/.-]", match.group(1)))
                page_dates.add(date(year, month, day).isoformat())
            except ValueError:
                counts["invalid_labelled_date_clues"] += 1
        dates.update(page_dates)
        tables = page.find_tables()
        counts["tables"] += len(tables)
        counts["tableless_pages"] += not tables
        for table in tables:
            # Never inherit a guessed layout across table boundaries.
            alignment = {}
            for row in table.extract():
                counts["physical_rows"] += 1
                counts["physical_cells"] += len(row)
                if counts["physical_rows"] > 20000 or counts["physical_cells"] > 200000:
                    raise ValueError("PDF census bounds")
                widths[str(len(row))] += 1
                flags = row_shape_clues(row)
                shapes.update(key for key, flag in flags.items() if flag)
                if flags["header_like_rows"] or header_row_role(row):
                    alignment = aligned_header_columns(row) if header_row_role(row) else {}
                    anchor_counts["header_rows"] += 1
                    if {"name", "identifier"} <= alignment.keys():
                        anchor_counts["name_identifier_bound_headers"] += 1
                    else:
                        anchor_counts["unbound_headers"] += 1
                elif not flags["empty_table_rows"]:
                    if not {"name", "identifier"} <= alignment.keys() or max(alignment.values()) >= len(row):
                        residual_alignment["no_complete_table_local_anchor"] += 1
                    else:
                        residual_alignment["aligned_nonheader_rows"] += 1
                        for role, column in alignment.items():
                            aligned_shapes[f"{role}:{cell_shape(row[column])}"] += 1
                        name_present = cell_shape(row[alignment["name"]]) != "blank"
                        identifier_shape = cell_shape(row[alignment["identifier"]])
                        if name_present and identifier_shape in {"eleven_digit_shape", "sixteen_character_shape_privacy_review"}:
                            residual_alignment["name_and_identifier_shape"] += 1
                        elif name_present:
                            residual_alignment["name_without_standard_identifier_shape"] += 1
                        else:
                            residual_alignment["missing_name_in_aligned_row"] += 1
                # Mutually exclusive physical categories; never imply logical records.
                if flags["empty_table_rows"]:
                    counts["blank_rows"] += 1
                elif flags["header_like_rows"]:
                    counts["header_shape_rows"] += 1
                elif flags["single_nonblank_cell_rows"]:
                    counts["single_cell_rows"] += 1
                elif flags["eleven_digit_whole_cell_rows"] or flags["sixteen_character_whole_cell_rows"]:
                    counts["multicell_identifier_shape_rows"] += 1
                else:
                    counts["unresolved_multicell_rows"] += 1
    if not counts["pages"] or not counts["physical_rows"]:
        raise ValueError("No physical census")
    buckets = ("blank_rows", "header_shape_rows", "single_cell_rows",
               "multicell_identifier_shape_rows", "unresolved_multicell_rows")
    if sum(counts[k] for k in buckets) != counts["physical_rows"]:
        raise ValueError("Unreconciled census")
    return {"counts": dict(counts), "widths": dict(widths),
            "row_shape_clues": dict(shapes), "labelled_header_date_clues": dict(dates),
            "table_local_header_alignment_counts": dict(anchor_counts),
            "aligned_field_shapes_not_values": dict(aligned_shapes),
            "aligned_row_review_counts_not_logical_census": dict(residual_alignment),
            "logical_record_census_approved": False, "official_edition_date_approved": False}


def novara_pdf_profile(raw, population, *, authority="novara"):
    if not isinstance(raw, bytes) or not raw.startswith(b"%PDF-") or len(raw) > 2000000:
        raise ValueError("Invalid bounded PDF")
    with pdfplumber.open(BytesIO(raw)) as pdf:
        return novara_pdf_pages(pdf.pages, population, authority=authority)


def audit_novara_pdfs(store, *, pins=NOVARA_PDF_PINS, scanner=novara_pdf_profile):
    if len(pins) != 2 or {p[0] for p in pins} != {"listed", "applicant"}:
        raise ValueError("Exact pair required")
    results = []
    for population, digest, size in pins:
        entry = {"population": population, "original_sha256": digest,
                 "expected_bytes": size, "source_bytes_verified": False}
        try:
            raw = store.read_digest_verified(digest)
            if len(raw) != size or sha256(raw).hexdigest() != digest:
                raise ValueError("Original identity mismatch")
            entry["source_bytes_verified"] = True
            entry["physical_pdf_profile"] = scanner(raw, population)
        except Exception as exc:
            entry["error_type"] = type(exc).__name__
            entry["review_code"] = "source_only_review_incomplete"
        results.append(entry)
    return {"scope": "novara_pdf_alternatives_source_only", "robot_revision": NOVARA_PDF_ROBOT_REVISION,
            "originals_expected": 2, "originals_sha_verified": sum(x["source_bytes_verified"] for x in results),
            "physical_profiles_completed": sum("physical_pdf_profile" in x for x in results),
            "source_edition_approved": False, "official_edition_date_approved": False,
            "privacy_approved": False, "public_release_eligible": False,
            "postgresql_writes": 0, "public_promotions": 0, "results": results}


# Frozen robot-state e8898f4db6d266436fff08b64072e354cdce0990.
# Filename dates are clues, never authenticated edition dates.
NUORO_LISTED_PIN = ("listed", "0b0182d31ace7b7c8ad20268d5eb0efe3f77281994816b7a8b3a7dd87d3327fa", 319097)
BRESCIA_CURRENT_PINS = {
    "brescia": (
        ("listed", "5dd616b3ed60daa03ab74690992fe7f26a2256b8dc3ec91c9a8205d638c0fc61", 295547),
        ("applicant", "cca55fc9573e242691feeb6b111814d6fad3e2af1546ef50f0ee767e6af9e259", 111605),
    ),
}


def audit_nuoro_listed(store, *, pin=NUORO_LISTED_PIN):
    """Single-population preflight only: no fabricated applicant completeness."""
    population, digest, size = pin
    if population != "listed":
        raise ValueError("Only the exact listed discovery scope is available")
    entry = {"population": population, "original_sha256": digest,
             "expected_bytes": size, "source_bytes_verified": False}
    try:
        raw = store.read_digest_verified(digest)
        if len(raw) != size or sha256(raw).hexdigest() != digest:
            raise ValueError("Original identity mismatch")
        entry["source_bytes_verified"] = True
        entry["physical_pdf_profile"] = novara_pdf_profile(raw, population, authority="nuoro")
    except Exception as exc:
        entry["error_type"] = type(exc).__name__
        entry["review_code"] = "source_only_review_incomplete"
    return {"scope": "nuoro_listed_source_only",
            "robot_revision": "e8898f4db6d266436fff08b64072e354cdce0990",
            "review_only": True, "originals_expected": 1,
            "originals_sha_verified": int(entry["source_bytes_verified"]),
            "physical_profiles_completed": int("physical_pdf_profile" in entry),
            "applicant_population": "UNRESOLVED_REQUIRES_REVIEW",
            "population_complete": False, "source_edition_approved": False,
            "official_edition_date_approved": False, "privacy_approved": False,
            "public_release_eligible": False, "postgresql_writes": 0,
            "public_promotions": 0, "results": [entry]}


def audit_current_brescia(store):
    report = audit(store, BRESCIA_CURRENT_PINS)
    return {**report, "scope": "brescia_current_delta_source_only",
            "robot_revision": "e8898f4db6d266436fff08b64072e354cdce0990",
            "official_edition_date_approved": False, "postgresql_writes": 0,
            "public_promotions": 0}


# Additional exact pair, not a replacement of previously frozen review inputs.
NOVARA_CURRENT_WORKBOOK_PINS = {
    "novara": (
        ("listed", "6749d8c1b9e5f9ec5bcd6c15a7bbc7b84d17cc6502ff135e4447a37c88eee5b2", 37006),
        ("applicant", "f1f0976ae3c10226cd4973eb7786e48070c1d63c6eb8a6483b42106434f5689d", 32214),
    ),
}


def audit_current_novara_workbooks(store):
    report = audit(store, NOVARA_CURRENT_WORKBOOK_PINS)
    return {**report, "scope": "novara_current_workbook_source_only",
            "robot_revision": "fc1de2663233ae3f6e119768fa1454c4ce43aa6b",
            "official_edition_date_approved": False, "postgresql_writes": 0,
            "public_promotions": 0}


def main() -> int:
    config = StoreConfig.from_env()
    store = EvidenceStore(client_for(config), config)
    result = audit(store)
    print(json.dumps(result, sort_keys=True))
    pdf_result = audit_novara_pdfs(store)
    print(json.dumps(pdf_result, sort_keys=True))
    nuoro = audit_nuoro_listed(store)
    print(json.dumps(nuoro, sort_keys=True))
    brescia = audit_current_brescia(store)
    print(json.dumps(brescia, sort_keys=True))
    novara_current = audit_current_novara_workbooks(store)
    print(json.dumps(novara_current, sort_keys=True))
    return int(result["originals_verified"] != result["originals_expected"] or
               pdf_result["physical_profiles_completed"] != pdf_result["originals_expected"] or
               nuoro["physical_profiles_completed"] != nuoro["originals_expected"] or
               brescia["originals_verified"] != brescia["originals_expected"] or
               novara_current["originals_verified"] != novara_current["originals_expected"])


if __name__ == "__main__":
    raise SystemExit(main())
