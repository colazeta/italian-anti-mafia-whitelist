from __future__ import annotations

import hashlib
import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import pdfplumber

LANDING_URL = "https://prefettura.interno.gov.it/it/prefetture/lecce/evidenza/white-list"
OUT = Path("tmp/lecce-probe")
USER_AGENT = "italian-anti-mafia-whitelist/0.1 (+Lecce source-boundary audit)"


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
