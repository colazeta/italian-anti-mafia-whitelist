from __future__ import annotations

import hashlib
import json
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

PAGE = "https://prefettura.interno.gov.it/it/prefetture/bologna/white-list-provinciali-elenco-imprese-iscritte"
UA = "italian-anti-mafia-whitelist/0.1 (+source-probe)"


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            cleaned = " ".join(data.split())
            if cleaned:
                self._parts.append(cleaned)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._parts)))
            self._href = None
            self._parts = []


def fetch(url: str) -> tuple[bytes, str]:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=60) as response:  # noqa: S310 fixed official URL
        return response.read(), response.geturl()


def main() -> None:
    html, final = fetch(PAGE)
    p = Links()
    p.feed(html.decode("utf-8", errors="replace"))
    selected = []
    for href, label in p.links:
        url = urljoin(final, href)
        folded = (label + " " + url).casefold()
        if not ("iscr" in folded or "richied" in folded or url.casefold().endswith(".pdf")):
            continue
        if not (url.casefold().endswith(".pdf") or "/sites/default/files/" in url):
            continue
        data, resolved = fetch(url)
        if not data.startswith(b"%PDF"):
            continue
        path = Path("artifacts/bologna-ordinary-probe") / f"resource-{len(selected)+1}.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        text = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=True, capture_output=True).stdout.decode("utf-8", errors="replace")
        selected.append({
            "label": label,
            "url": url,
            "final_url": resolved,
            "sha256": hashlib.sha256(data).hexdigest(),
            "byte_size": len(data),
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "preview": "\n".join(text.splitlines()[:140]),
        })
    out = {"page_url": PAGE, "page_sha256": hashlib.sha256(html).hexdigest(), "selected": selected}
    manifest = Path("artifacts/bologna-ordinary-probe/manifest.json")
    manifest.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(manifest.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
