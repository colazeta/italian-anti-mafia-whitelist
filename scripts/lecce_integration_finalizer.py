from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = "https://prefettura.interno.gov.it/it/prefetture/lecce/evidenza/white-list"
LISTED = "https://prefettura.interno.gov.it/sites/default/files/49/2026-09/elenco-white-list-per-categoria-aggiornato-9-settembre-2026.pdf"
APPLICANTS = "https://prefettura.interno.gov.it/sites/default/files/49/2026-09/elenco-richiedenti-iscrizione-aggiornato-9-settembre-2026.pdf"
LISTED_SHA = "acbe7b735107d48735bc8d01902fc73d49f00e6d8d6ef11dc0c1f9dfd344765d"
APPLICANTS_SHA = "9d94226065ea80c35a140da93c74ed404ceea79018a725f755768b1a55a30124"
DOC = "docs/sources/lecce-operational-check-2026-09-18.md"


def must_replace(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Required integration anchor missing in {path}: {old[:100]!r}")
    if new in text:
        return
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def update_publication() -> None:
    p = ROOT / "data/publication/multi_prefecture_pilot.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    if any(x["source_key"].startswith("lecce-") for x in data["sources"]):
        raise RuntimeError("Lecce publication sources already present")
    common = {
        "authority_key": "lecce",
        "authority_name": "Prefettura di Lecce",
        "register_key": "lecce-ordinary",
        "register_name": "White List ordinaria",
        "reference_date": "2026-09-09",
        "source_page_url": LANDING,
        "last_source_update": "2026-09-09",
        "last_source_update_basis": "edition date printed on every current official PDF page and stated by the official landing-page attachment labels; independently verified 18 September 2026; used only as a source-edition/reference boundary",
        "approval_mode": "raw_sha256",
    }
    data["sources"].extend([
        {
            **common,
            "source_key": "lecce-listed",
            "parser": "lecce_listed",
            "population_scope": "listed",
            "resource_url": LISTED,
            "sha256": LISTED_SHA,
            "expected_sector_rows": 1783,
            "expected_source_rows": 825,
            "notes": "Current 78-page official listed-side PDF. Independent captures are byte-identical. The fail-closed parser groups 1,783 statutory-section rows into 825 exact source-backed observations: 582 listed and 243 renewal/update in progress. Structured identifier coverage is 804/825; 20 raw-only identifiers, one blank identifier and six malformed source-date rows are retained without repair or inference. Exact evidence is documented in docs/sources/lecce-operational-check-2026-09-18.md.",
        },
        {
            **common,
            "source_key": "lecce-applicants",
            "parser": "lecce_applicants",
            "population_scope": "applicant",
            "resource_url": APPLICANTS,
            "sha256": APPLICANTS_SHA,
            "expected_source_rows": 90,
            "notes": "Current 10-page official applicant PDF. Independent captures are byte-identical and yield exactly 90 positive applicant observations, all pending because the source publishes no decision/outcome field. All 90 observations contain at least one structured identifier; 19 identifier cells contain both codice fiscale and partita IVA. Exact evidence is documented in docs/sources/lecce-operational-check-2026-09-18.md.",
        },
    ])
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_verified_pages() -> None:
    p = ROOT / "data/source_registry/verified_primary_pages.csv"
    with p.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = handle.seek(0) or None
    if any(r["authority_key"] == "lecce" for r in rows):
        raise RuntimeError("Lecce verified page already present")
    rows.append({"authority_key": "lecce", "landing_url": LANDING, "verification_date": "2026-09-18", "verification_status": "verified"})
    rows.sort(key=lambda r: r["authority_key"])
    with p.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["authority_key", "landing_url", "verification_date", "verification_status"])
        writer.writeheader(); writer.writerows(rows)


