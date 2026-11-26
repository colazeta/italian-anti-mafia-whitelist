"""Read-only source review of the latest archived Lecce PDF pair.

No row-level output, source edition approval, or publication. September's
strict parser is not modified or used to approve a November edition.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
import re

import pdfplumber

from white_list_archive.parsers.lecce_tables import (
    _ADMIN_PREFIXES, _iso_if_valid, _status, _strict_identifiers,
)
from white_list_archive.parsers.multi_prefecture_tables import _clean
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for

ROBOT_REVISION = "d59c67677586b0b6cb373d69bcdcb1713fc0d1bd"
PINS = (
    ("listed", "a33d02c78e5ca35a4aaae3427845267be83eb2f0e0160434943d2673755d5b6f", 1645131),
    ("applicant", "956a646a31a16745b5c97f1db7d266a6c7d6d33511720122863ac418b2bb91b5", 284598),
)
MAX_BYTES = 5_000_000
MAX_PAGES = 150
MAX_ROWS = 20_000
MARKER = "19/11/2026"
APPLICANT_HEADER = [
    "RAGIONE SOCIALE", "SEDE LEGALE", "CODICE FISCALE",
    "DATA DI PRESENTAZIONE DELL'ISTANZA",
]
SECTION = re.compile(r"^SEZIONE\s+([IVX]+)\b", re.I)
SECTIONS = frozenset(("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"))


def profile_pages(pages, population):
    """Census every physical row; report only bounded, aggregate review clues."""
    if population not in {"listed", "applicant"}:
        raise ValueError("Unknown population")
    counts, widths, sections, statuses = Counter(), Counter(), Counter(), Counter()
    grouped = set()
    residual_shapes, unresolved_status_shapes, unresolved_date_shapes = Counter(), Counter(), Counter()

    def residual(cells, reason):
        counts["unclassified_rows"] += 1
        nonblank = sum(bool(v) for v in cells)
        residual_shapes[f"{reason}:width_{len(cells)}:nonblank_{nonblank}"] += 1
    section = None
    expected_width = 7 if population == "listed" else 4
    for page in pages:
        counts["pages"] += 1
        if counts["pages"] > MAX_PAGES:
            raise ValueError("Page limit exceeded")
        counts["filename_date_marker_pages"] += MARKER in (page.extract_text() or "")
        tables = page.find_tables()
        counts["tables"] += len(tables)
        counts["pages_not_one_table"] += len(tables) != 1
        for table in tables:
            for raw in table.extract():
                counts["physical_rows"] += 1
                if counts["physical_rows"] > MAX_ROWS:
                    raise ValueError("Row limit exceeded")
                cells = [_clean(v) for v in raw]
                widths[str(len(cells))] += 1
                if not any(cells):
                    counts["blank_rows"] += 1
                    continue
                if len(cells) != expected_width:
                    residual(cells, "unexpected_width")
                    continue
                first = cells[0]
                if population == "listed":
                    match = SECTION.match(first)
                    if first.startswith("SEZIONE"):
                        section = match.group(1).upper() if match else None
                        if section not in SECTIONS:
                            section = None
                            residual(cells, "unknown_section")
                        else:
                            counts["section_heading_rows"] += 1
                        continue
                    if any(first.startswith(prefix) for prefix in _ADMIN_PREFIXES):
                        counts["administrative_header_rows"] += 1
                        continue
                    if not first or section is None:
                        residual(cells, "missing_name_or_section")
                        continue
                    identifier, dates = cells[3], cells[4:6]
                    try:
                        status = _status(cells[6])
                    except RuntimeError:
                        status = "unreviewed"
                        note = cells[6].casefold()
                        for key, pattern in (("renewal", r"\brinnov\w*"),
                                             ("pending", r"\b(?:istruttoria|attesa|corso)\b"),
                                             ("expiry", r"\bscad\w*"),
                                             ("adverse", r"\b(?:revoc\w*|dinieg\w*|cancell\w*|interditt\w*)")):
                            if re.search(pattern, note):
                                unresolved_status_shapes[key] += 1
                        unresolved_status_shapes["unreviewed_total"] += 1
                    statuses[status] += 1
                    sections[section] += 1
                    grouped.add(tuple(cells))
                else:
                    if cells == APPLICANT_HEADER:
                        counts["administrative_header_rows"] += 1
                        continue
                    if not first or not cells[2]:
                        residual(cells, "missing_name_or_identifier")
                        continue
                    identifier, dates = cells[2], cells[3:4]
                counts["candidate_data_shaped_rows"] += 1
                counts["rows_with_identifier_syntax"] += bool(_strict_identifiers(identifier))
                counts["rows_with_blank_identifier_field"] += not identifier
                counts["rows_with_unparseable_nonblank_date"] += any(
                    value and not _iso_if_valid(value) for value in dates)
                counts["rows_with_blank_date"] += any(not value for value in dates)
                for value in dates:
                    if value and not _iso_if_valid(value):
                        kind = ("numeric_date_shape" if re.fullmatch(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}", value)
                                else "other_nonblank")
                        unresolved_date_shapes[kind] += 1
    if not counts["pages"] or not counts["physical_rows"]:
        raise ValueError("No physical census")
    categories = ("blank_rows", "unclassified_rows", "section_heading_rows",
                  "administrative_header_rows", "candidate_data_shaped_rows")
    if sum(counts[k] for k in categories) != counts["physical_rows"]:
        raise ValueError("Unreconciled physical census")
    return {
        "counts": {k: counts[k] for k in (
            "pages", "filename_date_marker_pages", "tables", "pages_not_one_table",
            "physical_rows", *categories, "rows_with_identifier_syntax",
            "rows_with_blank_identifier_field", "rows_with_unparseable_nonblank_date",
            "rows_with_blank_date")},
        "widths": dict(sorted(widths.items())),
        "candidate_sector_rows": dict(sorted(sections.items())),
        "listed_status_clues": dict(sorted(statuses.items())),
        "unclassified_row_shape_counts": dict(sorted(residual_shapes.items())),
        "unreviewed_status_shape_counts_not_status_mapping": dict(sorted(unresolved_status_shapes.items())),
        "unparseable_date_field_shapes": dict(sorted(unresolved_date_shapes.items())),
        "listed_exact_cell_tuple_groups_not_entities": len(grouped) if population == "listed" else None,
        "source_edition_approved": False,
        "privacy_approved": False,
        "logical_record_census_approved": False,
    }


def profile_pdf(raw, population):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES or not raw.startswith(b"%PDF-"):
        raise ValueError("Invalid bounded PDF")
    with pdfplumber.open(BytesIO(raw)) as pdf:
        return profile_pages(pdf.pages, population)


def audit_pair(store, *, pins=PINS, scanner=profile_pdf):
    if len(pins) != 2 or {p[0] for p in pins} != {"listed", "applicant"}:
        raise ValueError("Both population pins required")
    results = []
    for population, digest, size in pins:
        item = {"population": population, "original_sha256": digest,
                "expected_bytes": size, "source_bytes_verified": False}
        try:
            raw = store.read_digest_verified(digest)
            if len(raw) != size or sha256(raw).hexdigest() != digest:
                raise ValueError("Original identity mismatch")
            item["source_bytes_verified"] = True
            item["physical_profile"] = scanner(raw, population)
        except Exception as exc:
            # Exception text can contain source values; never log it.
            item["error_type"] = type(exc).__name__
            item["review_code"] = "source_review_incomplete"
        results.append(item)
    return {
        "scope": "lecce_2026_11_19_archived_pair_source_only",
        "robot_revision": ROBOT_REVISION,
        "originals_expected": 2,
        "originals_sha_verified": sum(x["source_bytes_verified"] for x in results),
        "physical_profiles_completed": sum("physical_profile" in x for x in results),
        "source_edition_approved": False, "privacy_approved": False,
        "official_edition_date_approved": False, "public_release_eligible": False,
        "postgresql_writes": 0, "public_promotions": 0,
        "results": results,
    }


def main():
    try:
        cfg = StoreConfig.from_env()
        report = audit_pair(EvidenceStore(client_for(cfg), cfg))
    except Exception:
        report = {"scope": "lecce_2026_11_19_archived_pair_source_only",
                  "review_code": "protected_source_read_unavailable",
                  "originals_expected": 2, "originals_sha_verified": 0,
                  "physical_profiles_completed": 0, "public_release_eligible": False,
                  "source_edition_approved": False, "privacy_approved": False,
                  "postgresql_writes": 0, "public_promotions": 0}
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
