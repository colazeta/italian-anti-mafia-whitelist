import hashlib
import io
import json
import re
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import pdfplumber

LANDING = "https://prefettura.interno.gov.it/it/prefetture/alessandria/evidenza/white-list"
UA = "italian-anti-mafia-whitelist/0.1 (+source-resolution)"
DATE = re.compile(r"^\d{1,2}[./]\d{1,2}[./]\d{4}$")


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


def identifier_summary(values):
    lengths = Counter(len(re.sub(r"[^A-Za-z0-9]", "", value)) for value in values if value)
    unusual = [value for value in values if len(re.sub(r"[^A-Za-z0-9]", "", value)) not in {11, 16}]
    return {"lengths": dict(sorted(lengths.items())), "unusual_examples": unusual[:20], "unusual_count": len(unusual)}


def test_probe_alessandria_current_sources():
    html, content_type = fetch(LANDING)
    parser = Links()
    parser.feed(html.decode("utf-8", errors="replace"))
    pdf_links = []
    seen = set()
    for text, href in parser.links:
        url = urljoin(LANDING, href)
        folded = (text + " " + href).casefold()
        if re.search(r"\.pdf(?:$|\?)", url, re.I) and ("white" in folded or "iscr" in folded or "richied" in folded) and url not in seen:
            seen.add(url)
            pdf_links.append({"text": text, "url": url})

    reports = []
    for candidate in pdf_links:
        body, ctype = fetch(candidate["url"])
        listed = "richied" not in candidate["text"].casefold()
        source_rows = []
        sections = []
        outcomes = Counter()
        ids = []
        activities = Counter()
        date_cells = 0
        with pdfplumber.open(io.BytesIO(body)) as pdf:
            pages = len(pdf.pages)
            for page in pdf.pages:
                for table in page.extract_tables():
                    for raw in table:
                        row = [clean(cell) for cell in raw]
                        if row and row[0].upper().startswith("SEZIONE") and not any(row[1:]):
                            sections.append(row[0])
                        date_cells += sum(bool(DATE.fullmatch(cell)) for cell in row)
                        if listed:
                            if len(row) >= 7 and DATE.fullmatch(row[4] or "") and DATE.fullmatch(row[5] or ""):
                                source_rows.append(row[:7])
                                ids.append(row[3])
                                outcomes[row[6] or "<blank>"] += 1
                        else:
                            if len(row) >= 6 and DATE.fullmatch(row[4] or ""):
                                source_rows.append(row[:6])
                                ids.append(row[2])
                                activities[row[3]] += 1
                                outcomes[row[5] or "<blank>"] += 1
        if listed:
            groups = {}
            current_section = ""
            # Rewalk to associate every qualifying source row with its section.
            with pdfplumber.open(io.BytesIO(body)) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables():
                        for raw in table:
                            row = [clean(cell) for cell in raw]
                            if row and row[0].upper().startswith("SEZIONE") and not any(row[1:]):
                                current_section = row[0]
                                continue
                            if len(row) >= 7 and DATE.fullmatch(row[4] or "") and DATE.fullmatch(row[5] or ""):
                                key = (row[0], row[3], row[4], row[5], row[6])
                                group = groups.setdefault(key, {"offices": set(), "secondary": set(), "sections": set()})
                                if row[1]: group["offices"].add(row[1])
                                if row[2]: group["secondary"].add(row[2])
                                if current_section: group["sections"].add(current_section)
            unique_records = len(groups)
            max_sections = max((len(v["sections"]) for v in groups.values()), default=0)
            office_variant_groups = sum(len(v["offices"]) > 1 for v in groups.values())
        else:
            unique_records = len(source_rows)
            max_sections = None
            office_variant_groups = None
        reports.append({
            **candidate,
            "content_type": ctype,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "pages": pages,
            "source_rows": len(source_rows),
            "unique_records": unique_records,
            "date_cells": date_cells,
            "section_headers": sections,
            "outcomes": dict(outcomes),
            "identifier_summary": identifier_summary(ids),
            "activity_variants": len(activities),
            "activity_examples": list(activities)[:20],
            "max_sections_per_record": max_sections,
            "office_variant_groups": office_variant_groups,
            "first_row": source_rows[0] if source_rows else None,
            "last_row": source_rows[-1] if source_rows else None,
        })

    raise AssertionError("AL_COMPLETE=" + json.dumps({"landing_content_type": content_type, "pdf_reports": reports}, ensure_ascii=False))
