from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

from white_list_archive.parsers.brindisi_tables import parse_brindisi_applicants, parse_brindisi_listed
from white_list_archive.publishing.public_national_registry import _semantic_digest


def fetch(url: str, path: Path) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 white-list-archive-parser-smoke"})
    with urllib.request.urlopen(req, timeout=60) as response:
        body = response.read()
    if not body.startswith(b"%PDF"):
        raise RuntimeError(f"not a PDF: {url}")
    path.write_bytes(body)
    return hashlib.sha256(body).hexdigest()


def config(key: str, scope: str, url: str, sha: str) -> dict[str, object]:
    return {
        "source_key": key,
        "authority_key": "brindisi",
        "authority_name": "Prefettura di Brindisi",
        "register_key": "brindisi-ordinary",
        "register_name": "White List ordinaria",
        "population_scope": scope,
        "reference_date": "2026-09-08",
        "source_page_url": "https://prefettura.interno.gov.it/it/prefetture/brindisi/evidenza/white-list",
        "resource_url": url,
        "sha256": sha,
    }


def check(kind: str, url: str, parser) -> dict[str, object]:
    captures: list[dict[str, object]] = []
    for capture in (1, 2):
        path = Path(f"/tmp/brindisi-{kind}-{capture}.pdf")
        raw = fetch(url, path)
        batch = parser(path, config(f"brindisi-{kind}", "listed" if kind == "listed" else "applicant", url, raw))
        semantic = _semantic_digest(batch.records)
        captures.append(
            {
                "capture": capture,
                "raw_sha256": raw,
                "semantic_sha256": semantic,
                "diagnostics": batch.diagnostics,
                "record_count": len(batch.records),
            }
        )
        print("SMOKE", kind, capture, raw, semantic, json.dumps(batch.diagnostics, ensure_ascii=False, sort_keys=True))
        if kind == "applicants":
            print("APPLICANTS", json.dumps(batch.records, ensure_ascii=False))
    if len({str(item["semantic_sha256"]) for item in captures}) != 1:
        raise RuntimeError(f"{kind}: semantic drift across captures: {captures}")
    return {"kind": kind, "url": url, "captures": captures}


def main() -> None:
    result = {
        "reference_date": "2026-09-08",
        "listed": check("listed", os.environ["LISTED_URL"], parse_brindisi_listed),
        "applicants": check("applicants", os.environ["APPLICANT_URL"], parse_brindisi_applicants),
    }
    out = Path("tmp/brindisi-parser-smoke.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print("CHECKPOINT", out)


if __name__ == "__main__":
    main()
