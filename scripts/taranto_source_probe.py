from __future__ import annotations

import hashlib
import json
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

from white_list_archive.parsers.taranto_html import PARSERS

SOURCES = {
    "listed": {
        "parser": "taranto_html_listed",
        "source_key": "taranto-listed",
        "population_scope": "listed",
        "url": "https://prefettura.interno.gov.it/it/prefetture/taranto/white-list-elenco-imprese-iscritte",
    },
    "applicants": {
        "parser": "taranto_html_applicants",
        "source_key": "taranto-applicants",
        "population_scope": "applicant",
        "url": "https://prefettura.interno.gov.it/it/prefetture/taranto/elenco-imprese-richiedenti-liscrizione-nella-white-list",
    },
}
USER_AGENT = "italian-anti-mafia-whitelist/0.1 (+Taranto source-boundary audit)"


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*", "Cache-Control": "no-cache"})
    with urlopen(request, timeout=60) as response:  # noqa: S310 - fixed official pages
        return response.read()


def semantic_digest(records: list[dict[str, object]]) -> str:
    ignored = {"capture_sha256", "parser_name", "parser_version"}
    projected = [{key: value for key, value in record.items() if key not in ignored} for record in records]
    payload = json.dumps(projected, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def probe(kind: str) -> dict[str, object]:
    source = SOURCES[kind]
    first = fetch(source["url"])
    time.sleep(1)
    second = fetch(source["url"])
    first_sha = hashlib.sha256(first).hexdigest()
    second_sha = hashlib.sha256(second).hexdigest()
    cfg = {
        "source_key": source["source_key"],
        "authority_key": "taranto",
        "authority_name": "Prefettura di Taranto",
        "register_key": "taranto-ordinary",
        "register_name": "White List ordinaria",
        "population_scope": source["population_scope"],
        "reference_date": "2026-09-07",
        "source_page_url": source["url"],
        "resource_url": source["url"],
        "sha256": first_sha,
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"taranto-{kind}.html"
        path.write_bytes(first)
        batch = PARSERS[source["parser"]](path, cfg)
    return {
        "kind": kind,
        "url": source["url"],
        "first_bytes": len(first),
        "second_bytes": len(second),
        "first_sha256": first_sha,
        "second_sha256": second_sha,
        "byte_identical_repeat_fetch": first == second,
        "semantic_sha256": semantic_digest(batch.records),
        "diagnostics": batch.diagnostics,
        "first_record": batch.records[0],
        "last_record": batch.records[-1],
    }


if __name__ == "__main__":
    print(json.dumps({kind: probe(kind) for kind in ("listed", "applicants")}, ensure_ascii=False, indent=2, sort_keys=True))
