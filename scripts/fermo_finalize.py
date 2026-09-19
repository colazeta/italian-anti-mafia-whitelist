from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = "https://prefettura.interno.gov.it/it/prefetture/fermo/white-list-elenco-imprese-richiedenti-e-iscritte"
LISTED_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-05/imprese-iscritte-wl-22-maggio-2026_0.xlsx"
APPLICANTS_URL = "https://prefettura.interno.gov.it/sites/default/files/0/2026-05/imprese-richiedenti-iscrizione-wl-22-maggio-2026.xlsx"
LISTED_SHA = "2ed8f867c6ee477ec0af22a827ac0ccf54e4d483eec5de5fc27c812a0c31c6dd"
APPLICANTS_SHA = "fa17e1f6676f84dc51e8abd1fd6e7627a1a2ed684a55c490708a06990e48676f"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"{label}: expected one patch anchor, found {text.count(old)}")
    return text.replace(old, new, 1)


def patch_parser() -> None:
    path = ROOT / "src/white_list_archive/parsers/fermo_openxml.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''                source_fields={\n                    "source_row": record["source_row"],\n                    "source_ordinal": record["source_ordinal"],\n                    "activity_raw": record["activity_raw"],\n                    "listing_date_raw": record["listing_raw"],\n                    "expiry_date_raw": record["expiry_raw"],\n                    "malformed_listing_date": not bool(record["listing_date"]),\n                },''',
        '''                source_fields={\n                    "sections": list(record["activities"]),\n                    "listing_date_raw_variants": [record["listing_raw"]] if record["listing_raw"] else [],\n                    "expiry_date_raw_variants": [record["expiry_raw"]] if record["expiry_raw"] else [],\n                    "notes": [record["note"]] if record["note"] else [],\n                    "malformed_date_pairs": [f"listing_date={record['listing_raw']}"] if not record["listing_date"] else [],\n                },''',
        "listed public source fields",
    )
    text = replace_once(
        text,
        '''                source_fields={\n                    "source_row": record["source_row"],\n                    "source_ordinal": record["source_ordinal"],\n                    "activity_raw": record["activity_raw"],\n                    "application_date_raw": record["application_raw"],\n                    "malformed_application_date": not bool(record["application_date"]),\n                },''',
        '''                source_fields={\n                    "requested_activities_source": record["activity_raw"],\n                    "application_date_raw_variants": [record["application_raw"]] if record["application_raw"] else [],\n                    "malformed_date_pairs": [f"application_date={record['application_raw']}"] if not record["application_date"] else [],\n                },''',
        "applicant public source fields",
    )
    path.write_text(text, encoding="utf-8")


def patch_registry() -> None:
    path = ROOT / "src/white_list_archive/publishing/public_national_registry.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from white_list_archive.parsers.cuneo_positioned import PARSERS as CUNEO_PARSERS\n",
        "from white_list_archive.parsers.cuneo_positioned import PARSERS as CUNEO_PARSERS\nfrom white_list_archive.parsers.fermo_openxml import PARSERS as FERMO_PARSERS\n",
        "registry import",
    )
    text = replace_once(
        text,
        '        or CUNEO_PARSERS.get(cfg["parser"])\n',
        '        or CUNEO_PARSERS.get(cfg["parser"])\n        or FERMO_PARSERS.get(cfg["parser"])\n',
        "registry parser resolver",
    )
    path.write_text(text, encoding="utf-8")


