from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

from white_list_archive.parsers.reggio_calabria_tables import (
    parse_reggio_calabria_applicants,
    parse_reggio_calabria_listed,
)

LANDING = "https://prefettura.interno.gov.it/it/prefetture/reggio-calabria/evidenza/white-list"
SOURCES = {
    "listed": {
        "url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/white-list-foglio-unico-nuove-attivita-24-set-2026.pdf",
        "sha256": "f93a63a89c2c22f9fee27af29654c3dd5e97b58452dde92224b4b2259d3f148f",
        "byte_size": 266878,
        "source_key": "reggio-calabria-listed",
        "population_scope": "listed",
        "parser": parse_reggio_calabria_listed,
        "expected": 532,
    },
    "applicant": {
        "url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-richieste-iscrizioni-white-list-foglio-del-24-set-2026.pdf",
        "sha256": "da60df92f7ffdfc1148ead109395e00ae34e11cb53c01ccc6928bbdff0c71d53",
        "byte_size": 372194,
        "source_key": "reggio-calabria-applicants",
        "population_scope": "applicant",
        "parser": parse_reggio_calabria_applicants,
        "expected": 732,
    },
}


def test_reggio_calabria_exact_archived_editions_parse_end_to_end(tmp_path: Path) -> None:
    for kind, source in SOURCES.items():
        request = urllib.request.Request(source["url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
        assert len(payload) == source["byte_size"]
        assert hashlib.sha256(payload).hexdigest() == source["sha256"]
        path = tmp_path / f"{kind}.pdf"
        path.write_bytes(payload)
        cfg = {
            "source_key": source["source_key"],
            "authority_key": "reggio-calabria",
            "authority_name": "Prefettura di Reggio Calabria",
            "register_key": "reggio-calabria-ordinary",
            "register_name": "White List ordinaria",
            "population_scope": source["population_scope"],
            "reference_date": "2026-09-24",
            "source_page_url": LANDING,
            "resource_url": source["url"],
            "sha256": source["sha256"],
        }
        batch = source["parser"](path, cfg)
        assert len(batch.records) == source["expected"]
        assert batch.diagnostics["public_records"] == source["expected"]
        assert all(record["capture_sha256"] == source["sha256"] for record in batch.records)
