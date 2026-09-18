from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import pdfplumber

LANDING_URL = "https://prefettura.interno.gov.it/it/prefetture/lecce/evidenza/white-list"
OUT = Path("tmp/lecce-probe")
USER_AGENT = "italian-anti-mafia-whitelist/0.1 (+Lecce source-boundary audit)"
ID_RE = re.compile(r"(?<![A-Za-z0-9])(?:\d{11}|[A-Za-z0-9]{16})(?![A-Za-z0-9])")
DATE_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
SECTION_RE = re.compile(r"SEZIONE\s+([IVX]+)\s*[–—-]\s*([^\n]+)", re.I)


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._href: str | None = None
        self._parts: list[str] = []
        self.anchors: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        self._href = next((value for key, value in attrs if key.casefold() == "href" and value), None)
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._href is not None:
            text = " ".join("".join(self._parts).split())
            self.anchors.append((text, self._href))
            self._href = None
            self._parts = []


def fetch(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/pdf,*/*",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urlopen(request, timeout=90) as response:  # noqa: S310 - fixed official source
        return response.read()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def choose(anchors: list[tuple[str, str]], pattern: str) -> tuple[str, str]:
    regex = re.compile(pattern, re.IGNORECASE)
    hits = [(text, href) for text, href in anchors if regex.search(text)]
    if len(hits) != 1:
        raise RuntimeError(json.dumps({"pattern": pattern, "hits": hits}, ensure_ascii=False))
    return hits[0]


def cmd(*args: str) -> str:
    completed = subprocess.run(args, check=True, capture_output=True, text=True)
    return completed.stdout


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def useful_lines(text: str) -> list[str]:
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def identifiers(raw: str) -> list[str]:
    values: list[str] = []
    for match in ID_RE.finditer(clean(raw)):
        value = match.group(0).upper()
        if value not in values:
            values.append(value)
    return values


def valid_date(raw: str) -> bool:
    raw = clean(raw)
    match = DATE_RE.fullmatch(raw)
    if match is None:
        return False
    day, month, year = map(int, match.groups())
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True


def table_geometry(pdf_path: Path) -> dict[str, object]:
    pages: list[dict[str, object]] = []
    total_rows = 0
    widths: dict[str, int] = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            tables = page.find_tables()
            page_info: dict[str, object] = {"page": page_number, "table_count": len(tables)}
            if len(tables) == 1:
                extracted = tables[0].extract() or []
                rows = [[clean(cell) for cell in row] for row in extracted if any(clean(cell) for cell in row)]
                total_rows += len(rows)
                for row in rows:
                    widths[str(len(row))] = widths.get(str(len(row)), 0) + 1
                page_info.update(
                    {
                        "nonblank_rows": len(rows),
                        "widths": sorted({len(row) for row in rows}),
                        "first_rows": rows[:3],
                        "last_rows": rows[-3:],
                    }
                )
            pages.append(page_info)
    return {"total_nonblank_table_rows": total_rows, "row_width_histogram": widths, "pages": pages}


def inspect_pdf(kind: str, label: str, url: str) -> dict[str, object]:
    first = fetch(url)
    second = fetch(url)
    if first != second:
        raise RuntimeError(f"{kind} attachment changed between independent captures")
    pdf_path = OUT / f"lecce_{kind}.pdf"
    text_path = OUT / f"lecce_{kind}.txt"
    pdf_path.write_bytes(first)
    cmd("pdftotext", "-layout", str(pdf_path), str(text_path))
    text = text_path.read_text(encoding="utf-8", errors="replace")
    lines = useful_lines(text)
    info = cmd("pdfinfo", str(pdf_path))
    pages_match = re.search(r"^Pages:\s+(\d+)\s*$", info, re.MULTILINE)
    return {
        "kind": kind,
        "label": label,
        "url": url,
        "bytes": len(first),
        "sha256": sha256(first),
        "captures_identical": True,
        "pages": int(pages_match.group(1)) if pages_match else None,
        "nonblank_text_lines": len(lines),
        "head": lines[:40],
        "tail": lines[-40:],
        "table_geometry": table_geometry(pdf_path),
    }


def compact_pdf(item: dict[str, object]) -> dict[str, object]:
    geometry = item["table_geometry"]
    assert isinstance(geometry, dict)
    pages = geometry["pages"]
    assert isinstance(pages, list)
    return {
        "label": item["label"],
        "url": item["url"],
        "bytes": item["bytes"],
        "sha256": item["sha256"],
        "captures_identical": item["captures_identical"],
        "pdf_pages": item["pages"],
        "nonblank_text_lines": item["nonblank_text_lines"],
        "table_counts_by_page": [page.get("table_count") for page in pages],
        "nonblank_table_rows_by_page": [page.get("nonblank_rows") for page in pages],
        "row_widths_by_page": [page.get("widths") for page in pages],
        "total_nonblank_table_rows": geometry["total_nonblank_table_rows"],
        "row_width_histogram": geometry["row_width_histogram"],
    }


def _identity_key(row: list[str], name_index: int, office_index: int, identifier_index: int) -> str:
    ids = identifiers(row[identifier_index])
    if ids:
        return "ids:" + "|".join(sorted(ids))
    return f"fallback:{clean(row[name_index]).casefold()}|{clean(row[office_index]).casefold()}"


def audit_listed(pdf_path: Path) -> dict[str, object]:
    headers: Counter[tuple[str, ...]] = Counter()
    update_values: Counter[str] = Counter()
    section_raw_rows: Counter[str] = Counter()
    section_unique_ids: dict[str, set[str]] = defaultdict(set)
    rows_by_identity: dict[str, list[dict[str, object]]] = defaultdict(list)
    invalid_dates: list[dict[str, object]] = []
    blank_identifier_rows = 0
    parsed_identifier_rows = 0
    multi_identifier_rows = 0
    raw_data_rows = 0
    pages_without_section: list[int] = []
    section_pages: dict[str, list[int]] = defaultdict(list)

    with pdfplumber.open(pdf_path) as pdf:
        current_section = ""
        for page_number, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            hits = SECTION_RE.findall(text)
            if len(hits) > 1:
                raise RuntimeError(f"listed page {page_number}: multiple section headings: {hits!r}")
            if hits:
                current_section = hits[0][0].upper()
            if not current_section:
                pages_without_section.append(page_number)
            else:
                section_pages[current_section].append(page_number)
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(f"listed page {page_number}: expected one table, got {len(tables)}")
            extracted = tables[0].extract() or []
            rows = [[clean(cell) for cell in row] for row in extracted if any(clean(cell) for cell in row)]
            if not rows:
                raise RuntimeError(f"listed page {page_number}: empty table")
            header = tuple(rows[0])
            headers[header] += 1
            if len(header) != 7:
                raise RuntimeError(f"listed page {page_number}: unexpected header width {len(header)}")
            folded = [cell.casefold() for cell in header]
            required = ["denominazione", "sede legale", "codice fiscale", "data iscrizione", "data scadenza", "aggiornamento in corso"]
            if any(not any(token in cell for cell in folded) for token in required):
                raise RuntimeError(f"listed page {page_number}: unrecognised header: {header!r}")
            name_i = next(i for i, cell in enumerate(folded) if "denominazione" in cell)
            office_i = next(i for i, cell in enumerate(folded) if "sede legale" in cell)
            id_i = next(i for i, cell in enumerate(folded) if "codice fiscale" in cell)
            listing_i = next(i for i, cell in enumerate(folded) if "data iscrizione" in cell)
            expiry_i = next(i for i, cell in enumerate(folded) if "data scadenza" in cell)
            update_i = next(i for i, cell in enumerate(folded) if "aggiornamento in corso" in cell)
            for row_number, row in enumerate(rows[1:], 1):
                if len(row) != 7:
                    raise RuntimeError(f"listed page {page_number} row {row_number}: width drift")
                if not clean(row[name_i]):
                    raise RuntimeError(f"listed page {page_number} row {row_number}: blank company name")
                raw_data_rows += 1
                section_raw_rows[current_section] += 1
                ids = identifiers(row[id_i])
                if not clean(row[id_i]):
                    blank_identifier_rows += 1
                elif ids:
                    parsed_identifier_rows += 1
                    multi_identifier_rows += len(ids) > 1
                key = _identity_key(row, name_i, office_i, id_i)
                section_unique_ids[current_section].add(key)
                update_values[clean(row[update_i])] += 1
                for field_name, index in (("listing", listing_i), ("expiry", expiry_i)):
                    raw_date = clean(row[index])
                    if raw_date and not valid_date(raw_date):
                        invalid_dates.append({"page": page_number, "row": row_number, "field": field_name, "raw": raw_date})
                rows_by_identity[key].append(
                    {
                        "page": page_number,
                        "section": current_section,
                        "name": clean(row[name_i]),
                        "office": clean(row[office_i]),
                        "identifier_raw": clean(row[id_i]),
                        "listing": clean(row[listing_i]),
                        "expiry": clean(row[expiry_i]),
                        "update": clean(row[update_i]),
                    }
                )

    conflicts: Counter[str] = Counter()
    conflict_examples: list[dict[str, object]] = []
    section_cardinality: Counter[int] = Counter()
    for key, observations in rows_by_identity.items():
        section_cardinality[len({str(item["section"]) for item in observations})] += 1
        fields = {
            "name": {str(item["name"]) for item in observations},
            "office": {str(item["office"]) for item in observations},
            "listing": {str(item["listing"]) for item in observations},
            "expiry": {str(item["expiry"]) for item in observations},
            "update": {str(item["update"]) for item in observations},
        }
        changed = [field for field, values in fields.items() if len(values) > 1]
        for field in changed:
            conflicts[field] += 1
        if changed and len(conflict_examples) < 20:
            conflict_examples.append({"identity": key, "fields": changed, "observations": observations})

    return {
        "raw_data_rows": raw_data_rows,
        "unique_identity_count": len(rows_by_identity),
        "deduplicated_cross_section_rows": raw_data_rows - len(rows_by_identity),
        "header_variants": [{"count": count, "header": list(header)} for header, count in headers.items()],
        "section_pages": dict(section_pages),
        "section_raw_rows": dict(section_raw_rows),
        "section_unique_identity_counts": {section: len(values) for section, values in section_unique_ids.items()},
        "section_cardinality_per_identity": {str(key): value for key, value in sorted(section_cardinality.items())},
        "update_value_counts": dict(update_values),
        "blank_identifier_rows": blank_identifier_rows,
        "parsed_identifier_rows": parsed_identifier_rows,
        "multi_identifier_rows": multi_identifier_rows,
        "invalid_date_count": len(invalid_dates),
        "invalid_date_examples": invalid_dates[:30],
        "cross_section_conflict_counts": dict(conflicts),
        "cross_section_conflict_examples": conflict_examples,
        "pages_without_section": pages_without_section,
    }


def audit_applicants(pdf_path: Path) -> dict[str, object]:
    headers: Counter[tuple[str, ...]] = Counter()
    invalid_dates: list[dict[str, object]] = []
    blank_identifier_rows = 0
    parsed_identifier_rows = 0
    multi_identifier_rows = 0
    identities: Counter[str] = Counter()
    rows_total = 0
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            tables = page.find_tables()
            if len(tables) != 1:
                raise RuntimeError(f"applicant page {page_number}: expected one table, got {len(tables)}")
            extracted = tables[0].extract() or []
            rows = [[clean(cell) for cell in row] for row in extracted if any(clean(cell) for cell in row)]
            if not rows or len(rows[0]) != 4:
                raise RuntimeError(f"applicant page {page_number}: missing four-column header")
            header = tuple(rows[0])
            headers[header] += 1
            folded = [cell.casefold() for cell in header]
            required = ["ragione sociale", "sede legale", "codice fiscale", "data di presentazione"]
            if any(not any(token in cell for cell in folded) for token in required):
                raise RuntimeError(f"applicant page {page_number}: unrecognised header {header!r}")
            name_i = next(i for i, cell in enumerate(folded) if "ragione sociale" in cell)
            office_i = next(i for i, cell in enumerate(folded) if "sede legale" in cell)
            id_i = next(i for i, cell in enumerate(folded) if "codice fiscale" in cell)
            date_i = next(i for i, cell in enumerate(folded) if "data di presentazione" in cell)
            for row_number, row in enumerate(rows[1:], 1):
                if len(row) != 4:
                    raise RuntimeError(f"applicant page {page_number} row {row_number}: width drift")
                if not clean(row[name_i]):
                    raise RuntimeError(f"applicant page {page_number} row {row_number}: blank company name")
                rows_total += 1
                ids = identifiers(row[id_i])
                if not clean(row[id_i]):
                    blank_identifier_rows += 1
                elif ids:
                    parsed_identifier_rows += 1
                    multi_identifier_rows += len(ids) > 1
                identities[_identity_key(row, name_i, office_i, id_i)] += 1
                raw_date = clean(row[date_i])
                if raw_date and not valid_date(raw_date):
                    invalid_dates.append({"page": page_number, "row": row_number, "raw": raw_date})
    return {
        "rows": rows_total,
        "unique_identity_count": len(identities),
        "duplicate_identity_occurrences": sum(count - 1 for count in identities.values() if count > 1),
        "duplicate_identity_count": sum(count > 1 for count in identities.values()),
        "header_variants": [{"count": count, "header": list(header)} for header, count in headers.items()],
        "blank_identifier_rows": blank_identifier_rows,
        "parsed_identifier_rows": parsed_identifier_rows,
        "multi_identifier_rows": multi_identifier_rows,
        "invalid_date_count": len(invalid_dates),
        "invalid_date_examples": invalid_dates[:30],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    landing_first = fetch(LANDING_URL)
    landing_second = fetch(LANDING_URL)
    if landing_first != landing_second:
        raise RuntimeError("Lecce landing page changed between independent captures")
    parser = AnchorParser()
    parser.feed(landing_first.decode("utf-8", errors="replace"))
    parser.close()

    listed_label, listed_href = choose(parser.anchors, r"ELENCO\s+WHITE\s+LIST\s+PER\s+CATEGORIA")
    applicant_label, applicant_href = choose(parser.anchors, r"ELENCO\s+RICHIEDENTI\s+ISCRIZIONE")
    listed_url = urljoin(LANDING_URL, listed_href)
    applicant_url = urljoin(LANDING_URL, applicant_href)
    listed = inspect_pdf("listed", listed_label, listed_url)
    applicants = inspect_pdf("applicants", applicant_label, applicant_url)
    listed_path = OUT / "lecce_listed.pdf"
    applicant_path = OUT / "lecce_applicants.pdf"

    report = {
        "landing_url": LANDING_URL,
        "landing_bytes": len(landing_first),
        "landing_sha256": sha256(landing_first),
        "landing_captures_identical": True,
        "matched_anchors": {
            "listed": {"label": listed_label, "url": listed_url},
            "applicants": {"label": applicant_label, "url": applicant_url},
        },
        "listed": listed,
        "applicants": applicants,
    }
    summary = {
        "landing_url": LANDING_URL,
        "landing_bytes": len(landing_first),
        "landing_sha256": sha256(landing_first),
        "landing_captures_identical": True,
        "listed": compact_pdf(listed),
        "applicants": compact_pdf(applicants),
        "listed_semantics": audit_listed(listed_path),
        "applicant_semantics": audit_applicants(applicant_path),
    }
    (OUT / "lecce_probe.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "lecce_probe_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