def patch_publication_config() -> None:
    path = ROOT / "data/publication/multi_prefecture_pilot.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if any(x["source_key"].startswith("fermo-") for x in data["sources"]):
        raise SystemExit("Fermo publication sources already exist")
    common = {
        "authority_key": "fermo",
        "authority_name": "Prefettura di Fermo",
        "register_key": "fermo-ordinary",
        "register_name": "White List ordinaria",
        "reference_date": "2026-05-22",
        "source_page_url": LANDING,
        "last_source_update": "2026-05-22",
        "last_source_update_basis": "explicit official attachment label al 22 maggio 2026; two independent cache-bypassed captures reverified byte-identical on 19 September 2026",
        "approval_mode": "raw_sha256",
    }
    data["sources"].extend(
        [
            {
                **common,
                "source_key": "fermo-listed",
                "parser": "fermo_listed",
                "population_scope": "listed",
                "resource_url": LISTED_URL,
                "sha256": LISTED_SHA,
                "expected_source_rows": 174,
                "notes": "Dedicated official listed-company XLSX. 174 observations = 97 listed + 77 renewal/update in progress; 163/174 have structured identifiers. Source ordinals 105 and 121 are absent; one malformed listing date remains raw-only.",
            },
            {
                **common,
                "source_key": "fermo-applicants",
                "parser": "fermo_applicants",
                "population_scope": "applicant",
                "resource_url": APPLICANTS_URL,
                "sha256": APPLICANTS_SHA,
                "expected_source_rows": 75,
                "notes": "Dedicated official applicant XLSX. Positive applicant title evidence yields 75 pending observations; 70/75 have structured identifiers. Source ordinal 38 is absent; raw numeric date token 46092 is retained without inference.",
            },
        ]
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_csv_row(path: Path, rows_to_add: list[dict[str, str]], key: str) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    existing = {row[key] for row in rows}
    for row in rows_to_add:
        if row[key] in existing:
            raise SystemExit(f"Duplicate CSV key: {row[key]}")
        rows.append(row)
    rows.sort(key=lambda row: row[key])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def patch_source_registry() -> None:
    add_csv_row(
        ROOT / "data/source_registry/verified_primary_pages.csv",
        [{"authority_key": "fermo", "landing_url": LANDING, "verified_date": "2026-09-19", "verification_status": "verified"}],
        "authority_key",
    )
    add_csv_row(
        ROOT / "data/source_registry/source_series_inventory.csv",
        [
            {
                "source_series_key": "fermo-listed",
                "authority_key": "fermo",
                "regime_code": "WL-REGIME-L190-2012",
                "population_scope": "listed",
                "sector_scope": "all",
                "publication_model": "periodic_attachment",
                "series_url": LANDING,
                "resource_resolution_status": "landing_page_resolved",
                "verified_date": "2026-09-19",
                "notes": "Current official Fermo page directly reverified 19 September 2026; dedicated XLSX explicitly labelled al 22 maggio 2026 yields 174 listed-side observations (97 listed; 77 renewal/update). Exact SHA and conservative anomaly handling are documented in docs/sources/fermo-operational-check-2026-09-19.md.",
            },
            {
                "source_series_key": "fermo-applicants",
                "authority_key": "fermo",
                "regime_code": "WL-REGIME-L190-2012",
                "population_scope": "applicant",
                "sector_scope": "all",
                "publication_model": "periodic_attachment",
                "series_url": LANDING,
                "resource_resolution_status": "landing_page_resolved",
                "verified_date": "2026-09-19",
                "notes": "Current official Fermo page directly reverified 19 September 2026; dedicated applicant XLSX explicitly labelled al 22 maggio 2026 yields exactly 75 pending observations. Exact SHA and conservative anomaly handling are documented in docs/sources/fermo-operational-check-2026-09-19.md.",
            },
        ],
        "source_series_key",
    )


def patch_coverage() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    row = next(x for x in data["prefectures"] if x["authority_key"] == "fermo")
    row.update(
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
            "latest_source_reference_date": "2026-05-22",
            "last_successful_investigation_on": "2026-09-19",
            "coverage_status": "VALIDATED",
            "terminal_reason": None,
            "completion_evidence": [
                "docs/sources/fermo-operational-check-2026-09-19.md",
                "src/white_list_archive/parsers/fermo_openxml.py",
                "tests/test_fermo_parser_semantics.py",
                "data/publication/multi_prefecture_pilot.json",
            ],
            "known_content_sha256": [LISTED_SHA, APPLICANTS_SHA],
            "evidence": [
                "data/source_registry/verified_primary_pages.csv",
                "data/source_registry/source_series_inventory.csv",
                "data/publication/multi_prefecture_pilot.json",
                "docs/sources/fermo-operational-check-2026-09-19.md",
            ],
            "last_completed_coverage_stage": "VALIDATED",
            "unresolved_issue": ["Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure."],
            "actionable_issue": False,
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def patch_tests_and_catalog() -> None:
    path = ROOT / "data/catalog.csv"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, "verified-primary-page,57,", "verified-primary-page,58,", "catalog verified pages")
    text = replace_once(text, "source_series,112,", "source_series,114,", "catalog source series")
    path.write_text(text, encoding="utf-8")

    path = ROOT / "tests/test_source_registry.py"
    text = replace_once(path.read_text(encoding="utf-8"), "assert len(pages) == 57", "assert len(pages) == 58", "source registry test")
    path.write_text(text, encoding="utf-8")

    path = ROOT / "tests/test_source_population_coverage.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, 'assert report["verified_authority_count"] == 57', 'assert report["verified_authority_count"] == 58', "coverage authority count")
    text = replace_once(text, 'assert report["register_scope_count"] == 59', 'assert report["register_scope_count"] == 60', "coverage register count")
    text = replace_once(text, 'assert report["complete_register_scope_count"] == 59', 'assert report["complete_register_scope_count"] == 60', "coverage complete count")
    text = replace_once(text, '("bari", "udine", "crotone", "cuneo")', '("bari", "udine", "crotone", "cuneo", "fermo")', "coverage authority tuple")
    path.write_text(text, encoding="utf-8")

    path = ROOT / "tests/public_portal_browser.cjs"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, "      assert.ok(labels.includes('White List ordinaria · Prefettura di Cuneo'));\n", "      assert.ok(labels.includes('White List ordinaria · Prefettura di Cuneo'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Fermo'));\n", "browser label")
    text = replace_once(text, "      assert.equal(stats.total,63925);", "      assert.equal(stats.total,64174);", "browser total")
    text = replace_once(text, "'chieti','cremona','cuneo'].includes(r.authority_key)", "'chieti','cremona','cuneo','fermo'].includes(r.authority_key)", "browser baseline exclusion")
    anchor = "      assert.equal(cuneo.filter(r=>r.source_key==='cuneo-listed'&&!r.observed_listing_date&&r.source_fields.listing_date_raw_variants.length>1).length,1);\n"
    addition = """      const fermo=registry.records.filter(r=>r.authority_key==='fermo');
      assert.equal(fermo.length,249);
      assert.equal(fermo.filter(r=>r.source_key==='fermo-listed').length,174);
      assert.equal(fermo.filter(r=>r.source_key==='fermo-applicants').length,75);
      assert.deepEqual(statusCounts(fermo),{listed:97,pending:75,renewal_update_in_progress:77});
      assert.equal(new Set(fermo.map(r=>r.record_locator)).size,249);
      assert.equal(fermo.filter(r=>r.identifiers.length>0).length,233);
      assert.equal(fermo.filter(r=>r.identifier_field_raw&&r.identifiers.length===0).length,16);
      assert.equal(fermo.filter(r=>r.source_key==='fermo-listed'&&!r.observed_listing_date&&r.source_fields.malformed_date_pairs.length===1).length,1);
      assert.equal(fermo.filter(r=>r.source_key==='fermo-applicants'&&!r.application_date&&r.source_fields.malformed_date_pairs.length===1).length,1);
"""
    text = replace_once(text, anchor, anchor + addition, "browser Fermo assertions")
    path.write_text(text, encoding="utf-8")


