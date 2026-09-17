from __future__ import annotations

import csv
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = "https://prefettura.interno.gov.it/it/prefetture/modena/white-list-elenchi-provinciali-ed-elenchi-ricostruzione-post-sisma"
CHECK_AT = "2026-09-16T22:28:25Z"
REFERENCE_DATE = "2026-09-16"

SOURCES = {
    "modena-provincial-listed": {
        "template": "bologna-provincial-listed",
        "parser": "modena_listed",
        "register_key": "modena-provincial",
        "register_name": "White List provinciale",
        "population_scope": "listed",
        "resource_url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/iscritti-elenchi-wl-provinciali.pdf",
        "sha256": "84f7ffa41f8e14b7cb1b3f5817d46e20c721b43a1a77280955999be331f2380a",
        "expected_source_rows": 1181,
        "expected_sector_rows": 2174,
        "regime_code": "WL-REGIME-L190-2012",
        "sector_scope": "all",
        "notes": "Current official Modena landing page verified 17 September 2026; the ordinary provincial registered-company attachment was captured twice independently with identical bytes. It yields 2,174 source-sector rows and 1,181 exact logical observations. Exact byte identity, grouping rules and reviewed malformed-date evidence are documented in docs/sources/modena-operational-check-2026-09-17.md.",
    },
    "modena-provincial-applicants": {
        "template": "bologna-provincial-applicants",
        "parser": "modena_applicants",
        "register_key": "modena-provincial",
        "register_name": "White List provinciale",
        "population_scope": "applicant",
        "resource_url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/richiedenti-iscrizione-elenchi-wl-provinciali.pdf",
        "sha256": "323c1dace295b50f4baff85545879be920dc05ef9072f34b4d98449acf11f79f",
        "expected_source_rows": 502,
        "expected_sector_rows": 803,
        "regime_code": "WL-REGIME-L190-2012",
        "sector_scope": "all",
        "notes": "Current official Modena landing page verified 17 September 2026; the ordinary provincial applicant attachment was captured twice independently with identical bytes. It yields 803 source-sector rows and 502 exact pending observations. Exact byte identity and grouping rules are documented in docs/sources/modena-operational-check-2026-09-17.md.",
    },
    "modena-post-sisma-listed": {
        "template": "bologna-post-sisma-listed",
        "parser": "modena_listed",
        "register_key": "modena-post-sisma",
        "register_name": "White List post-sisma",
        "population_scope": "listed",
        "resource_url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-08/iscritti-elenchi-wl-ricostruzione-post-sisma_5.pdf",
        "sha256": "658e24f8342c04dc8c16dba8d4e3660c16fbff89722507a30dfba1d9a43274d0",
        "expected_source_rows": 1679,
        "expected_sector_rows": 2927,
        "regime_code": "WL-REGIME-ER-SISMA-2012",
        "sector_scope": "special_regime",
        "notes": "Current official Modena landing page verified 17 September 2026 positively exposes a distinct post-earthquake registered-company attachment. Two independent captures were byte-identical; the source yields 2,927 source-sector rows and 1,679 exact logical observations. Exact byte identity, grouping rules and reviewed malformed-date evidence are documented in docs/sources/modena-operational-check-2026-09-17.md.",
    },
    "modena-post-sisma-applicants": {
        "template": "bologna-post-sisma-applicants",
        "parser": "modena_applicants",
        "register_key": "modena-post-sisma",
        "register_name": "White List post-sisma",
        "population_scope": "applicant",
        "resource_url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-08/richiedenti-iscrizione-elenchi-wl-ricostruzione-post-sisma_3.pdf",
        "sha256": "e21f47c956dd355fc2400ef110916349632ad6f31eb7878c99a3d05834eb5bf1",
        "expected_source_rows": 430,
        "expected_sector_rows": 432,
        "regime_code": "WL-REGIME-ER-SISMA-2012",
        "sector_scope": "special_regime",
        "notes": "Current official Modena landing page verified 17 September 2026 positively exposes a distinct post-earthquake applicant attachment. Two independent captures were byte-identical; the source yields 432 source-sector rows and 430 exact pending observations. Exact byte identity and grouping rules are documented in docs/sources/modena-operational-check-2026-09-17.md.",
    },
}


