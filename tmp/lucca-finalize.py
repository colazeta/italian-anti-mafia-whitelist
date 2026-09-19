from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
LANDING = "https://prefettura.interno.gov.it/it/prefetture/lucca/elenco-imprese-iscritte-e-richiedenti"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-imprese-iscritte-agg-l-40-del-2020-al-11-settembre-2026.pdf"
APPLICANTS_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-imprese-richiedenti-agg-l-40-del-2020-al-08-settembre-2026.pdf"
LISTED_SHA = "d5a0f11c68a0a3dfb01d10b30f35130c7899795bb46e0239226ad5ea575b5c67"
APPLICANTS_SHA = "fd9cdc163e09c411ce5fd1f716d85811a15503f3527ac0f5abdaec909de4f084"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, got {count}: {old!r}")
    return text.replace(old, new)


def verify_sources() -> None:
    sources = {
        "listed": (LISTED_URL, LISTED_SHA, 532170),
        "applicants": (APPLICANTS_URL, APPLICANTS_SHA, 179370),
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; italian-anti-mafia-whitelist source verification)",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    for key, (url, expected_sha, expected_bytes) in sources.items():
        captures: list[tuple[int, str]] = []
        for _ in range(2):
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            body = response.content
            observed = (len(body), hashlib.sha256(body).hexdigest())
            captures.append(observed)
            if observed != (expected_bytes, expected_sha):
                raise RuntimeError(f"{key}: official source drift: {observed!r}")
            time.sleep(1)
        if captures[0] != captures[1]:
            raise RuntimeError(f"{key}: independent captures differ: {captures!r}")
        print(f"verified {key}: bytes={captures[0][0]} sha256={captures[0][1]}")


def clean_parser_public_fields() -> None:
    path = ROOT / "src/white_list_archive/parsers/lucca_tables.py"
    text = path.read_text(encoding="utf-8")
    anchor = '                "identifier_raw_source": identifier_raw,\n'
    if text.count(anchor) != 2:
        raise RuntimeError(f"Lucca identifier source-field anchor drift: {text.count(anchor)}")
    text = text.replace(anchor, "")
    expiry = '                "expiry_cell_raw": expiry_raw,\n'
    if text.count(expiry) != 1:
        raise RuntimeError(f"Lucca expiry-cell source-field anchor drift: {text.count(expiry)}")
    text = text.replace(expiry, "")
    path.write_text(text, encoding="utf-8")


def update_publication_config() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if any(source.get("authority_key") == "lucca" for source in cfg["sources"]):
        raise RuntimeError("Lucca already present in publication config")
    cfg["sources"].extend(
        [
            {
                "authority_key": "lucca",
                "authority_name": "Prefettura di Lucca",
                "register_key": "lucca-ordinary",
                "register_name": "White List ordinaria",
                "reference_date": "2026-09-11",
                "source_page_url": LANDING,
                "last_source_update": "2026-09-15",
                "last_source_update_basis": "official landing-page 'Ultimo aggiornamento' 15 September 2026, 12:12; source reference_date follows the listed attachment marker and is not promoted to a company decision/legal-effect date",
                "approval_mode": "raw_sha256",
                "source_key": "lucca-listed",
                "parser": "lucca_listed",
                "population_scope": "listed",
                "resource_url": LISTED_URL,
                "sha256": LISTED_SHA,
                "expected_source_rows": 331,
                "notes": "Dedicated official listed PDF positively exposed by the current landing page. 331 table rows yield 229 listed and 102 renewal/update-in-progress observations. Structured identifier coverage is 324/331; seven source rows remain raw-only. No malformed identifier or missing expiry value is repaired inferentially.",
            },
            {
                "authority_key": "lucca",
                "authority_name": "Prefettura di Lucca",
                "register_key": "lucca-ordinary",
                "register_name": "White List ordinaria",
                "reference_date": "2026-09-08",
                "source_page_url": LANDING,
                "last_source_update": "2026-09-15",
                "last_source_update_basis": "official landing-page 'Ultimo aggiornamento' 15 September 2026, 12:12; source reference_date follows the applicant attachment marker and is not promoted to a company decision/legal-effect date",
                "approval_mode": "raw_sha256",
                "source_key": "lucca-applicants",
                "parser": "lucca_applicants",
                "population_scope": "applicant",
                "resource_url": APPLICANTS_URL,
                "sha256": APPLICANTS_SHA,
                "expected_source_rows": 71,
                "notes": "Dedicated official applicant PDF positively exposed by the current landing page. All 71 table rows are pending observations and structured identifier coverage is 69/71; the two malformed numeric identifiers remain raw-only. Applicant coverage is positive source evidence, never inferred from absence.",
            },
        ]
    )
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_csv_registries() -> None:
    pages_path = ROOT / "data/source_registry/verified_primary_pages.csv"
    with pages_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    if fields is None:
        raise RuntimeError("verified primary pages header missing")
    if any(row["authority_key"] == "lucca" for row in rows):
        raise RuntimeError("Lucca already in verified primary pages")
    rows.append(
        {
            "authority_key": "lucca",
            "landing_url": LANDING,
            "verification_date": "2026-09-19",
            "verification_status": "verified",
        }
    )
    rows.sort(key=lambda row: row["authority_key"])
    with pages_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    series_path = ROOT / "data/source_registry/source_series_inventory.csv"
    with series_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        series = list(reader)
    if fields is None:
        raise RuntimeError("source series header missing")
    if any(row["authority_key"] == "lucca" for row in series):
        raise RuntimeError("Lucca already in source series inventory")
    series.extend(
        [
            {
                "source_series_key": "lucca-applicants",
                "authority_key": "lucca",
                "regime_code": "WL-REGIME-L190-2012",
                "population_scope": "applicant",
                "sector_scope": "all",
                "publication_model": "periodic_attachment",
                "series_url": LANDING,
                "resource_resolution_status": "landing_page_resolved",
                "verified_date": "2026-09-19",
                "notes": "Current official Lucca page directly re-verified 19 September 2026 and positively exposes the dedicated applicant PDF marked Aggiornato al 08/09/2026. Exact bytes, denominator and conservative anomaly handling are documented in docs/sources/lucca-operational-check-2026-09-19.md.",
            },
            {
                "source_series_key": "lucca-listed",
                "authority_key": "lucca",
                "regime_code": "WL-REGIME-L190-2012",
                "population_scope": "listed",
                "sector_scope": "all",
                "publication_model": "periodic_attachment",
                "series_url": LANDING,
                "resource_resolution_status": "landing_page_resolved",
                "verified_date": "2026-09-19",
                "notes": "Current official Lucca page directly re-verified 19 September 2026 and positively exposes the dedicated listed PDF marked Aggiornato al 11/09/2026. Exact bytes, denominator and conservative status/identifier handling are documented in docs/sources/lucca-operational-check-2026-09-19.md.",
            },
        ]
    )
    series.sort(key=lambda row: row["source_series_key"])
    with series_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(series)