def write_doc() -> None:
    path = ROOT / "docs/sources/fermo-operational-check-2026-09-19.md"
    path.write_text(
        f"""# Fermo White List operational check — 19 September 2026

## Official publication surface

The current official Prefettura di Fermo page positively exposes two separate populations: **Elenco di imprese iscritte alla White list al 22 maggio 2026** and **Elenco di imprese richiedenti iscrizione alla White list al 22 maggio 2026**. Both resources are XLSX attachments. Applicant completeness is therefore based on positive official evidence, not inferred from failed discovery.

- Listed XLSX: `{LISTED_URL}` — SHA-256 `{LISTED_SHA}`. Two independent cache-bypassed captures on 19 September 2026 were byte-identical.
- Applicant XLSX: `{APPLICANTS_URL}` — SHA-256 `{APPLICANTS_SHA}`. Two independent cache-bypassed captures on 19 September 2026 were byte-identical.

The edition reference date is **22 May 2026**, taken from the explicit official attachment labels. The 19 September date is only the verification/capture date.

## Reviewed parser boundary

The listed workbook has one sheet (`Foglio1`) and a reviewed physical shape of 400 rows × 12 columns. Styled trailing ordinal-only cells are not company observations. The company boundary is **174 observations**, source ordinals 1–176 with 105 and 121 absent: **97 listed** and **77 renewal/update in progress**. Structured identifier coverage is 163/174; eleven malformed numeric identifiers remain raw-only. One malformed listing-date token, `28/11/204`, remains raw with no canonical date inferred.

The applicant workbook has one sheet and a reviewed physical shape of 267 rows × 15 columns. Its company boundary is **75 pending observations**, source ordinals 1–76 with 38 absent. Structured identifier coverage is 70/75; five malformed numeric identifiers remain raw-only. The raw application-date token `46092` is retained without conversion or inference.

Activity cells expose statutory section codes (`Sez. I` … `Sez. X`); the parser preserves only explicitly observed codes and fails closed on an unknown vocabulary.

## Publication decision

Both official sources are kept as separate source series under register `fermo-ordinary`, approved by exact raw SHA-256. The combined public candidate contributes **249 observations**. Canonical hosted-database integration and independent durable-evidence verification remain separate governance concerns and are not asserted by this expansion.
""",
        encoding="utf-8",
    )