def dump_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def replace_once(text: str, old: str, new: str, context: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{context}: expected one occurrence, found {count}: {old!r}")
    return text.replace(old, new, 1)


def patch_publication_config() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    current = {row["source_key"]: row for row in config["sources"]}
    if set(SOURCES) & set(current):
        raise RuntimeError("Modena publication sources already present; refusing non-idempotent integration")
    additions = []
    for key, spec in SOURCES.items():
        template = current.get(spec["template"])
        if template is None:
            raise RuntimeError(f"Missing template source {spec['template']}")
        row = deepcopy(template)
        row.update(
            source_key=key,
            parser=spec["parser"],
            authority_key="modena",
            authority_name="Prefettura di Modena",
            register_key=spec["register_key"],
            register_name=spec["register_name"],
            population_scope=spec["population_scope"],
            reference_date=REFERENCE_DATE,
            source_page_url=LANDING,
            resource_url=spec["resource_url"],
            sha256=spec["sha256"],
            expected_source_rows=spec["expected_source_rows"],
            expected_sector_rows=spec["expected_sector_rows"],
            last_source_update=REFERENCE_DATE,
            last_source_update_basis="current official Modena landing page and byte-pinned attachment verification",
        )
        row.pop("semantic_sha256", None)
        row["approval_mode"] = "raw_sha256"
        additions.append(row)
    index = next((i for i, row in enumerate(config["sources"]) if row["authority_key"] > "modena"), len(config["sources"]))
    config["sources"][index:index] = additions
    dump_json(path, config)


def patch_verified_pages() -> None:
    path = ROOT / "data/source_registry/verified_primary_pages.csv"
    fields, rows = read_csv(path)
    if any(row["authority_key"] == "modena" for row in rows):
        raise RuntimeError("Modena primary page already present")
    rows.append({
        "authority_key": "modena",
        "landing_url": LANDING,
        "verification_date": "2026-09-17",
        "verification_status": "verified",
    })
    rows.sort(key=lambda row: row["authority_key"])
    write_csv(path, fields, rows)


def patch_source_inventory() -> None:
    path = ROOT / "data/source_registry/source_series_inventory.csv"
    fields, rows = read_csv(path)
    existing = {row["source_series_key"] for row in rows}
    if set(SOURCES) & existing:
        raise RuntimeError("Modena source-series inventory already contains candidate rows")
    for key, spec in SOURCES.items():
        rows.append({
            "source_series_key": key,
            "authority_key": "modena",
            "regime_code": spec["regime_code"],
            "population_scope": spec["population_scope"],
            "sector_scope": spec["sector_scope"],
            "publication_model": "periodic_attachment",
            "series_url": LANDING,
            "resource_resolution_status": "landing_page_resolved",
            "verified_date": "2026-09-17",
            "notes": spec["notes"],
        })
    rows.sort(key=lambda row: row["source_series_key"])
    write_csv(path, fields, rows)


def patch_catalog() -> None:
    path = ROOT / "data/catalog.csv"
    fields, rows = read_csv(path)
    expected = {"verified-primary-pages": "48", "source-series-inventory": "95"}
    seen: set[str] = set()
    for row in rows:
        dataset_id = row["dataset_id"]
        if dataset_id in expected:
            row["record_count"] = expected[dataset_id]
            seen.add(dataset_id)
    if seen != set(expected):
        raise RuntimeError(f"Missing catalogue rows: {sorted(set(expected) - seen)}")
    write_csv(path, fields, rows)


def patch_monitoring() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    ledger = json.loads(path.read_text(encoding="utf-8"))
    matches = [row for row in ledger["prefectures"] if row["authority_key"] == "modena"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Modena ledger row, got {len(matches)}")
    row = matches[0]
    row.update(
        official_landing_page=LANDING,
        source_verified=True,
        current_edition_identified=True,
        capture_implemented=True,
        parser_implemented=True,
        parser_validated=True,
        company_observations_loaded=True,
        observation_layer="public_source_observations",
        canonical_integration_validated=False,
        public_export_enabled=True,
        durable_evidence_verified=False,
        population_scopes_complete=True,
        latest_source_reference_date=REFERENCE_DATE,
        last_successful_source_check_at=CHECK_AT,
        last_attempted_source_check_at=CHECK_AT,
        last_content_change_at=CHECK_AT,
        last_successful_investigation_on="2026-09-17",
        monitoring_status="CURRENT",
        unresolved_issue=["https://github.com/colazeta/italian-anti-mafia-whitelist/issues/16"],
        actionable_issue=False,
        coverage_status="VALIDATED",
        terminal_reason=None,
        completion_evidence=[
            "docs/sources/modena-operational-check-2026-09-17.md",
            "src/white_list_archive/parsers/modena_tables.py",
            "tests/test_modena_parser_semantics.py",
            "data/publication/multi_prefecture_pilot.json",
        ],
        known_content_sha256=[SOURCES[key]["sha256"] for key in SOURCES],
        evidence=[
            "data/source_registry/verified_primary_pages.csv",
            "data/source_registry/source_series_inventory.csv",
            "data/publication/multi_prefecture_pilot.json",
            "docs/sources/modena-operational-check-2026-09-17.md",
        ],
        last_completed_coverage_stage="VALIDATED",
    )
    if "source_update_pending" in row:
        row["source_update_pending"] = False
    dump_json(path, ledger)


def patch_public_registry() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from white_list_archive.parsers.milano_webapp import PARSERS as MILANO_PARSERS\n",
        "from white_list_archive.parsers.milano_webapp import PARSERS as MILANO_PARSERS\nfrom white_list_archive.parsers.modena_tables import PARSERS as MODENA_PARSERS\n",
        "Modena parser import",
    )
    text = replace_once(
        text,
        "        or MILANO_PARSERS.get(cfg[\"parser\"])\n    )",
        "        or MILANO_PARSERS.get(cfg[\"parser\"])\n        or MODENA_PARSERS.get(cfg[\"parser\"])\n    )",
        "Modena parser dispatch",
    )
    path.write_text(text, encoding="utf-8")


def patch_source_tests() -> None:
    path = ROOT / "tests/test_source_registry.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, "assert len(pages) == 47", "assert len(pages) == 48", "verified primary-page count")
    path.write_text(text, encoding="utf-8")

    path = ROOT / "tests/test_source_population_coverage.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, 'assert report["verified_authority_count"] == 47', 'assert report["verified_authority_count"] == 48', "verified authority count")
    text = replace_once(text, 'assert report["register_scope_count"] == 48', 'assert report["register_scope_count"] == 50', "register scope count")
    text = replace_once(text, 'assert report["complete_register_scope_count"] == 48', 'assert report["complete_register_scope_count"] == 50', "complete register scope count")
    append = '''\n\ndef test_modena_special_register_is_a_separate_completeness_scope():\n    report = _report()\n    modena = [row for row in report["scopes"] if row["authority_key"] == "modena"]\n    assert {row["regime_code"] for row in modena} == {\n        "WL-REGIME-L190-2012",\n        "WL-REGIME-ER-SISMA-2012",\n    }\n    assert all(row["listed_status"] == "COVERED_SEPARATE_SERIES" for row in modena)\n    assert all(row["applicant_status"] == "COVERED_SEPARATE_SERIES" for row in modena)\n    assert all(row["source_population_complete"] for row in modena)\n'''
    if "test_modena_special_register_is_a_separate_completeness_scope" in text:
        raise RuntimeError("Modena population-scope test already present")
    path.write_text(text.rstrip() + append.rstrip() + "\n", encoding="utf-8")


def patch_browser_test() -> None:
    path = ROOT / "tests/public_portal_browser.cjs"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "      assert.ok(labels.includes('White List — Prefettura di Milano · Prefettura di Milano'));\n",
        "      assert.ok(labels.includes('White List — Prefettura di Milano · Prefettura di Milano'));\n      assert.ok(labels.includes('White List provinciale · Prefettura di Modena'));\n      assert.ok(labels.includes('White List post-sisma · Prefettura di Modena'));\n",
        "Modena register labels",
    )
    text = replace_once(text, "assert.equal(stats.total,54177);", "assert.equal(stats.total,57969);", "public total")
    text = replace_once(
        text,
        "'sassari','milano'].includes(r.authority_key)",
        "'sassari','milano','modena'].includes(r.authority_key)",
        "baseline authority exclusion",
    )
    marker = "      assert.ok(milano.every(r=>r.source_fields.sections.length===r.source_fields.physical_locators.length));\n"
    addition = marker + """      const modena=registry.records.filter(r=>r.authority_key==='modena');\n      assert.equal(modena.length,3792);\n      assert.equal(modena.filter(r=>r.source_key==='modena-provincial-listed').length,1181);\n      assert.equal(modena.filter(r=>r.source_key==='modena-provincial-applicants').length,502);\n      assert.equal(modena.filter(r=>r.source_key==='modena-post-sisma-listed').length,1679);\n      assert.equal(modena.filter(r=>r.source_key==='modena-post-sisma-applicants').length,430);\n      assert.deepEqual(statusCounts(modena),{listed:1560,pending:932,renewal_update_in_progress:1300});\n      assert.equal(new Set(modena.map(r=>r.record_locator)).size,3792);\n      assert.equal(modena.filter(r=>r.identifiers.length>0).length,3751);\n      assert.equal(modena.filter(r=>r.identifier_field_raw&&r.identifiers.length===0).length,41);\n      assert.ok(modena.every(r=>r.requested_activities.length>0));\n      assert.ok(modena.every(r=>['modena_listed','modena_applicants'].includes(r.parser_name)&&r.parser_version==='1'));\n      assert.ok(modena.every(r=>r.source_fields.sections.length>0&&r.source_fields.physical_locators.length>0));\n"""
    text = replace_once(text, marker, addition, "Modena browser evidence")
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_publication_config()
    patch_verified_pages()
    patch_source_inventory()
    patch_catalog()
    patch_monitoring()
    patch_public_registry()
    patch_source_tests()
    patch_browser_test()


if __name__ == "__main__":
    main()
