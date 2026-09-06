from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

USER_AGENT = "italian-anti-mafia-whitelist/0.1 (+research archive)"
COMBINED_RE = re.compile(r"(?:elenco|00).*imprese.*iscritte.*richiedenti", re.I | re.S)
DATE_RE = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](20\d{2})")


@dataclass(frozen=True)
class Link:
    text: str
    url: str


@dataclass(frozen=True)
class CaptureManifest:
    reference_date: str
    page_url: str
    resource_url: str
    final_url: str
    sha256: str
    byte_size: int
    content_type: str
    local_path: str
    page_count: int | None
    text_sha256: str | None
    schema_fingerprint: str | None


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[Link] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            text = " ".join("".join(self._text).split())
            self.links.append(Link(text=text, url=self._href))
            self._href = None
            self._text = []


def _request(url: str) -> tuple[bytes, str, str]:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as response:
        return response.read(), response.headers.get_content_type(), response.geturl()


def resolve_combined_resource(page_url: str) -> tuple[str, str]:
    body, _, final = _request(page_url)
    parser = _Links()
    parser.feed(body.decode("utf-8", errors="replace"))
    matches = [link for link in parser.links if COMBINED_RE.search(link.text)]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one combined White List attachment; found {len(matches)}")
    return urljoin(final, matches[0].url), matches[0].text


def _reference_date(page_url: str, title: str) -> str:
    match = DATE_RE.search(title)
    if match:
        d, m, y = map(int, match.groups())
        return f"{y:04d}-{m:02d}-{d:02d}"
    slug = page_url.rstrip("/").split("/")[-1]
    months = {"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,"giugno":6,"luglio":7,"agosto":8,"settembre":9,"ottobre":10,"novembre":11,"dicembre":12}
    m = re.search(r"-(\d{1,2})-([a-z]+)-(20\d{2})$", slug)
    if not m or m.group(2) not in months:
        raise RuntimeError(f"Cannot infer explicit reference date from {page_url}")
    return f"{int(m.group(3)):04d}-{months[m.group(2)]:02d}-{int(m.group(1)):02d}"


def _pdf_text(path: Path) -> tuple[str, int | None]:
    proc = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=True, capture_output=True)
    text = proc.stdout.decode("utf-8", errors="replace")
    info = subprocess.run(["pdfinfo", str(path)], check=True, capture_output=True, text=True).stdout
    pages = None
    for line in info.splitlines():
        if line.startswith("Pages:"):
            pages = int(line.split(":", 1)[1].strip())
            break
    return text, pages


def _schema_fingerprint(text: str) -> str:
    # Deliberately structural rather than content-addressed: normalise dates,
    # identifiers and long number runs, then fingerprint the recurring first-page labels.
    head = "\n".join(text.splitlines()[:180]).upper()
    head = re.sub(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", "<DATE>", head)
    head = re.sub(r"\b\d{7,16}\b", "<ID>", head)
    head = re.sub(r"\s+", " ", head).strip()
    return hashlib.sha256(head.encode()).hexdigest()


def capture(page_url: str, output_dir: Path) -> CaptureManifest:
    resource_url, title = resolve_combined_resource(page_url)
    reference_date = _reference_date(page_url, title)
    data, content_type, final_url = _request(resource_url)
    ext = ".pdf" if data.startswith(b"%PDF") or content_type == "application/pdf" else Path(urlparse(final_url).path).suffix or ".bin"
    edition_dir = output_dir / reference_date
    edition_dir.mkdir(parents=True, exist_ok=True)
    path = edition_dir / f"combined{ext}"
    path.write_bytes(data)

    text_sha = None
    fingerprint = None
    page_count = None
    if ext == ".pdf":
        text, page_count = _pdf_text(path)
        text_path = edition_dir / "combined.txt"
        text_path.write_text(text, encoding="utf-8")
        text_sha = hashlib.sha256(text.encode()).hexdigest()
        fingerprint = _schema_fingerprint(text)

    return CaptureManifest(
        reference_date=reference_date,
        page_url=page_url,
        resource_url=resource_url,
        final_url=final_url,
        sha256=hashlib.sha256(data).hexdigest(),
        byte_size=len(data),
        content_type=content_type,
        local_path=str(path),
        page_count=page_count,
        text_sha256=text_sha,
        schema_fingerprint=fingerprint,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("page_urls", nargs="+")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/cosenza-capture"))
    parser.add_argument("--manifest", type=Path, default=Path("artifacts/cosenza-capture/manifest.json"))
    args = parser.parse_args()
    manifests = [capture(url, args.output_dir) for url in args.page_urls]
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps([asdict(m) for m in manifests], indent=2, ensure_ascii=False), encoding="utf-8")
    print(args.manifest.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
