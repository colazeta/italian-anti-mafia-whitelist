from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LANDING = "https://prefettura.interno.gov.it/it/prefetture/cagliari/evidenza/white-list"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/white-list-elenco-ditte-iscritte-al-06-settembre-2026.pdf"
APPLICANT_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-09/white-list-elenco-ditte-richiedenti-iscrizione-al-06-settembre-2026.pdf"
LISTED_SHA = "dfbc00403ee287511a48df5314c663f5a1c6173803d87c4ce27b1d80e2c13114"
APPLICANT_SHA = "7429040f5945ecb72cc7b152dbd8aaeee0e0a5df9bb7414e951a4cec4a4f50f7"
REFERENCE_DATE = "2026-09-06"
CHECK_AT = "2026-09-11T12:00:44Z"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one replacement target, found {count}")
    return text.replace(old, new, 1)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def patch_public_config() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    if any(source["source_key"].startswith("cagliari-") for source in config["sources"]):
        raise RuntimeError("Cagliari already present in publication config")
    config["verified_at"] = "2026-09-11"
    config["sources"].extend(
        [
            {
                "source_key": "cagliari-listed",
                "parser": "cagliari_listed",
                "authority_key": "cagliari",
                "authority_name": "Prefettura di Cagliari",
                "register_key": "cagliari-ordinary",
                "register_name": "White List ordinaria · Prefettura di Cagliari",
                "population_scope": "listed",
                "reference_date": REFERENCE_DATE,
                "source_page_url": LANDING,
                "resource_url": LISTED_URL,
                "sha256": LISTED_SHA,
                "expected_sector_rows": 1832,
                "expected_source_rows": 750,
                "last_source_update": REFERENCE_DATE,
                "last_source_update_basis": "dated official resource exposed by the current official landing page",
                "notes": "Official landing page positively labels this attachment as Elenco Ditte iscritte. The PDF internal title incorrectly says richiedenti, while its table semantics are registration date, expiry date and update-in-progress. The discrepancy is retained as source provenance; the byte-pinned 1,832 sector rows yield 750 observations after conflict-audited conservative repeat grouping. Malformed ten-digit source identifier 0336817853 is preserved raw and never reconstructed."
            },
            {
                "source_key": "cagliari-applicants",
                "parser": "cagliari_applicants",
                "authority_key": "cagliari",
                "authority_name": "Prefettura di Cagliari",
                "register_key": "cagliari-ordinary",
                "register_name": "White List ordinaria · Prefettura di Cagliari",
                "population_scope": "applicant",
                "reference_date": REFERENCE_DATE,
                "source_page_url": LANDING,
                "resource_url": APPLICANT_URL,
                "sha256": APPLICANT_SHA,
                "expected_source_rows": 51,
                "last_source_update": REFERENCE_DATE,
                "last_source_update_basis": "dated official resource exposed by the current official landing page",
                "notes": "Official landing page positively exposes the applicant attachment. It contains 51 explicit In istruttoria observations. Malformed ten-digit source identifier 3814850925 and one blank source address are preserved without reconstruction or inference."
            },
        ]
    )
    write_json(path, config)