def update_catalog() -> None:
    path = ROOT / "data/catalog.csv"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,60,false",
        "verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,61,false",
        "verified page catalogue count",
    )
    text = replace_once(
        text,
        "source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,118,false",
        "source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,120,false",
        "source series catalogue count",
    )
    path.write_text(text, encoding="utf-8")


def update_coverage() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = [item for item in data["authorities"] if item["authority_key"] == "lucca"]
    if len(rows) != 1:
        raise RuntimeError(f"Lucca national coverage row cardinality drift: {len(rows)}")
    item = rows[0]
    item.update(
        {
            "official_landing_page": LANDING,
            "source_verified": True,
            "current_edition_identified": True,
            "capture_implemented": True,
            "parser_implemented": True,
            "parser_validated": True,
            "company_observations_loaded": True,
            "observation_layer": "public_source_observations",
            "canonical_integration_validated": False,
            "public_export_enabled": True,
            "durable_evidence_verified": False,
            "population_scopes_complete": True,
            "latest_source_reference_date": "2026-09-11",
            "last_successful_investigation_on": "2026-09-19",
            "coverage_status": "VALIDATED",
            "terminal_reason": None,
            "unresolved_issue": [
                "Canonical hosted-database integration and independent durable-evidence verification remain separate infrastructure gates; the 15 September landing update timestamp is publication-surface provenance and is not promoted to a company decision or legal-effect date."
            ],
            "actionable_issue": False,
            "completion_evidence": [
                "docs/sources/lucca-operational-check-2026-09-19.md",
                "src/white_list_archive/parsers/lucca_tables.py",
                "tests/test_lucca_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [LISTED_SHA, APPLICANTS_SHA],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                "docs/sources/lucca-operational-check-2026-09-19.md",
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_public_builder() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    text = path.read_text(encoding="utf-8")
    anchor = "from white_list_archive.parsers.imperia_sources import PARSERS as IMPERIA_PARSERS\n"
    text = replace_once(
        text,
        anchor,
        anchor + "from white_list_archive.parsers.lucca_tables import PARSERS as LUCCA_PARSERS\n",
        "public builder parser import",
    )
    anchor = '        or IMPERIA_PARSERS.get(cfg["parser"])\n'
    text = replace_once(
        text,
        anchor,
        anchor + '        or LUCCA_PARSERS.get(cfg["parser"])\n',
        "public builder parser dispatch",
    )
    path.write_text(text, encoding="utf-8")


def update_public_workflow() -> None:
    path = ROOT / ".github/workflows/public-pages.yml"
    text = path.read_text(encoding="utf-8")
    anchor = "      - 'src/white_list_archive/parsers/imperia_sources.py'\n"
    text = replace_once(text, anchor, anchor + "      - 'src/white_list_archive/parsers/lucca_tables.py'\n", "public workflow parser path")
    for old, new, label in [
        ("assert reg['meta']['record_count'] == 64865", "assert reg['meta']['record_count'] == 65267", "public record total"),
        (",'grosseto','imperia'}", ",'grosseto','imperia','lucca'}", "public authority set"),
        (",'grosseto-ordinary','imperia-ordinary'\n", ",'grosseto-ordinary','imperia-ordinary','lucca-ordinary'\n", "public register set"),
        ("assert reg['meta']['authority_count'] == 60", "assert reg['meta']['authority_count'] == 61", "public authority total"),
        ("assert reg['meta']['register_count'] == 62", "assert reg['meta']['register_count'] == 63", "public register total"),
        ("assert pref['meta']['published_count'] == 60", "assert pref['meta']['published_count'] == 61", "public published total"),
        ("assert pref['meta']['mapped_count'] == 60", "assert pref['meta']['mapped_count'] == 61", "public mapped total"),
    ]:
        text = replace_once(text, old, new, label)
    anchor = "          assert len({r['record_locator'] for r in imperia_records}) == 273\n"
    block = """          lucca = [x for x in pref['prefectures'] if x['authority_key'] == 'lucca']
          assert len(lucca) == 1 and lucca[0]['mapped'] and lucca[0]['published'] and lucca[0]['series_count'] == 2
          lucca_records = [r for r in reg['records'] if r['authority_key'] == 'lucca']
          assert len(lucca_records) == 402
          assert sum(r['source_key'] == 'lucca-listed' for r in lucca_records) == 331
          assert sum(r['source_key'] == 'lucca-applicants' for r in lucca_records) == 71
          assert sum(r['source_status'] == 'listed' for r in lucca_records) == 229
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in lucca_records) == 102
          assert sum(r['source_status'] == 'pending' for r in lucca_records) == 71
          assert sum(bool(r['identifiers']) for r in lucca_records) == 393
          assert len({r['record_locator'] for r in lucca_records}) == 402
"""
    text = replace_once(text, anchor, anchor + block, "public Lucca assertion anchor")
    path.write_text(text, encoding="utf-8")


def update_browser_test() -> None:
    path = ROOT / "tests/public_portal_browser.cjs"
    text = path.read_text(encoding="utf-8")
    anchor = "      assert.ok(labels.includes('White List ordinaria · Prefettura di Imperia'));\n"
    text = replace_once(text, anchor, anchor + "      assert.ok(labels.includes('White List ordinaria · Prefettura di Lucca'));\n", "browser register label")
    text = replace_once(text, "assert.equal(stats.total,64865);", "assert.equal(stats.total,65267);", "browser total")
    text = replace_once(
        text,
        ",'grosseto','imperia'].includes(r.authority_key)",
        ",'grosseto','imperia','lucca'].includes(r.authority_key)",
        "browser baseline authority exclusion",
    )
    anchor = "      assert.equal(imperia.filter(r=>r.identifiers.length>0).length,257);\n"
    block = """      const lucca=registry.records.filter(r=>r.authority_key==='lucca');
      assert.equal(lucca.length,402);
      assert.equal(lucca.filter(r=>r.source_key==='lucca-listed').length,331);
      assert.equal(lucca.filter(r=>r.source_key==='lucca-applicants').length,71);
      assert.deepEqual(statusCounts(lucca),{listed:229,pending:71,renewal_update_in_progress:102});
      assert.equal(new Set(lucca.map(r=>r.record_locator)).size,402);
      assert.equal(lucca.filter(r=>r.identifiers.length>0).length,393);
"""
    text = replace_once(text, anchor, anchor + block, "browser Lucca assertion anchor")
    path.write_text(text, encoding="utf-8")


def update_registry_tests() -> None:
    path = ROOT / "tests/test_source_registry.py"
    text = replace_once(path.read_text(encoding="utf-8"), "assert len(pages) == 60", "assert len(pages) == 61", "source registry count")
    path.write_text(text, encoding="utf-8")

    path = ROOT / "tests/test_source_population_coverage.py"
    text = path.read_text(encoding="utf-8")
    for old, new, label in [
        ('assert report["verified_authority_count"] == 60', 'assert report["verified_authority_count"] == 61', "verified authority count"),
        ('assert report["register_scope_count"] == 62', 'assert report["register_scope_count"] == 63', "register scope count"),
        ('assert report["complete_register_scope_count"] == 62', 'assert report["complete_register_scope_count"] == 63', "complete scope count"),
        ('        "imperia",\n    ):', '        "imperia",\n        "lucca",\n    ):', "recent resolved authority tuple"),
    ]:
        text = replace_once(text, old, new, label)
    path.write_text(text, encoding="utf-8")


def remove_transactional_files() -> None:
    for rel in [
        ".github/workflows/lucca-source-probe.yml",
        ".github/workflows/lucca-parser-validate.yml",
        ".github/workflows/lucca-integration-finalizer.yml",
        ".github/workflows/lucca-integration-finalizer-v2.yml",
        "tmp/lucca-finalize.py",
    ]:
        path = ROOT / rel
        if path.exists():
            path.unlink()


def main() -> None:
    verify_sources()
    clean_parser_public_fields()
    update_publication_config()
    update_csv_registries()
    update_catalog()
    update_coverage()
    update_public_builder()
    update_public_workflow()
    update_browser_test()
    update_registry_tests()
    remove_transactional_files()
    print("Lucca permanent integration materialised; transactional files removed")


if __name__ == "__main__":
    main()