def update_source_series() -> None:
    p = ROOT / "data/source_registry/source_series_inventory.csv"
    with p.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle); fields = reader.fieldnames; rows = list(reader)
    if not fields:
        raise RuntimeError("source_series_inventory header missing")
    if any(r["source_series_key"].startswith("lecce-") for r in rows):
        raise RuntimeError("Lecce source series already present")
    rows.extend([
        {
            "source_series_key": "lecce-listed", "authority_key": "lecce", "regime_code": "WL-REGIME-L190-2012",
            "population_scope": "listed", "sector_scope": "all", "publication_model": "periodic_attachment",
            "series_url": LANDING, "resource_resolution_status": "landing_page_resolved", "verified_date": "2026-09-18",
            "notes": "Current official landing page directly verified 18 September 2026 and exposing the listed PDF labelled updated 9 September 2026. Independent attachment captures are byte-identical; exact source identity, 1,783 sector-row/825 observation boundary and anomaly handling are documented in docs/sources/lecce-operational-check-2026-09-18.md.",
        },
        {
            "source_series_key": "lecce-applicants", "authority_key": "lecce", "regime_code": "WL-REGIME-L190-2012",
            "population_scope": "applicant", "sector_scope": "all", "publication_model": "periodic_attachment",
            "series_url": LANDING, "resource_resolution_status": "landing_page_resolved", "verified_date": "2026-09-18",
            "notes": "Current official landing page directly verified 18 September 2026 and exposing the applicant PDF labelled updated 9 September 2026. Independent attachment captures are byte-identical and yield exactly 90 pending observations; exact evidence is documented in docs/sources/lecce-operational-check-2026-09-18.md.",
        },
    ])
    rows.sort(key=lambda r: r["source_series_key"])
    with p.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def update_catalog() -> None:
    counts = {}
    for key, rel in (("verified-primary-pages", "data/source_registry/verified_primary_pages.csv"), ("source-series-inventory", "data/source_registry/source_series_inventory.csv")):
        with (ROOT / rel).open(encoding="utf-8", newline="") as handle:
            counts[key] = sum(1 for _ in csv.DictReader(handle))
    p = ROOT / "data/catalog.csv"
    with p.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle); fields = reader.fieldnames; rows = list(reader)
    if not fields: raise RuntimeError("catalog header missing")
    for row in rows:
        if row["dataset_id"] in counts:
            row["record_count"] = str(counts[row["dataset_id"]])
    with p.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def update_coverage() -> None:
    p = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    matches = [x for x in data["prefectures"] if x["authority_key"] == "lecce"]
    if len(matches) != 1: raise RuntimeError("Expected exactly one Lecce coverage row")
    row = matches[0]
    row.update({
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
        "latest_source_reference_date": "2026-09-09",
        "last_successful_source_check_at": "2026-09-18T06:00:48Z",
        "last_attempted_source_check_at": "2026-09-18T06:00:48Z",
        "last_successful_investigation_on": "2026-09-18",
        "monitoring_status": "CURRENT",
        "unresolved_issue": ["Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."],
        "actionable_issue": False,
        "coverage_status": "VALIDATED",
        "terminal_reason": None,
        "completion_evidence": [DOC, "src/white_list_archive/parsers/lecce_tables.py", "tests/test_lecce_parser_semantics.py", "data/publication/multi_prefecture_pilot.json"],
        "known_content_sha256": [LISTED_SHA, APPLICANTS_SHA],
        "evidence": ["data/source_registry/verified_primary_pages.csv", "data/source_registry/source_series_inventory.csv", "data/publication/multi_prefecture_pilot.json", DOC],
        "last_completed_coverage_stage": "VALIDATED",
    })
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_dispatcher() -> None:
    must_replace(
        "src/white_list_archive/publishing/public_national_registry.py",
        "from white_list_archive.parsers.taranto_html import PARSERS as TARANTO_PARSERS\n",
        "from white_list_archive.parsers.taranto_html import PARSERS as TARANTO_PARSERS\nfrom white_list_archive.parsers.lecce_tables import PARSERS as LECCE_PARSERS\n",
    )
    must_replace(
        "src/white_list_archive/publishing/public_national_registry.py",
        "        or TARANTO_PARSERS.get(cfg[\"parser\"])\n    )",
        "        or TARANTO_PARSERS.get(cfg[\"parser\"])\n        or LECCE_PARSERS.get(cfg[\"parser\"])\n    )",
    )