def patch_csv_registries() -> None:
    verified_path = ROOT / "data/source_registry/verified_primary_pages.csv"
    with verified_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0])
    found = 0
    for row in rows:
        if row["authority_key"] == "cagliari":
            row.update(landing_url=LANDING, verification_date="2026-09-11", verification_status="verified")
            found += 1
    if found != 1:
        raise RuntimeError(f"verified_primary_pages: expected one Cagliari row, found {found}")
    with verified_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)

    series_path = ROOT / "data/source_registry/source_series_inventory.csv"
    with series_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0])
    notes = {
        "cagliari-listed": (
            "Current official landing page directly reverified 11 September 2026; it positively exposes the listed-company PDF dated 6 September 2026. "
            "The byte-pinned 24-page attachment has 1,832 sector rows yielding 750 conflict-audited public observations (713 listed; 37 renewal/update in progress). "
            "Its internal heading is mislabeled as richiedenti despite listed registration/expiry table semantics; this anomaly and raw malformed identifier handling are documented in docs/sources/cagliari-operational-check-2026-09-11.md."
        ),
        "cagliari-applicants": (
            "Current official landing page directly reverified 11 September 2026; it separately and positively exposes the applicant PDF dated 6 September 2026. "
            "The byte-pinned two-page attachment yields 51 explicit In istruttoria observations; malformed identifier and blank-address source values remain raw/uninferred. "
            "Exact evidence is documented in docs/sources/cagliari-operational-check-2026-09-11.md."
        ),
    }
    found = set()
    for row in rows:
        if row["source_series_key"] in notes:
            row["series_url"] = LANDING
            row["resource_resolution_status"] = "landing_page_resolved"
            row["verified_date"] = "2026-09-11"
            row["notes"] = notes[row["source_series_key"]]
            found.add(row["source_series_key"])
    if found != set(notes):
        raise RuntimeError(f"source_series_inventory missing Cagliari rows: {set(notes) - found}")
    with series_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def patch_ledger() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    ledger = json.loads(path.read_text(encoding="utf-8"))
    matches = [row for row in ledger["prefectures"] if row["authority_key"] == "cagliari"]
    if len(matches) != 1:
        raise RuntimeError(f"national ledger: expected one Cagliari row, found {len(matches)}")
    row = matches[0]
    row.update(
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
        last_content_change_at=None,
        last_successful_investigation_on="2026-09-11",
        monitoring_status="CURRENT",
        unresolved_issue=["Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."],
        actionable_issue=False,
        coverage_status="VALIDATED",
        terminal_reason=None,
        completion_evidence=[
            "docs/sources/cagliari-operational-check-2026-09-11.md",
            "src/white_list_archive/parsers/cagliari_tables.py",
            "tests/test_cagliari_parser_semantics.py",
            "data/publication/multi_prefecture_pilot.json",
        ],
        known_content_sha256=[LISTED_SHA, APPLICANT_SHA],
        evidence=[
            "data/source_registry/verified_primary_pages.csv",
            "data/source_registry/source_series_inventory.csv",
            "data/publication/multi_prefecture_pilot.json",
            "docs/sources/cagliari-operational-check-2026-09-11.md",
        ],
        last_completed_coverage_stage="VALIDATED",
    )
    if "source_update_pending" in row:
        row["source_update_pending"] = False
    write_json(path, ledger)


def patch_registry_binding() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from white_list_archive.parsers.brindisi_tables import PARSERS as BRINDISI_PARSERS\n",
        "from white_list_archive.parsers.brindisi_tables import PARSERS as BRINDISI_PARSERS\nfrom white_list_archive.parsers.cagliari_tables import PARSERS as CAGLIARI_PARSERS\n",
        "registry import",
    )
    text = replace_once(
        text,
        "        or BRINDISI_PARSERS.get(cfg[\"parser\"])\n",
        "        or BRINDISI_PARSERS.get(cfg[\"parser\"])\n        or CAGLIARI_PARSERS.get(cfg[\"parser\"])\n",
        "registry parser chain",
    )
    path.write_text(text, encoding="utf-8")


def patch_operations_test() -> None:
    path = ROOT / "tests/test_operations.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    # source-identified stage. Cagliari remains unadvanced while Brindisi graduates\n    # only after positive listed/applicant evidence, byte identity and parser validation.\n    authority_key = \"cagliari\"\n",
        "    # source-identified stage. Crotone remains unadvanced while Cagliari graduates\n    # only after positive listed/applicant evidence, byte identity and parser validation.\n    authority_key = \"crotone\"\n",
        "operations unadvanced fixture",
    )
    path.write_text(text, encoding="utf-8")


