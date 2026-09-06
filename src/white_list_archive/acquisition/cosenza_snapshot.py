from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from io import StringIO
from urllib.parse import urljoin
from urllib.request import Request, urlopen

_MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}

_DATE_RE = re.compile(
    r"(?:aggiornat[ioa]\s+al\s+)?(?P<day>\d{1,2})\s+"
    r"(?P<month>gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+"
    r"(?P<year>20\d{2})",
    re.IGNORECASE,
)
_SECTION_RE = re.compile(r"\bSEZ(?:IONE)?\.?\s*(I{1,3}|IV|V|VI{0,3}|IX|X)\b", re.IGNORECASE)


@dataclass(frozen=True)
class CosenzaAttachment:
    label: str
    url: str
    resource_kind: str
    section_notation: str | None = None


@dataclass(frozen=True)
class CosenzaSnapshotEdition:
    reference_date: date
    page_url: str
    attachments: tuple[CosenzaAttachment, ...]


class _LinkTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.text_parts: list[str] = []
        self._href: str | None = None
        self._link_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._link_parts = []

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if not cleaned:
            return
        self.text_parts.append(cleaned)
        if self._href is not None:
            self._link_parts.append(cleaned)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            label = " ".join(self._link_parts).strip()
            if label:
                self.links.append((self._href, label))
            self._href = None
            self._link_parts = []


def _extract_reference_date(text: str, page_url: str) -> date:
    match = _DATE_RE.search(text)
    if match is None:
        slug = page_url.replace("-", " ")
        match = _DATE_RE.search(slug)
    if match is None:
        raise ValueError("No explicit Cosenza White List reference date found")
    return date(
        int(match.group("year")),
        _MONTHS[match.group("month").lower()],
        int(match.group("day")),
    )


def _classify_attachment(label: str) -> tuple[str, str | None] | None:
    folded = " ".join(label.casefold().split())
    section_match = _SECTION_RE.search(label)
    if section_match:
        return "sector_list", section_match.group(1).upper()
    if "imprese iscritte" in folded and "richiedenti" in folded:
        return "combined_list", None
    if "elenco" in folded and "iscritte" in folded and "richiedenti" in folded:
        return "combined_list", None
    return None


def parse_cosenza_snapshot_html(html: str, page_url: str) -> CosenzaSnapshotEdition:
    parser = _LinkTextParser()
    parser.feed(html)
    full_text = " ".join(parser.text_parts)
    reference_date = _extract_reference_date(full_text, page_url)

    attachments: list[CosenzaAttachment] = []
    seen: set[tuple[str, str]] = set()
    for href, label in parser.links:
        classification = _classify_attachment(label)
        if classification is None:
            continue
        resource_kind, section_notation = classification
        absolute_url = urljoin(page_url, href)
        key = (absolute_url, resource_kind)
        if key in seen:
            continue
        seen.add(key)
        attachments.append(
            CosenzaAttachment(
                label=label,
                url=absolute_url,
                resource_kind=resource_kind,
                section_notation=section_notation,
            )
        )

    return CosenzaSnapshotEdition(
        reference_date=reference_date,
        page_url=page_url,
        attachments=tuple(attachments),
    )


def fetch_cosenza_snapshot(page_url: str, timeout: int = 30) -> CosenzaSnapshotEdition:
    request = Request(page_url, headers={"User-Agent": "italian-anti-mafia-whitelist/0.1"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - official public source URL supplied by caller
        html = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")
    return parse_cosenza_snapshot_html(html, page_url)


def _write_csv(edition: CosenzaSnapshotEdition, output: object) -> None:
    writer = csv.writer(output)
    writer.writerow(["reference_date", "page_url", "resource_kind", "section_notation", "label", "resource_url"])
    for attachment in edition.attachments:
        writer.writerow(
            [
                edition.reference_date.isoformat(),
                edition.page_url,
                attachment.resource_kind,
                attachment.section_notation or "",
                attachment.label,
                attachment.url,
            ]
        )


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Discover resources from one dated Cosenza White List snapshot page")
    cli.add_argument("url")
    cli.add_argument("--output", help="CSV output path; stdout if omitted")
    args = cli.parse_args(argv)

    edition = fetch_cosenza_snapshot(args.url)
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as handle:
            _write_csv(edition, handle)
    else:
        buffer = StringIO()
        _write_csv(edition, buffer)
        sys.stdout.write(buffer.getvalue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
