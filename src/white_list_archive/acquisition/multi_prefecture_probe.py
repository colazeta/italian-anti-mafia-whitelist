from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

USER_AGENT = "italian-anti-mafia-whitelist/0.1 (+source-probe)"

TARGETS = {
    "parma": {
        "page_url": "https://prefettura.interno.gov.it/it/prefetture/parma/evidenza/white-list",
        "labels": ["White list provinciali", "elenco imprese iscritte", "elenco imprese richiedenti"],
    },
    "pistoia": {
        "page_url": "https://prefettura.interno.gov.it/it/prefetture/pistoia/evidenza/white-list",
        "labels": ["Elenco Aziende Iscritte", "Elenco Aziende Richiedenti"],
    },
    "bologna-provincial": {
        "page_url": "https://prefettura.interno.gov.it/it/prefetture/bologna/white-list-provinciali",
        "labels": ["iscritte", "richiedenti"],
    },
    "bologna-post-sisma": {
        "page_url": "https://prefettura.interno.gov.it/it/prefetture/bologna/white-list-post-sisma-elenco-imprese-iscritte",
        "labels": ["iscpost", "ricpost", "iscritte", "richiedenti"],
    },
}


@dataclass(frozen=True)
class Link:
    label: str
    url: str


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.text_parts: list[str] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._parts = []

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if cleaned:
            self.text_parts.append(cleaned)
            if self._href is not None:
                self._parts.append(cleaned)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._parts).strip()))
            self._href = None
            self._parts = []


def _fetch(url: str) -> tuple[bytes, str, dict[str, str]]:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urlopen(req, timeout=60) as response:  # noqa: S310 - fixed official source inventory
        headers = {k.lower(): v for k, v in response.headers.items()}
        return response.read(), response.geturl(), headers


def _last_update(text: str) -> str | None:
    match = re.search(
        r"Ultimo aggiornamento\s+([A-Za-zÀ-ÿ]+\s+\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+20\d{2}(?:,\s*ore\s*\d{1,2}:\d{2})?)",
        text,
        re.I,
    )
    return match.group(1) if match else None


def _pdf_preview(path: Path, lines: int = 120) -> dict[str, object]:
    text = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"], check=True, capture_output=True
    ).stdout.decode("utf-8", errors="replace")
    info = subprocess.run(
        ["pdfinfo", str(path)], check=True, capture_output=True, text=True
    ).stdout
    page_count = None
    for line in info.splitlines():
        if line.startswith("Pages:"):
            page_count = int(line.split(":", 1)[1].strip())
            break
    return {
        "page_count": page_count,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "preview": "\n".join(text.splitlines()[:lines]),
    }


def probe(output_dir: Path) -> list[dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for key, spec in TARGETS.items():
        body, final_url, headers = _fetch(str(spec["page_url"]))
        html = body.decode(headers.get("content-encoding") or "utf-8", errors="replace")
        parser = _Parser()
        parser.feed(html)
        full_text = " ".join(parser.text_parts)
        links = [
            Link(label=label, url=urljoin(final_url, href))
            for href, label in parser.links
            if href
        ]
        wanted_terms = [str(x).casefold() for x in spec["labels"]]
        selected = [
            link
            for link in links
            if any(term in (link.label + " " + link.url).casefold() for term in wanted_terms)
        ]
        # Keep unique URLs while preserving order.
        seen: set[str] = set()
        selected = [link for link in selected if not (link.url in seen or seen.add(link.url))]

        target_result: dict[str, object] = {
            "key": key,
            "page_url": spec["page_url"],
            "final_page_url": final_url,
            "page_sha256": hashlib.sha256(body).hexdigest(),
            "last_update_text": _last_update(full_text),
            "all_links": [asdict(link) for link in links],
            "selected": [],
        }
        for idx, link in enumerate(selected, start=1):
            data, resolved, resource_headers = _fetch(link.url)
            suffix = ".pdf" if data.startswith(b"%PDF") else ".bin"
            path = output_dir / f"{key}-{idx}{suffix}"
            path.write_bytes(data)
            item: dict[str, object] = {
                "label": link.label,
                "url": link.url,
                "final_url": resolved,
                "sha256": hashlib.sha256(data).hexdigest(),
                "byte_size": len(data),
                "content_type": resource_headers.get("content-type"),
                "local_path": str(path),
            }
            if suffix == ".pdf":
                item.update(_pdf_preview(path))
            target_result["selected"].append(item)
        results.append(target_result)
    return results


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--output-dir", type=Path, default=Path("artifacts/multi-prefecture-probe"))
    cli.add_argument("--manifest", type=Path, default=Path("artifacts/multi-prefecture-probe/manifest.json"))
    args = cli.parse_args(argv)
    result = probe(args.output_dir)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(args.manifest.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