def write_public_pages_candidate() -> None:
    path = ROOT / ".github/workflows/public-pages.yml"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, "      - 'src/white_list_archive/parsers/cuneo_positioned.py'\n", "      - 'src/white_list_archive/parsers/cuneo_positioned.py'\n      - 'src/white_list_archive/parsers/fermo_openxml.py'\n", "public workflow parser path")
    text = replace_once(text, "assert reg['meta']['record_count'] == 63925", "assert reg['meta']['record_count'] == 64174", "public workflow record count")
    text = replace_once(text, "'chieti','cremona','cuneo'}", "'chieti','cremona','cuneo','fermo'}", "public workflow authority set")
    text = replace_once(text, "'chieti-ordinary','cremona-ordinary','cuneo-ordinary'", "'chieti-ordinary','cremona-ordinary','cuneo-ordinary','fermo-ordinary'", "public workflow register set")
    text = replace_once(text, "assert reg['meta']['authority_count'] == 57", "assert reg['meta']['authority_count'] == 58", "public workflow authority count")
    text = replace_once(text, "assert reg['meta']['register_count'] == 59", "assert reg['meta']['register_count'] == 60", "public workflow register count")
    text = replace_once(text, "assert pref['meta']['published_count'] == 57", "assert pref['meta']['published_count'] == 58", "public workflow published count")
    text = replace_once(text, "assert pref['meta']['mapped_count'] == 57", "assert pref['meta']['mapped_count'] == 58", "public workflow mapped count")
    anchor = "          assert len({r['record_locator'] for r in cuneo_records}) == 516\n"
    addition = """          fermo = [x for x in pref['prefectures'] if x['authority_key'] == 'fermo']
          assert len(fermo) == 1 and fermo[0]['mapped'] and fermo[0]['published'] and fermo[0]['series_count'] == 2
          fermo_records = [r for r in reg['records'] if r['authority_key'] == 'fermo']
          assert len(fermo_records) == 249
          assert sum(r['source_key'] == 'fermo-listed' for r in fermo_records) == 174
          assert sum(r['source_key'] == 'fermo-applicants' for r in fermo_records) == 75
          assert sum(r['source_status'] == 'listed' for r in fermo_records) == 97
          assert sum(r['source_status'] == 'pending' for r in fermo_records) == 75
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in fermo_records) == 77
          assert sum(bool(r['identifiers']) for r in fermo_records) == 233
          assert len({r['record_locator'] for r in fermo_records}) == 249
"""
    text = replace_once(text, anchor, anchor + addition, "public workflow Fermo assertions")
    candidate = ROOT / "tmp/fermo-public-pages-candidate.yml"
    candidate.parent.mkdir(exist_ok=True)
    candidate.write_text(text, encoding="utf-8")


def main() -> None:
    patch_parser()
    patch_registry()
    patch_publication_config()
    patch_source_registry()
    patch_coverage()
    patch_tests_and_catalog()
    write_doc()
    write_public_pages_candidate()


if __name__ == "__main__":
    main()