def update_public_workflow() -> None:
    path = ".github/workflows/public-pages.yml"
    must_replace(path, "      - 'src/white_list_archive/parsers/taranto_html.py'\n", "      - 'src/white_list_archive/parsers/taranto_html.py'\n      - 'src/white_list_archive/parsers/lecce_tables.py'\n")
    replacements = {
        "assert reg['meta']['record_count'] == 59642": "assert reg['meta']['record_count'] == 60557",
        "'firenze','taranto'}": "'firenze','taranto','lecce'}",
        "'firenze-ordinary','taranto-ordinary'\n          }": "'firenze-ordinary','taranto-ordinary','lecce-ordinary'\n          }",
        "assert reg['meta']['authority_count'] == 51": "assert reg['meta']['authority_count'] == 52",
        "assert reg['meta']['register_count'] == 53": "assert reg['meta']['register_count'] == 54",
        "assert pref['meta']['published_count'] == 51": "assert pref['meta']['published_count'] == 52",
        "assert pref['meta']['mapped_count'] == 51": "assert pref['meta']['mapped_count'] == 52",
    }
    for old, new in replacements.items(): must_replace(path, old, new)
    anchor = "          assert sum(bool(r.get('source_fields', {}).get('malformed_date_pairs')) for r in taranto_records if r['source_key'] == 'taranto-listed') == 8\n"
    block = anchor + "          lecce = [x for x in pref['prefectures'] if x['authority_key'] == 'lecce']\n          assert len(lecce) == 1 and lecce[0]['mapped'] and lecce[0]['published'] and lecce[0]['series_count'] == 2\n          lecce_records = [r for r in reg['records'] if r['authority_key'] == 'lecce']\n          assert len(lecce_records) == 915\n          assert sum(r['source_key'] == 'lecce-listed' for r in lecce_records) == 825\n          assert sum(r['source_key'] == 'lecce-applicants' for r in lecce_records) == 90\n          assert sum(r['source_status'] == 'listed' for r in lecce_records) == 582\n          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in lecce_records) == 243\n          assert sum(r['source_status'] == 'pending' for r in lecce_records) == 90\n          assert len({r['record_locator'] for r in lecce_records}) == 915\n          assert sum(bool(r['identifiers']) for r in lecce_records) == 894\n          assert sum(bool(r['identifier_field_raw']) and not r['identifiers'] for r in lecce_records) == 20\n          assert sum(not bool(r['identifier_field_raw']) and not r['identifiers'] for r in lecce_records) == 1\n          assert sum(not bool(r['observed_listing_date']) and bool(r['source_fields']['listing_date_raw_variants']) for r in lecce_records if r['source_key'] == 'lecce-listed') == 4\n          assert sum(not bool(r['observed_expiry_date']) and bool(r['source_fields']['expiry_date_raw_variants']) for r in lecce_records if r['source_key'] == 'lecce-listed') == 2\n"
    must_replace(path, anchor, block)


def update_browser() -> None:
    path = "tests/public_portal_browser.cjs"
    must_replace(path, "      assert.ok(labels.includes('White List ordinaria · Prefettura di Taranto'));\n", "      assert.ok(labels.includes('White List ordinaria · Prefettura di Taranto'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Lecce'));\n")
    must_replace(path, "      assert.equal(stats.total,59642);", "      assert.equal(stats.total,60557);")
    must_replace(path, "'como','firenze','taranto'].includes(r.authority_key)", "'como','firenze','taranto','lecce'].includes(r.authority_key)")
    anchor = "      assert.equal(taranto.filter(r=>r.source_key==='taranto-listed'&&r.source_fields.malformed_date_pairs.length>0).length,8);\n"
    block = anchor + "      const lecce=registry.records.filter(r=>r.authority_key==='lecce');\n      assert.equal(lecce.length,915);\n      assert.equal(lecce.filter(r=>r.source_key==='lecce-listed').length,825);\n      assert.equal(lecce.filter(r=>r.source_key==='lecce-applicants').length,90);\n      assert.deepEqual(statusCounts(lecce),{listed:582,pending:90,renewal_update_in_progress:243});\n      assert.equal(new Set(lecce.map(r=>r.record_locator)).size,915);\n      assert.equal(lecce.filter(r=>r.identifiers.length>0).length,894);\n      assert.equal(lecce.filter(r=>r.identifier_field_raw&&r.identifiers.length===0).length,20);\n      assert.equal(lecce.filter(r=>!r.identifier_field_raw&&r.identifiers.length===0).length,1);\n      assert.equal(lecce.filter(r=>r.source_key==='lecce-listed'&&!r.observed_listing_date&&r.source_fields.listing_date_raw_variants.length>0).length,4);\n      assert.equal(lecce.filter(r=>r.source_key==='lecce-listed'&&!r.observed_expiry_date&&r.source_fields.expiry_date_raw_variants.length>0).length,2);\n"
    must_replace(path, anchor, block)


def main() -> None:
    update_publication(); update_verified_pages(); update_source_series(); update_catalog(); update_coverage(); update_dispatcher(); update_public_workflow(); update_browser()


if __name__ == "__main__":
    main()
