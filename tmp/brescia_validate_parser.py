from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

from white_list_archive.parsers.brescia_openxml import (
    parse_brescia_applicants,
    parse_brescia_listed,
)

LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-ditte-iscritte-10-settembre-2026.xlsx"
APPLICANT_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-ditte-richiedenti-l-iscrizione-10-settembre-2026.xlsx"
LISTED_SHA = "509e6724de2d4d63f403e254236ec2c5b77077d676ee8c17382464d5c9da07a7"
APPLICANT_SHA = "0ab15af0f0f2838aa162177cbc07b91f3d7d80b561ca490611b8ec368c595f34"
SOURCE_PAGE_URL = "https://prefettura.interno.gov.it/it/prefetture/brescia/evidenza/white-list"


def download_twice(url: str, expected_sha: str, destination: Path) -> None:
    hashes: list[str] = []
    first_body: bytes | None = None
    for _ in range(2):
        request = Request(
            url,
            headers={"User-Agent": "italian-anti-mafia-whitelist/parser-validation"},
        )
        with urlopen(request, timeout=90) as response:
            body = response.read()
        digest = hashlib.sha256(body).hexdigest()
        hashes.append(digest)
        if first_body is None:
            first_body = body
    if hashes != [expected_sha, expected_sha]:
        raise SystemExit(f"source SHA drift for {url}: {hashes!r} != {[expected_sha, expected_sha]!r}")
    assert first_body is not None
    destination.write_bytes(first_body)


def cfg(parser: str, source_key: str, scope: str, resource_url: str, sha256: str) -> dict[str, object]:
    return {
        "parser": parser,
        "source_key": source_key,
        "authority_key": "brescia",
        "authority_name": "Prefettura di Brescia",
        "register_key": "brescia-ordinary",
        "register_name": "White List ordinaria",
        "population_scope": scope,
        "reference_date": "2026-09-10",
        "source_page_url": SOURCE_PAGE_URL,
        "resource_url": resource_url,
        "sha256": sha256,
    }


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        listed_path = Path(directory) / "listed.xlsx"
        applicant_path = Path(directory) / "applicants.xlsx"
        download_twice(LISTED_URL, LISTED_SHA, listed_path)
        download_twice(APPLICANT_URL, APPLICANT_SHA, applicant_path)

        listed = parse_brescia_listed(
            listed_path,
            cfg("brescia_listed", "brescia-listed", "listed", LISTED_URL, LISTED_SHA),
        )
        applicants = parse_brescia_applicants(
            applicant_path,
            cfg("brescia_applicants", "brescia-applicants", "applicant", APPLICANT_URL, APPLICANT_SHA),
        )

        assert listed.diagnostics["sector_rows"] == 3380, listed.diagnostics
        assert listed.diagnostics["public_records"] == 2071, listed.diagnostics
        assert listed.diagnostics["status_counts"] == {
            "listed": 1859,
            "renewal_update_in_progress": 212,
        }, listed.diagnostics
        assert listed.diagnostics["peer_resolved_date_rows"] == 2, listed.diagnostics
        assert listed.diagnostics["reviewed_structural_shift_rows"] == 1, listed.diagnostics

        assert applicants.diagnostics["source_rows"] == 1264, applicants.diagnostics
        assert applicants.diagnostics["public_records"] == 1263, applicants.diagnostics
        assert applicants.diagnostics["status_counts"] == {"pending": 1263}, applicants.diagnostics
        assert applicants.diagnostics["missing_application_dates"] == 841, applicants.diagnostics
        assert applicants.diagnostics["malformed_application_dates"] == 1, applicants.diagnostics
        assert applicants.diagnostics["duplicate_exact_groups"] == 1, applicants.diagnostics
        assert len(listed.records) + len(applicants.records) == 3334

        print(
            json.dumps(
                {
                    "listed": listed.diagnostics,
                    "applicants": applicants.diagnostics,
                    "total_records": len(listed.records) + len(applicants.records),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
