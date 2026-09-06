"""Discovery of the Ministry of the Interior national White List index.

The national index is treated as a discovery source, not as the canonical data
source for company records.  It tells us which territorial White List resource
is exposed for each jurisdiction and allows us to detect changes in national
coverage without guessing local URLs.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

NATIONAL_INDEX_URL = "https://prefettura.interno.gov.it/it/white-list-nazionale"
DEFAULT_USER_AGENT = (
    "italian-anti-mafia-whitelist/0.1 (+https://github.com/colazeta/italian-anti-mafia-whitelist)"
)


@dataclass(frozen=True, slots=True)
class NationalIndexEntry:
    jurisdiction_name: str
    title: str
    white_list_url: str
    source_page: str


@dataclass(slots=True)
class _Cell:
    text_parts: list[str]
    href: str | None = None

    @property
    def text(self) -> str:
        return " ".join(" ".join(self.text_parts).split())


class _NationalIndexHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[_Cell]] = []
        self._row: list[_Cell] | None = None
        self._cell: _Cell | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = _Cell([])
        elif tag == "a" and self._cell is not None:
            href = dict(attrs).get("href")
            if href and self._cell.href is None:
                self._cell.href = href

    def handle_data(self, data: str) -> None:
        if self._cell is not None and data.strip():
            self._cell.text_parts.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(self._cell)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
            self._cell = None


def parse_national_index_html(html: str, page_url: str) -> list[NationalIndexEntry]:
    """Parse one page of the Ministry national White List index."""
    parser = _NationalIndexHTMLParser()
    parser.feed(html)

    entries: list[NationalIndexEntry] = []
    for row in parser.rows:
        if len(row) < 3:
            continue
        jurisdiction = row[0].text.strip()
        title = row[1].text.strip()
        href = row[2].href
        if not jurisdiction or jurisdiction.casefold() == "provincia":
            continue
        if "white list" not in title.casefold():
            continue
        if not href:
            continue
        entries.append(
            NationalIndexEntry(
                jurisdiction_name=jurisdiction,
                title=title,
                white_list_url=urljoin(page_url, href),
                source_page=page_url,
            )
        )
    return entries


def _page_url(base_url: str, page: int) -> str:
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode({'page': page})}"


def fetch_html(url: str, *, timeout: float = 30.0, user_agent: str = DEFAULT_USER_AGENT) -> str:
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed official discovery endpoint by default
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def discover_national_index(
    *,
    base_url: str = NATIONAL_INDEX_URL,
    max_pages: int = 10,
    timeout: float = 30.0,
) -> list[NationalIndexEntry]:
    """Fetch paginated index pages until no new White List rows are found."""
    if max_pages < 1:
        raise ValueError("max_pages must be >= 1")

    found: dict[tuple[str, str], NationalIndexEntry] = {}
    for page in range(max_pages):
        url = _page_url(base_url, page)
        entries = parse_national_index_html(fetch_html(url, timeout=timeout), url)
        before = len(found)
        for entry in entries:
            found[(entry.jurisdiction_name.casefold(), entry.white_list_url)] = entry
        if page > 0 and (not entries or len(found) == before):
            break

    return sorted(found.values(), key=lambda item: item.jurisdiction_name.casefold())


def entries_to_csv(entries: Iterable[NationalIndexEntry]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["jurisdiction_name", "title", "white_list_url", "source_page"],
        lineterminator="\n",
    )
    writer.writeheader()
    for entry in entries:
        writer.writerow(
            {
                "jurisdiction_name": entry.jurisdiction_name,
                "title": entry.title,
                "white_list_url": entry.white_list_url,
                "source_page": entry.source_page,
            }
        )
    return buffer.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover the official national White List index")
    parser.add_argument("--base-url", default=NATIONAL_INDEX_URL)
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--output", type=Path, help="CSV destination; stdout when omitted")
    args = parser.parse_args(argv)

    entries = discover_national_index(
        base_url=args.base_url,
        max_pages=args.max_pages,
        timeout=args.timeout,
    )
    payload = entries_to_csv(entries)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
