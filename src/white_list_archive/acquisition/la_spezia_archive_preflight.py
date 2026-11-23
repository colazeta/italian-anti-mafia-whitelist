"""Read-only, bounded structural QA of archived La Spezia White List HTML.

This source-only diagnostic never approves editions, legal statuses, identities,
dates or public data. Original text and row values never appear in the receipt.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from html.parser import HTMLParser
import json
import re

from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for

# Archived official population pages in robot-state@7ec6f97. These are
# HTML response originals, NOT dated or approved SourceEditions.
PINS = (
    ("listed", "4b668d585797c537c1d4f7dc27e7f8733dbe568914668829d88f5ad09e02f7c9", 147017),
    ("applicant", "50cc45c03517013084d626a1415ca5bd003579c1594ebc65273cad37cb690f8d", 83851),
)
ROBOT_REVISION = "7ec6f97"
MAX_HTML_BYTES = 500_000
MAX_TABLE_ROWS = 20_000
MAX_COLUMNS = 60
MAX_CELL_CHARS = 20_000
_HEADER_CUES = {
    "name": re.compile(r"ragione\s+sociale|denominazione", re.I),
    "identifier": re.compile(r"partita\s+i\.?v\.?a\.?|codice\s+fiscale", re.I),
    "sector": re.compile(r"attivit[aà]|settore|sezione", re.I),
    "date": re.compile(r"data\s+(?:iscrizione|presentazione|scadenza)", re.I),
    "outcome": re.compile(r"\besito\b", re.I),
}
_TITLE_CUE = {
    "listed": re.compile(r"ditte\s+iscritte|imprese\s+iscritte", re.I),
    "applicant": re.compile(r"richiest[oa]\s+iscrizione|hanno\s+richiesto\s+iscrizione", re.I),
}


class _Structure(HTMLParser):
    """Retain only row/heading text until it has been reduced to safe counts."""

    def __init__(self, population: str):
        super().__init__(convert_charrefs=True)
        if population not in _TITLE_CUE:
            raise ValueError("Unrecognised population")
        self.population = population
        self.table_depth = 0
        self.row_open = False
        self.cell_tag = None
        self.cell_parts: list[str] = []
        self.row_cells: list[str] = []
        self.heading = None
        self.heading_parts: list[str] = []
        self.h1_population_cue = False
        self.section_heading_cues = 0
        self.tables = 0
        self.rows = 0
        self.nonblank_rows = 0
        self.multicell_rows = 0
        self.header_rows = 0
        self.possible_data_rows = 0
        self.columns = Counter()
        self.header_cues = Counter()

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table_depth += 1
            if self.table_depth != 1:
                raise ValueError("Nested HTML tables need separate review")
            self.tables += 1
        elif tag == "tr" and self.table_depth == 1:
            if self.row_open:
                raise ValueError("Nested HTML rows need separate review")
            self.row_open = True
            self.row_cells = []
        elif tag in ("th", "td") and self.row_open:
            if self.cell_tag is not None:
                raise ValueError("Nested HTML cells need separate review")
            self.cell_tag = tag
            self.cell_parts = []
        elif tag in ("h1", "h2", "h3", "h4") and self.table_depth == 0:
            if self.heading is None:
                self.heading = tag
                self.heading_parts = []

    def handle_data(self, data):
        if self.cell_tag is not None:
            self.cell_parts.append(data)
            if sum(map(len, self.cell_parts)) > MAX_CELL_CHARS:
                raise ValueError("Oversized HTML table cell")
        elif self.heading is not None:
            self.heading_parts.append(data)
            if sum(map(len, self.heading_parts)) > MAX_CELL_CHARS:
                raise ValueError("Oversized HTML heading")

    def handle_endtag(self, tag):
        if self.cell_tag == tag:
            if len(self.row_cells) >= MAX_COLUMNS:
                raise ValueError("Excessive table width")
            self.row_cells.append(" ".join(" ".join(self.cell_parts).split()))
            self.cell_parts = []
            self.cell_tag = None
        elif tag == "tr" and self.row_open:
            if self.cell_tag is not None:
                raise ValueError("Unclosed HTML cell")
            self._finish_row()
            self.row_open = False
            self.row_cells = []
        elif tag == "table" and self.table_depth:
            if self.row_open:
                raise ValueError("Unclosed HTML row")
            self.table_depth -= 1
        elif tag == self.heading:
            value = " ".join(" ".join(self.heading_parts).split())
            if tag == "h1" and _TITLE_CUE[self.population].search(value):
                self.h1_population_cue = True
            if re.search(r"\bsezione\s*(?:n\.?\s*)?\d{1,2}\b", value, re.I):
                self.section_heading_cues += 1
            self.heading = None
            self.heading_parts = []

    def _finish_row(self):
        self.rows += 1
        if self.rows > MAX_TABLE_ROWS:
            raise ValueError("Excessive HTML table rows")
        width = len(self.row_cells)
        if width > MAX_COLUMNS:
            raise ValueError("Excessive HTML table width")
        self.columns[str(width)] += 1
        filled = [value for value in self.row_cells if value]
        if filled:
            self.nonblank_rows += 1
        if len(filled) >= 2:
            self.multicell_rows += 1
        # Mark header-shaped rows as such; never turn a row into an approved
        # observation or infer distinct legal entities from repeated sectors.
        joined = " ".join(self.row_cells)
        cues = [key for key, regex in _HEADER_CUES.items()
                if regex.search(joined)]
        if len(cues) >= 2:
            self.header_rows += 1
            self.header_cues.update(cues)
        elif filled:
            self.possible_data_rows += 1

    def summary(self) -> dict:
        if self.table_depth or self.row_open or self.cell_tag is not None:
            raise ValueError("Unclosed HTML table structure")
        return {
            "html_tables": self.tables,
            "physical_table_rows": self.rows,
            "nonblank_table_rows": self.nonblank_rows,
            "multicell_table_rows": self.multicell_rows,
            "header_shaped_rows": self.header_rows,
            "possible_data_shaped_rows_not_records": self.possible_data_rows,
            "row_widths": dict(sorted(self.columns.items())),
            "header_cues_in_header_shaped_rows": dict(sorted(self.header_cues.items())),
            "population_h1_cue": self.h1_population_cue,
            "section_heading_cues": self.section_heading_cues,
            "logical_record_census": False,
            "date_authenticated": False,
            "status_or_sector_validated": False,
            "privacy_approved": False,
        }


def profile_html(raw: bytes, population: str) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_HTML_BYTES:
        raise ValueError("HTML input exceeds bounded source review")
    if not raw.lstrip().lower().startswith((b"<!doctype html", b"<html")):
        raise ValueError("Archived original does not begin as HTML")
    parser = _Structure(population)
    parser.feed(raw.decode("utf-8", errors="strict"))
    parser.close()
    result = parser.summary()
    if not result["html_tables"] or not result["physical_table_rows"]:
        raise ValueError("No physical HTML table rows")
    return result


def audit_pair(store, *, pins=PINS, scanner=profile_html) -> dict:
    if len(pins) != 2 or {item[0] for item in pins} != {"listed", "applicant"}:
        raise ValueError("Both population originals required")
    results = []
    for population, digest, size in pins:
        item = {"population": population, "original_sha256": digest,
                "expected_bytes": size, "source_bytes_verified": False}
        try:
            raw = store.read_digest_verified(digest)
            if len(raw) != size or sha256(raw).hexdigest() != digest:
                raise ValueError("Original size or digest mismatch")
            item["source_bytes_verified"] = True
            item["physical_html_profile"] = scanner(raw, population)
        except Exception as exc:
            item["review_code"] = (
                "byte_identity_mismatch" if str(exc) == "Original size or digest mismatch"
                else "source_only_review_failed")
            item["error_type"] = type(exc).__name__
        results.append(item)
    return {
        "scope": "la_spezia_official_html_pair_source_only",
        "robot_revision": ROBOT_REVISION,
        "review_only": True,
        "originals_expected": 2,
        "originals_sha_verified": sum(x["source_bytes_verified"] for x in results),
        "physical_profiles_completed": sum("physical_html_profile" in x for x in results),
        "source_edition_approved": False,
        "official_edition_date_approved": False,
        "privacy_approved": False,
        "public_release_eligible": False,
        "postgresql_writes": 0,
        "public_promotions": 0,
        "results": results,
    }


def main() -> int:
    try:
        cfg = StoreConfig.from_env()
        result = audit_pair(EvidenceStore(client_for(cfg), cfg))
    except Exception:
        result = {
            "scope": "la_spezia_official_html_pair_source_only",
            "review_only": True,
            "originals_expected": 2,
            "originals_sha_verified": 0,
            "physical_profiles_completed": 0,
            "source_edition_approved": False,
            "privacy_approved": False,
            "public_release_eligible": False,
            "postgresql_writes": 0,
            "public_promotions": 0,
            "review_code": "protected_source_read_unavailable",
        }
    print(json.dumps(result, sort_keys=True))
    return 0  # A source diagnostic is not publication acceptance.


if __name__ == "__main__":
    raise SystemExit(main())
