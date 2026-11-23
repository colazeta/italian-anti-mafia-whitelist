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
LATEST_REVIEW_REVISION = "d59c67677586b0b6cb373d69bcdcb1713fc0d1bd"
LATEST_PINS = (
    ("listed", "c99bb76cb85d13bc7dcd4c92819591b96121fb0390a4671f021d16e4e8c797bd", 147048),
    ("applicant", "f8a80612da73298d21812bbc966e5cf5b351d8f8b7d1aca246791f7621b494e0", 83852),
)
MAX_HTML_BYTES = 500_000
MAX_TABLE_ROWS = 20_000
MAX_TABLES = 128
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


# Only structural heading hints. A label is never a sector attribution.
_SECTION_CUE = re.compile(r"\bsezione\s*(?:n[.]?\s*)?(?:\d{1,2}|[IVXLCDM]{1,5})(?=\b|[.):])", re.I)


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
        self.section_label_cues = 0
        self.pending_section_labels = 0
        self.emphasis_tag = None
        self.emphasis_parts: list[str] = []
        self.tables = 0
        self.table_profiles: list[dict] = []
        self.active_table: dict | None = None
        self.row_has_th = False
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
            if self.tables >= MAX_TABLES:
                raise ValueError("Excessive number of HTML tables")
            self.tables += 1
            pending_labels = self.pending_section_labels
            self.pending_section_labels = 0
            self.active_table = {
                "table_ordinal": self.tables,
                "preceding_section_label_cues": pending_labels,
                "physical_rows": 0, "nonblank_rows": 0,
                "th_tag_rows": 0, "header_shaped_rows": 0,
                "possible_data_shaped_rows_not_records": 0,
                "row_widths": Counter(), "header_cues": Counter(),
            }
        elif tag == "tr" and self.table_depth == 1:
            if self.row_open:
                raise ValueError("Nested HTML rows need separate review")
            self.row_open = True
            self.row_cells = []
            self.row_has_th = False
        elif tag in ("th", "td") and self.row_open:
            if self.cell_tag is not None:
                raise ValueError("Nested HTML cells need separate review")
            self.cell_tag = tag
            if tag == "th":
                self.row_has_th = True
            self.cell_parts = []
        elif tag in ("h1", "h2", "h3", "h4") and self.table_depth == 0:
            if self.heading is None:
                self.heading = tag
                self.heading_parts = []
        elif (tag in ("strong", "b") and self.table_depth == 0
              and self.heading is None and self.emphasis_tag is None):
            self.emphasis_tag = tag
            self.emphasis_parts = []

    def handle_data(self, data):
        if self.cell_tag is not None:
            self.cell_parts.append(data)
            if sum(map(len, self.cell_parts)) > MAX_CELL_CHARS:
                raise ValueError("Oversized HTML table cell")
        elif self.heading is not None:
            self.heading_parts.append(data)
            if sum(map(len, self.heading_parts)) > MAX_CELL_CHARS:
                raise ValueError("Oversized HTML heading")
        elif self.emphasis_tag is not None:
            self.emphasis_parts.append(data)
            if sum(map(len, self.emphasis_parts)) > MAX_CELL_CHARS:
                raise ValueError("Oversized HTML emphasis")

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
            self.row_has_th = False
        elif tag == "table" and self.table_depth:
            if self.row_open:
                raise ValueError("Unclosed HTML row")
            if self.active_table is None:
                raise ValueError("Missing HTML table profile")
            profile = self.active_table
            self.table_profiles.append({
                **{k: v for k, v in profile.items()
                   if k not in ("row_widths", "header_cues")},
                "row_widths": dict(sorted(profile["row_widths"].items())),
                "header_cues": dict(sorted(profile["header_cues"].items())),
            })
            self.active_table = None
            self.table_depth -= 1
        elif tag == self.heading:
            value = " ".join(" ".join(self.heading_parts).split())
            if tag == "h1" and _TITLE_CUE[self.population].search(value):
                self.h1_population_cue = True
            self._record_section_label(value, from_heading=True)
            self.heading = None
            self.heading_parts = []
        elif tag == self.emphasis_tag:
            value = " ".join(" ".join(self.emphasis_parts).split())
            self._record_section_label(value, from_heading=False)
            self.emphasis_tag = None
            self.emphasis_parts = []

    def _record_section_label(self, value: str, *, from_heading: bool):
        if _SECTION_CUE.search(value):
            self.section_label_cues += 1
            self.pending_section_labels += 1
            if from_heading:
                self.section_heading_cues += 1

    def _finish_row(self):
        if self.active_table is None:
            raise ValueError("Missing HTML table during row audit")
        profile = self.active_table
        profile["physical_rows"] += 1
        self.rows += 1
        if self.rows > MAX_TABLE_ROWS:
            raise ValueError("Excessive HTML table rows")
        width = len(self.row_cells)
        if width > MAX_COLUMNS:
            raise ValueError("Excessive HTML table width")
        self.columns[str(width)] += 1
        profile["row_widths"][str(width)] += 1
        if self.row_has_th:
            profile["th_tag_rows"] += 1
        filled = [value for value in self.row_cells if value]
        if filled:
            self.nonblank_rows += 1
            profile["nonblank_rows"] += 1
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
            profile["header_shaped_rows"] += 1
            profile["header_cues"].update(cues)
        elif filled:
            self.possible_data_rows += 1
            profile["possible_data_shaped_rows_not_records"] += 1

    def summary(self) -> dict:
        if self.table_depth or self.row_open or self.cell_tag is not None:
            raise ValueError("Unclosed HTML table structure")
        if len(self.table_profiles) != self.tables or self.active_table is not None:
            raise ValueError("Unreconciled HTML table profiles")
        if sum(p["preceding_section_label_cues"] for p in self.table_profiles) + self.pending_section_labels != self.section_label_cues:
            raise ValueError("Unreconciled structural section label hints")
        if any(sum(p[key] for p in self.table_profiles) != total for key, total in (
            ("physical_rows", self.rows), ("nonblank_rows", self.nonblank_rows),
            ("header_shaped_rows", self.header_rows),
            ("possible_data_shaped_rows_not_records", self.possible_data_rows),
        )):
            raise ValueError("HTML table profile totals disagree")
        return {
            "html_tables": self.tables,
            "table_profiles": self.table_profiles,
            "physical_table_rows": self.rows,
            "nonblank_table_rows": self.nonblank_rows,
            "multicell_table_rows": self.multicell_rows,
            "header_shaped_rows": self.header_rows,
            "possible_data_shaped_rows_not_records": self.possible_data_rows,
            "row_widths": dict(sorted(self.columns.items())),
            "header_cues_in_header_shaped_rows": dict(sorted(self.header_cues.items())),
            "population_h1_cue": self.h1_population_cue,
            "section_heading_cues": self.section_heading_cues,
            "structural_section_label_cues": self.section_label_cues,
            "trailing_section_label_cues": self.pending_section_labels,
            "sector_to_table_mapping_approved": False,
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


class _TableIdentity(_Structure):
    """Compare ordered normalised physical table cells without exporting them."""

    def __init__(self, population):
        super().__init__(population)
        self.identity = sha256()

    def _finish_row(self):
        super()._finish_row()
        payload = json.dumps(
            [self.tables, self.row_has_th, self.row_cells],
            ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")
        self.identity.update(len(payload).to_bytes(8, "big"))
        self.identity.update(payload)


def _table_identity(raw, population):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_HTML_BYTES:
        raise ValueError("HTML input exceeds bounded source review")
    if not raw.lstrip().lower().startswith((b"<!doctype html", b"<html")):
        raise ValueError("Archived original does not begin as HTML")
    parser = _TableIdentity(population)
    parser.feed(raw.decode("utf-8", errors="strict"))
    parser.close()
    profile = parser.summary()
    if not profile["html_tables"] or not profile["physical_table_rows"]:
        raise ValueError("No physical HTML table rows")
    return profile, parser.identity.digest()


def compare_archived_versions(store, *, previous=PINS, current=LATEST_PINS):
    """Distinguish byte drift from ordered normalised physical cell drift."""
    for pins in (previous, current):
        if len(pins) != 2 or {x[0] for x in pins} != {"listed", "applicant"}:
            raise ValueError("Both population originals required per revision")
    rows = []
    for population in ("listed", "applicant"):
        item = {"population": population, "versions_verified": 0,
                "ordered_normalised_table_cells_equal": None,
                "physical_structure_equal": None}
        identities = []
        profiles = []
        for pins in (previous, current):
            _, digest, size = next(pin for pin in pins if pin[0] == population)
            try:
                raw = store.read_digest_verified(digest)
                if len(raw) != size or sha256(raw).hexdigest() != digest:
                    raise ValueError("Original size or digest mismatch")
                item["versions_verified"] += 1
                profile, identity = _table_identity(raw, population)
                profiles.append(profile)
                identities.append(identity)
            except Exception:
                item["review_code"] = "version_comparison_incomplete"
        if len(identities) == 2:
            item["ordered_normalised_table_cells_equal"] = identities[0] == identities[1]
            item["physical_structure_equal"] = profiles[0] == profiles[1]
            item["review_code"] = "source_cell_comparison_only"
        rows.append(item)
    return {
        "scope": "la_spezia_exact_archived_version_comparison",
        "previous_robot_revision": ROBOT_REVISION,
        "current_robot_revision": LATEST_REVIEW_REVISION,
        "versions_expected": 4,
        "versions_verified": sum(row["versions_verified"] for row in rows),
        "population_comparisons_completed": sum(
            row["ordered_normalised_table_cells_equal"] is not None for row in rows),
        "source_edition_approved": False, "privacy_approved": False,
        "public_release_eligible": False, "postgresql_writes": 0,
        "public_promotions": 0, "results": rows,
    }


def main() -> int:
    try:
        cfg = StoreConfig.from_env()
        store = EvidenceStore(client_for(cfg), cfg)
        result = audit_pair(store)
        result["version_comparison"] = compare_archived_versions(store)
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
