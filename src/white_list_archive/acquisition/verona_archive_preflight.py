"""Bounded redacted PDF preflight for the archived Verona listed/applicant pair.

A capture and physical-page audit is neither a SourceEdition nor publication.
Run only in the existing protected evidence-archive worker; never log source text.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
import re

import pdfplumber

from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for


# Frozen from robot-state@7ec6f97, captured by run 45080425727.
# Filename 19 November is a clue, not an authenticated reference date.
PINS = (
    ("listed", "d443032c6db23c38b0e81e0d4aacdb6bc10a2e54696f4acdf9d0f031cb89416b", 300988),
    ("applicant", "1124adc25205aaafa0e8e69c0ca536b136667b201064c8fc9f15fb388c7c260e", 167332),
)
ROBOT_REVISION = "7ec6f97"
MAX_PDF_BYTES = 2_000_000
MAX_PAGES = 250
MAX_TEXT_PER_PAGE = 250_000
MAX_TABLE_ROWS_PER_PAGE = 20_000
MAX_TABLE_CELLS_PER_PAGE = 200_000
_DATE = re.compile(r"(?<!\d)(?:19\s*[/.-]\s*11\s*[/.-]\s*2026|19\s+novembre\s+2026)(?!\d)", re.I)
_TITLE = {
    "listed": re.compile(r"\b(?:elenco|white\s*list)\b.{0,120}\b(?:iscritte|iscritti)\b", re.I),
    "applicant": re.compile(r"\b(?:elenco|white\s*list)\b.{0,120}\b(?:richiedenti|richieste|istanze)\b", re.I),
}



def row_shape_clues(row) -> dict[str, bool]:
    """Unapproved syntactic clues only; no record, identity or legal inference.

    Only whole-cell shapes count as possible identifiers. All observations are
    aggregate flags; no original string or locator is returned.
    """
    values = [str(cell or "").strip() for cell in row]
    if any(len(value) > 10_000 for value in values):
        raise ValueError("PDF table cell exceeds bounded review")
    eleven = any(re.fullmatch(r"[0-9]{11}", value) for value in values)
    sixteen = any(
        re.fullmatch(r"[A-Za-z0-9]{16}", value) and re.search(r"[A-Za-z]", value)
        for value in values
    )
    header_text = " ".join(value.casefold() for value in values)
    header_patterns = (
        r"\b(?:ragione\s+sociale|denominazione)\b",
        r"\b(?:codice\s+fiscale|partita\s+iva|p\s*\.?\s*iva)\b",
        r"\b(?:settore|sezione|categoria|attivit[aà])\b",
    )
    header_like = sum(bool(re.search(p, header_text)) for p in header_patterns) >= 2
    nonblank = sum(bool(value) for value in values)
    return {
        "eleven_digit_whole_cell_rows": bool(eleven),
        "sixteen_character_whole_cell_rows": bool(sixteen),
        "both_syntactic_shapes_rows": bool(eleven and sixteen),
        "header_like_rows": header_like,
        "unanchored_nonheader_nonblank_rows": bool(nonblank and not eleven and not sixteen and not header_like),
        "empty_table_rows": nonblank == 0,
        "single_nonblank_cell_rows": nonblank == 1,
    }


def page_profile(page, population: str) -> dict:
    """Only bounded page-level structure and aggregate source-layout clues."""
    if population not in _TITLE:
        raise ValueError("Unknown population")
    if not 0 < page.width <= 5000 or not 0 < page.height <= 5000:
        raise ValueError("Invalid PDF page geometry")
    content = page.extract_text() or ""
    if len(content) > MAX_TEXT_PER_PAGE:
        raise ValueError("PDF text exceeds bounded review")
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    header = page.crop((0, 0, page.width, page.height * .18)).extract_text() or ""
    if len(header) > MAX_TEXT_PER_PAGE:
        raise ValueError("PDF header exceeds bounded review")
    title_lines = [line for line in header.splitlines() if _TITLE[population].search(line)]
    # A same-line 19 November clue is not automatically an official edition date.
    title_date_cue = any(_DATE.search(line) for line in title_lines)
    table_rows = 0
    table_cells = 0
    table_widths = Counter()
    nonempty_multicell_rows = 0
    row_shapes = Counter()
    tables = page.find_tables()
    for table in tables:
        for row in table.extract():
            table_rows += 1
            table_cells += len(row)
            if table_rows > MAX_TABLE_ROWS_PER_PAGE or table_cells > MAX_TABLE_CELLS_PER_PAGE:
                raise ValueError("PDF tables exceed bounded review")
            present = sum(bool(str(cell or "").strip()) for cell in row)
            if present >= 2:
                nonempty_multicell_rows += 1
            table_widths[str(len(row))] += 1
            row_shapes.update(key for key, flag in row_shape_clues(row).items() if flag)
    return {
        "nonblank_text_lines": len(lines),
        "table_count": len(tables),
        "physical_table_rows": table_rows,
        "nonblank_multicell_table_rows": nonempty_multicell_rows,
        "table_widths": dict(sorted(table_widths.items())),
        "unapproved_row_shape_counts": dict(sorted(row_shapes.items())),
        "verona_authority_header_cue": bool(re.search(
            r"\bprefettura\s+(?:di\s+)?verona\b", header, re.I)),
        "population_title_header_cue": bool(title_lines),
        "filename_date_in_title_line_cue": bool(title_date_cue),
        "filename_date_anywhere_in_page_text_cue": bool(_DATE.search(content)),
    }


def census_pdf(raw: bytes, population: str) -> dict:
    if not isinstance(raw, bytes) or not raw.startswith(b"%PDF-") or len(raw) > MAX_PDF_BYTES:
        raise ValueError("Original is not a bounded PDF")
    pages = []
    with pdfplumber.open(BytesIO(raw)) as pdf:
        if not 1 <= len(pdf.pages) <= MAX_PAGES:
            raise ValueError("Unexpected PDF page count")
        for page in pdf.pages:
            pages.append(page_profile(page, population))
            page.close()
    totals = Counter()
    widths = Counter()
    row_shapes = Counter()
    for item in pages:
        for key in ("nonblank_text_lines", "table_count", "physical_table_rows",
                    "nonblank_multicell_table_rows"):
            totals[key] += item[key]
        for key in ("verona_authority_header_cue", "population_title_header_cue",
                    "filename_date_in_title_line_cue",
                    "filename_date_anywhere_in_page_text_cue"):
            totals[key + "_pages"] += int(item[key])
        widths.update(item["table_widths"])
        row_shapes.update(item["unapproved_row_shape_counts"])
    return {"pages": len(pages), "aggregate_counts": dict(totals),
            "unapproved_row_shape_counts": dict(sorted(row_shapes.items())),
            "physical_table_row_widths": dict(sorted(widths.items())),
            "tableless_pages": sum(not p["table_count"] for p in pages),
            "physical_census_only": True, "logical_record_census": False,
            "identifier_syntax_only_not_validated": True,
            "official_document_date_authenticated": False}


def audit_pair(store: EvidenceStore, *, pins=PINS, scanner=census_pdf) -> dict:
    if len(pins) != 2 or {x[0] for x in pins} != {"listed", "applicant"}:
        raise ValueError("Full listed/applicant original pair required")
    results = []
    for population, digest, size in pins:
        item = {"population": population, "original_sha256": digest,
                "expected_bytes": size, "source_bytes_verified": False}
        try:
            raw = store.read_digest_verified(digest)
            if len(raw) != size or sha256(raw).hexdigest() != digest:
                raise ValueError("Original size or digest mismatch")
            item["source_bytes_verified"] = True
            item["physical_pdf_profile"] = scanner(raw, population)
        except Exception as exc:
            # Never output provider exceptions, source text, raw PDF, URL, or locators.
            item["review_code"] = (
                "byte_identity_mismatch" if str(exc) == "Original size or digest mismatch"
                else "source_only_review_failed")
            item["error_type"] = type(exc).__name__
        results.append(item)
    return {
        "scope": "verona_2026_11_19_filename_pair_source_only",
        "robot_revision": ROBOT_REVISION, "review_only": True,
        "originals_expected": 2,
        "originals_sha_verified": sum(x["source_bytes_verified"] for x in results),
        "physical_profiles_completed": sum("physical_pdf_profile" in x for x in results),
        "official_edition_date_approved": False,
        "source_edition_approved": False,
        "parser_or_logical_record_count_approved": False,
        "privacy_approved": False,
        "public_release_eligible": False,
        "postgresql_writes": 0, "public_promotions": 0, "results": results,
    }


def main() -> int:
    try:
        config = StoreConfig.from_env()
        report = audit_pair(EvidenceStore(client_for(config), config))
    except Exception:
        report = {
            "scope": "verona_2026_11_19_filename_pair_source_only",
            "review_only": True, "originals_expected": 2,
            "originals_sha_verified": 0, "physical_profiles_completed": 0,
            "official_edition_date_approved": False,
            "source_edition_approved": False, "privacy_approved": False,
            "public_release_eligible": False,
            "postgresql_writes": 0, "public_promotions": 0,
            "review_code": "protected_source_read_unavailable",
        }
    print(json.dumps(report, sort_keys=True))
    return 0  # Source-only errors remain explicit within the receipt, never approvals.


if __name__ == "__main__":
    raise SystemExit(main())
