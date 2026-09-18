from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}: {old!r}")
    return text.replace(old, new, 1)


def update_publication_config() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    keys = {item["source_key"] for item in data["sources"]}
    if {"taranto-listed", "taranto-applicants"} & keys:
        raise RuntimeError("Taranto publication sources already present; refusing duplicate finalisation")
    data["sources"].extend(
        [
            {
                "source_key": "taranto-listed",
                "parser": "taranto_html_listed",
                "authority_key": "taranto",
                "authority_name": "Prefettura di Taranto",
                "register_key": "taranto-ordinary",
                "register_name": "White List ordinaria",
                "population_scope": "listed",
                "reference_date": "2026-09-18",
                "source_page_url": "https://prefettura.interno.gov.it/it/prefetture/taranto/white-list-elenco-imprese-iscritte",
                "resource_url": "https://prefettura.interno.gov.it/it/prefetture/taranto/white-list-elenco-imprese-iscritte",
                "sha256": "545d6db44a8f68ec1e9ef460a4a8129e64d77385bfab318f8d050051219643c9",
                "semantic_sha256": "27211daaa4734c29bc0f48d9a86e229d04671a150fcad997b8045d997e6bab92",
                "approval_mode": "semantic_sha256",
                "expected_source_rows": 388,
                "last_source_update": "2026-09-18",
                "last_source_update_basis": "current mutable official HTML table captured and independently revalidated 18 September 2026; date is an observation/reference boundary only and is not an inferred company event or legal-effect date",
                "notes": "Mutable official registered-company HTML table. Repeated independent no-cache captures were byte-identical at 150,817 bytes. The fail-closed parser yields exactly 388 observations: 212 listed and 176 renewal/update in progress. Structured identifier coverage is 381/388 with seven raw-only identifiers; eight rows retain at least one malformed source date without repair or inference. Publication is approved against the full parsed semantic digest while raw capture SHA-256 remains observation provenance. Exact evidence is documented in docs/sources/taranto-operational-check-2026-09-18.md.",
            },
            {
                "source_key": "taranto-applicants",
                "parser": "taranto_html_applicants",
                "authority_key": "taranto",
                "authority_name": "Prefettura di Taranto",
                "register_key": "taranto-ordinary",
                "register_name": "White List ordinaria",
                "population_scope": "applicant",
                "reference_date": "2026-09-18",
                "source_page_url": "https://prefettura.interno.gov.it/it/prefetture/taranto/elenco-imprese-richiedenti-liscrizione-nella-white-list",
                "resource_url": "https://prefettura.interno.gov.it/it/prefetture/taranto/elenco-imprese-richiedenti-liscrizione-nella-white-list",
                "sha256": "ade85a5326dc8aa99c4cc2695bad87aee897964cd4c10c59b665793ec3d900f6",
                "semantic_sha256": "b6bfcea34e1ff19a79164b4b0b13acbd55a8985c2cec66048d719e6704155982",
                "approval_mode": "semantic_sha256",
                "expected_source_rows": 212,
                "last_source_update": "2026-09-18",
                "last_source_update_basis": "current mutable official HTML table captured and independently revalidated 18 September 2026; date is an observation/reference boundary only and is not an inferred company event or legal-effect date",
                "notes": "Mutable official applicant HTML table. Repeated independent no-cache captures were byte-identical at 107,423 bytes. The fail-closed parser yields exactly 212 pending observations. Structured identifier coverage is 211/212 with one raw-only identifier; no malformed application dates were observed. Publication is approved against the full parsed semantic digest while raw capture SHA-256 remains observation provenance. Exact evidence is documented in docs/sources/taranto-operational-check-2026-09-18.md.",
            },
        ]
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_public_dispatch() -> None:
    path = "src/white_list_archive/publishing/public_national_registry.py"
    text = read(path)
    text = replace_once(
        text,
        "from white_list_archive.parsers.firenze_sources import parse_firenze_applicants, parse_firenze_listed\n",
        "from white_list_archive.parsers.firenze_sources import parse_firenze_applicants, parse_firenze_listed\nfrom white_list_archive.parsers.taranto_html import PARSERS as TARANTO_PARSERS\n",
        label="Taranto parser import",
    )
    text = replace_once(
        text,
        "        or FIRENZE_PARSERS.get(cfg[\"parser\"])\n    )\n",
        "        or FIRENZE_PARSERS.get(cfg[\"parser\"])\n        or TARANTO_PARSERS.get(cfg[\"parser\"])\n    )\n",
        label="Taranto parser dispatch",
    )
    write(path, text)


def update_verified_pages() -> None:
    path = ROOT / "data/source_registry/verified_primary_pages.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    if any(row["authority_key"] == "taranto" for row in rows):
        raise RuntimeError("Taranto verified-primary page already exists")
    rows.append(
        {
            "authority_key": "taranto",
            "landing_url": "https://prefettura.interno.gov.it/it/prefetture/taranto/white-list-elenco-imprese-iscritte",
            "verification_date": "2026-09-18",
            "verification_status": "verified",
        }
    )
    rows.sort(key=lambda row: row["authority_key"])
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["authority_key", "landing_url", "verification_date", "verification_status"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def update_source_series() -> None:
    path = ROOT / "data/source_registry/source_series_inventory.csv"
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if any(row["authority_key"] == "taranto" for row in rows):
        raise RuntimeError("Taranto source series already exist")
    rows.extend(
        [
            {
                "source_series_key": "taranto-applicants",
                "authority_key": "taranto",
                "regime_code": "WL-REGIME-L190-2012",
                "population_scope": "applicant",
                "sector_scope": "all",
                "publication_model": "html_table",
                "series_url": "https://prefettura.interno.gov.it/it/prefetture/taranto/elenco-imprese-richiedenti-liscrizione-nella-white-list",
                "resource_resolution_status": "direct_series_page_resolved",
                "verified_date": "2026-09-18",
                "notes": "Current dedicated official applicant HTML table directly verified 18 September 2026. Repeated independent captures are byte-identical and the table yields exactly 212 pending observations. Exact semantic approval, identifier coverage and date handling are documented in docs/sources/taranto-operational-check-2026-09-18.md.",
            },
            {
                "source_series_key": "taranto-listed",
                "authority_key": "taranto",
                "regime_code": "WL-REGIME-L190-2012",
                "population_scope": "listed",
                "sector_scope": "all",
                "publication_model": "html_table",
                "series_url": "https://prefettura.interno.gov.it/it/prefetture/taranto/white-list-elenco-imprese-iscritte",
                "resource_resolution_status": "direct_series_page_resolved",
                "verified_date": "2026-09-18",
                "notes": "Current dedicated official registered-company HTML table directly verified 18 September 2026. Repeated independent captures are byte-identical and the table yields exactly 388 observations: 212 listed and 176 renewal/update in progress. Exact semantic approval, identifier anomalies and malformed-date handling are documented in docs/sources/taranto-operational-check-2026-09-18.md.",
            },
        ]
    )
    rows.sort(key=lambda row: row["source_series_key"])
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def update_catalog_and_tests() -> None:
    text = read("data/catalog.csv")
    text = replace_once(text, "verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,50,", "verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,51,", label="catalog verified page count")
    text = replace_once(text, "source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,99,", "source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,101,", label="catalog source series count")
    write("data/catalog.csv", text)

    text = read("tests/test_source_registry.py")
    text = replace_once(text, "    assert len(pages) == 50\n", "    assert len(pages) == 51\n", label="verified pages test")
    write("tests/test_source_registry.py", text)

    text = read("tests/test_source_population_coverage.py")
    text = replace_once(text, "    assert report[\"verified_authority_count\"] == 50\n", "    assert report[\"verified_authority_count\"] == 51\n", label="verified authority count")
    text = replace_once(text, "    assert report[\"register_scope_count\"] == 52\n", "    assert report[\"register_scope_count\"] == 53\n", label="register scope count")
    text = replace_once(text, "    assert report[\"complete_register_scope_count\"] == 52\n", "    assert report[\"complete_register_scope_count\"] == 53\n", label="complete register scope count")
    write("tests/test_source_population_coverage.py", text)


def update_monitoring() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("authorities") or data.get("prefectures") or data.get("coverage")
    if not isinstance(entries, list):
        raise RuntimeError("national coverage authority list not found")
    matches = [item for item in entries if item.get("authority_key") == "taranto"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one Taranto monitoring entry, found {len(matches)}")
    item = matches[0]
    item.update(
        {
            "official_landing_page": "https://prefettura.interno.gov.it/it/prefetture/taranto/white-list-elenco-imprese-iscritte",
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
            "latest_source_reference_date": "2026-09-18",
            "last_successful_source_check_at": "2026-09-18T04:49:45Z",
            "last_attempted_source_check_at": "2026-09-18T04:49:45Z",
            "last_successful_investigation_on": "2026-09-18",
            "monitoring_status": "CURRENT",
            "unresolved_issue": ["Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."],
            "actionable_issue": False,
            "coverage_status": "VALIDATED",
            "terminal_reason": None,
            "completion_evidence": [
                "docs/sources/taranto-operational-check-2026-09-18.md",
                "src/white_list_archive/parsers/taranto_html.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [
                "545d6db44a8f68ec1e9ef460a4a8129e64d77385bfab318f8d050051219643c9",
                "ade85a5326dc8aa99c4cc2695bad87aee897964cd4c10c59b665793ec3d900f6",
            ],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                "docs/sources/taranto-operational-check-2026-09-18.md",
            ],
            "last_completed_coverage_stage": "VALIDATED",
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_public_workflow() -> None:
    path = ".github/workflows/public-pages.yml"
    text = read(path)
    text = replace_once(text, "      - 'src/white_list_archive/parsers/firenze_sources.py'\n", "      - 'src/white_list_archive/parsers/firenze_sources.py'\n      - 'src/white_list_archive/parsers/taranto_html.py'\n", label="workflow parser path")
    text = replace_once(text, "          assert reg['meta']['record_count'] == 59042\n", "          assert reg['meta']['record_count'] == 59642\n", label="workflow record count")
    text = replace_once(text, "'como','firenze'}\n", "'como','firenze','taranto'}\n", label="workflow authority set")
    text = replace_once(text, "'como-ordinary','firenze-ordinary'\n", "'como-ordinary','firenze-ordinary','taranto-ordinary'\n", label="workflow register set")
    text = replace_once(text, "          assert reg['meta']['authority_count'] == 50\n", "          assert reg['meta']['authority_count'] == 51\n", label="workflow authority count")
    text = replace_once(text, "          assert reg['meta']['register_count'] == 52\n", "          assert reg['meta']['register_count'] == 53\n", label="workflow register count")
    text = replace_once(text, "          assert pref['meta']['published_count'] == 50\n", "          assert pref['meta']['published_count'] == 51\n", label="workflow published count")
    text = replace_once(text, "          assert pref['meta']['mapped_count'] == 50\n", "          assert pref['meta']['mapped_count'] == 51\n", label="workflow mapped count")
    marker = "          assert sum(not bool(r['registered_office']) for r in firenze_applicants) == 2\n"
    taranto = """          taranto = [x for x in pref['prefectures'] if x['authority_key'] == 'taranto']
          assert len(taranto) == 1 and taranto[0]['mapped'] and taranto[0]['published'] and taranto[0]['series_count'] == 2
          taranto_records = [r for r in reg['records'] if r['authority_key'] == 'taranto']
          assert len(taranto_records) == 600
          assert sum(r['source_key'] == 'taranto-listed' for r in taranto_records) == 388
          assert sum(r['source_key'] == 'taranto-applicants' for r in taranto_records) == 212
          assert sum(r['source_status'] == 'listed' for r in taranto_records) == 212
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in taranto_records) == 176
          assert sum(r['source_status'] == 'pending' for r in taranto_records) == 212
          assert len({r['record_locator'] for r in taranto_records}) == 600
          assert sum(bool(r['identifiers']) for r in taranto_records) == 592
          assert sum(bool(r['identifier_field_raw']) and not r['identifiers'] for r in taranto_records) == 8
          assert sum(bool(r.get('source_fields', {}).get('malformed_date_pairs')) for r in taranto_records if r['source_key'] == 'taranto-listed') == 8
"""
    text = replace_once(text, marker, marker + taranto, label="workflow Taranto assertions")
    write(path, text)


def update_browser_test() -> None:
    path = "tests/public_portal_browser.cjs"
    text = read(path)
    text = replace_once(text, "      assert.ok(labels.includes('White List ordinaria · Prefettura di Firenze'));\n", "      assert.ok(labels.includes('White List ordinaria · Prefettura di Firenze'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Taranto'));\n", label="browser Taranto label")
    text = replace_once(text, "      assert.equal(stats.total,59042);\n", "      assert.equal(stats.total,59642);\n", label="browser total")
    text = replace_once(text, "'como','firenze'].includes(r.authority_key));\n", "'como','firenze','taranto'].includes(r.authority_key));\n", label="browser authority exclusion")
    marker = "      assert.equal(firenze.filter(r=>r.source_key==='firenze-applicants'&&!r.registered_office).length,2);\n"
    taranto = """      const taranto=registry.records.filter(r=>r.authority_key==='taranto');
      assert.equal(taranto.length,600);
      assert.equal(taranto.filter(r=>r.source_key==='taranto-listed').length,388);
      assert.equal(taranto.filter(r=>r.source_key==='taranto-applicants').length,212);
      assert.deepEqual(statusCounts(taranto),{listed:212,pending:212,renewal_update_in_progress:176});
      assert.equal(new Set(taranto.map(r=>r.record_locator)).size,600);
      assert.equal(taranto.filter(r=>r.identifiers.length>0).length,592);
      assert.equal(taranto.filter(r=>r.identifier_field_raw&&r.identifiers.length===0).length,8);
      assert.equal(taranto.filter(r=>r.source_key==='taranto-listed'&&r.source_fields.malformed_date_pairs.length>0).length,8);
"""
    text = replace_once(text, marker, marker + taranto, label="browser Taranto assertions")
    write(path, text)


def write_operational_note() -> None:
    path = ROOT / "docs/sources/taranto-operational-check-2026-09-18.md"
    if path.exists():
        raise RuntimeError("Taranto operational note already exists")
    path.write_text(
        """# Taranto operational source check — 18 September 2026

## Scope

This note freezes the evidence boundary used to integrate the current official Taranto White List populations into the public national registry. It concerns source-backed observations only and does not infer legal effect from absence, malformed source fields, or a status transition.

## Official sources

- Listed population: https://prefettura.interno.gov.it/it/prefetture/taranto/white-list-elenco-imprese-iscritte
- Applicant population: https://prefettura.interno.gov.it/it/prefetture/taranto/elenco-imprese-richiedenti-liscrizione-nella-white-list

Both resources are mutable official HTML pages. Repeated independent no-cache captures were used before approval. Publication therefore fails closed on the complete parsed semantic digest; the raw capture SHA-256 is retained as provenance rather than used as the approval boundary.

## Registered-company table

Repeated captures were byte-identical at 150,817 bytes with raw SHA-256 `545d6db44a8f68ec1e9ef460a4a8129e64d77385bfab318f8d050051219643c9`. The parser yields exactly 388 observations: 212 `listed` and 176 `renewal_update_in_progress`. Structured identifier coverage is 381/388; seven source identifier values remain raw-only. Eight rows contain at least one malformed source date. Those strings are retained in provenance and are not repaired by inference. The approved contract-safe semantic SHA-256 is `27211daaa4734c29bc0f48d9a86e229d04671a150fcad997b8045d997e6bab92`.

The parser accepts only the explicitly observed note semantics: blank note -> `listed`; `In fase di rinnovo` and `In fase di aggiornamento` -> `renewal_update_in_progress`. A new status lexeme is a fail-closed error.

## Applicant table

Repeated captures were byte-identical at 107,423 bytes with raw SHA-256 `ade85a5326dc8aa99c4cc2695bad87aee897964cd4c10c59b665793ec3d900f6`. The parser yields exactly 212 pending observations. Structured identifier coverage is 211/212; one source identifier remains raw-only. No malformed application dates were observed in the approved boundary. The approved contract-safe semantic SHA-256 is `b6bfcea34e1ff19a79164b4b0b13acbd55a8985c2cec66048d719e6704155982`.

## Publication boundary

The combined Taranto publication population is 600 source-backed observations: 212 listed, 176 renewal/update in progress, and 212 pending. There are 592 observations with a structured identifier and eight with a non-empty raw identifier that deliberately does not pass strict identifier normalisation. All 600 record locators must remain unique.

At the pre-Taranto live national baseline of 59,042 records / 50 published Prefectures / 52 registers, successful integration produces the candidate boundary 59,642 records / 51 published Prefectures / 53 registers / 51 mapped Prefectures. Canonical hosted-database integration and durable-evidence governance remain separate from this public-source validation boundary.
""",
        encoding="utf-8",
    )


def main() -> None:
    update_publication_config()
    update_public_dispatch()
    update_verified_pages()
    update_source_series()
    update_catalog_and_tests()
    update_monitoring()
    update_public_workflow()
    update_browser_test()
    write_operational_note()


if __name__ == "__main__":
    main()