def patch_browser_test() -> None:
    path = ROOT / "tests/public_portal_browser.cjs"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "      assert.ok(labels.includes('White List ordinaria · Prefettura di Brindisi'));\n",
        "      assert.ok(labels.includes('White List ordinaria · Prefettura di Brindisi'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Cagliari'));\n",
        "browser register label",
    )
    text = replace_once(text, "      assert.equal(stats.total,17714);\n", "      assert.equal(stats.total,18515);\n", "browser total")
    text = replace_once(
        text,
        "'bergamo','barletta-andria-trani','brindisi'].includes(r.authority_key));",
        "'bergamo','barletta-andria-trani','brindisi','cagliari'].includes(r.authority_key));",
        "browser frozen baseline exclusion",
    )
    anchor = "      assert.deepEqual(statusCounts(brindisi),{listed:341,pending:26,renewal_update_in_progress:44});\n"
    block = anchor + "      const cagliari=registry.records.filter(r=>r.authority_key==='cagliari');\n      assert.equal(cagliari.length,801);\n      assert.equal(cagliari.filter(r=>r.source_key==='cagliari-listed').length,750);\n      assert.equal(cagliari.filter(r=>r.source_key==='cagliari-applicants').length,51);\n      assert.deepEqual(statusCounts(cagliari),{listed:713,pending:51,renewal_update_in_progress:37});\n      const aeffe=cagliari.filter(r=>r.name==='AEFFE di Farci Alessandro');\n      assert.equal(aeffe.length,1);\n      assert.equal(aeffe[0].identifier_field_raw,'0336817853');\n      assert.deepEqual(aeffe[0].identifiers,[]);\n      assert.deepEqual(aeffe[0].requested_activities,['Sezione 1','Sezione 5']);\n      const lapignola=cagliari.filter(r=>r.name==='La Pignola S.r.l.');\n      assert.equal(lapignola.length,1);\n      assert.equal(lapignola[0].identifier_field_raw,'3814850925');\n      assert.deepEqual(lapignola[0].identifiers,[]);\n      const collu=cagliari.filter(r=>r.name==='Collu Giuliano Impresa Individuale');\n      assert.equal(collu.length,1);\n      assert.equal(collu[0].registered_office,'');\n"
    text = replace_once(text, anchor, block, "browser Cagliari assertions")
    path.write_text(text, encoding="utf-8")


def patch_public_pages() -> None:
    path = ROOT / ".github/workflows/public-pages.yml"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "      - 'src/white_list_archive/parsers/brindisi_tables.py'\n",
        "      - 'src/white_list_archive/parsers/brindisi_tables.py'\n      - 'src/white_list_archive/parsers/cagliari_tables.py'\n",
        "Pages parser trigger",
    )
    text = replace_once(text, "          assert reg['meta']['record_count'] == 17714\n", "          assert reg['meta']['record_count'] == 18515\n", "Pages record count")
    text = replace_once(
        text,
        "'bergamo','barletta-andria-trani','brindisi'}\n",
        "'bergamo','barletta-andria-trani','brindisi','cagliari'}\n",
        "Pages authority set",
    )
    text = replace_once(
        text,
        "'bergamo-ordinary','barletta-andria-trani-ordinary','brindisi-ordinary'\n",
        "'bergamo-ordinary','barletta-andria-trani-ordinary','brindisi-ordinary','cagliari-ordinary'\n",
        "Pages register set",
    )
    text = replace_once(text, "          assert reg['meta']['authority_count'] == 21\n", "          assert reg['meta']['authority_count'] == 22\n", "Pages authority count")
    text = replace_once(text, "          assert reg['meta']['register_count'] == 22\n", "          assert reg['meta']['register_count'] == 23\n", "Pages register count")
    text = replace_once(text, "          assert pref['meta']['published_count'] == 21\n", "          assert pref['meta']['published_count'] == 22\n", "Pages published count")
    anchor = "          brindisi = [x for x in pref['prefectures'] if x['authority_key'] == 'brindisi']\n          assert len(brindisi) == 1 and brindisi[0]['mapped'] and brindisi[0]['published']\n"
    block = anchor + "          cagliari = [x for x in pref['prefectures'] if x['authority_key'] == 'cagliari']\n          assert len(cagliari) == 1 and cagliari[0]['mapped'] and cagliari[0]['published']\n"
    text = replace_once(text, anchor, block, "Pages Cagliari mapped/published assertion")
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_public_config()
    patch_csv_registries()
    patch_ledger()
    patch_registry_binding()
    patch_operations_test()
    patch_browser_test()
    patch_public_pages()
    print("Cagliari production candidate materialised: 801 records; target national 18515 / 22 / 23 / mapped 35")


if __name__ == "__main__":
    main()
