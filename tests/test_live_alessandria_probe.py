import hashlib
import io
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import pdfplumber

LANDING = "https://prefettura.interno.gov.it/it/prefetture/alessandria/evidenza/white-list"
UA = "italian-anti-mafia-whitelist/0.1 (+source-resolution)"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.current = dict(attrs).get("href")

    def handle_data(self, data):
        if self.current and data.strip():
            self.links.append((data.strip(), self.current))

    def handle_endtag(self, tag):
        if tag == "a":
            self.current = None


def fetch(url):
    req = Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urlopen(req, timeout=90) as response:
        return response.read(), response.headers.get_content_type()


def clean(value):
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def test_probe_alessandria_current_sources():
    html, content_type = fetch(LANDING)
    parser = Links()
    parser.feed(html.decode("utf-8", errors="replace"))
    candidates = []
    seen = set()
    for text, href in parser.links:
        url = urljoin(LANDING, href)
        folded = (text + " " + href).casefold()
        if ("white" in folded or "iscr" in folded or "richied" in folded) and url not in seen:
            seen.add(url)
            candidates.append({"text": text, "url": url})

    reports = []
    for candidate in candidates:
        if not re.search(r"\.pdf(?:$|\?)", candidate["url"], re.I):
            continue
        body, ctype = fetch(candidate["url"])
        report = {
            **candidate,
            "content_type": ctype,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "pages": None,
            "tables": [],
            "page_text_samples": [],
        }
        with pdfplumber.open(io.BytesIO(body)) as pdf:
            report["pages"] = len(pdf.pages)
            for page_no, page in enumerate(pdf.pages[:3], start=1):
                text = clean(page.extract_text() or "")
                report["page_text_samples"].append({"page": page_no, "text": text[:1200]})
                for table_no, table in enumerate(page.extract_tables()[:3], start=1):
                    rows = [[clean(cell) for cell in row] for row in table[:8]]
                    report["tables"].append({"page": page_no, "table": table_no, "rows": rows})
        reports.append(report)

    payload = {
        "landing_content_type": content_type,
        "candidate_links": candidates,
        "pdf_reports": reports,
    }
    raise AssertionError("AL_PROBE=" + json.dumps(payload, ensure_ascii=False))
