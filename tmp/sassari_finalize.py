from __future__ import annotations

import argparse
import json
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def coverage_and_note() -> None:
    coverage_path = Path("data/monitoring/national_coverage.json")
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    matches = [row for row in coverage["rows"] if row.get("authority_key") == "sassari"]
    if len(matches) != 1:
        raise SystemExit(f"expected one Sassari coverage row, found {len(matches)}")
    sassari = matches[0]
    expected = {
        "source_verified": True,
        "current_edition_identified": True,
        "capture_implemented": True,
        "parser_implemented": True,
        "parser_validated": True,
        "company_observations_loaded": True,
        "public_export_enabled": True,
        "population_scopes_complete": True,
        "canonical_integration_validated": False,
        "durable_evidence_verified": False,
        "latest_source_reference_date": "2026-08-31",
    }
    for key, value in expected.items():
        if sassari.get(key) != value:
            raise SystemExit(f"unexpected Sassari coverage state for {key}: {sassari.get(key)!r} != {value!r}")
    sassari["canonical_integration_validated"] = True
    coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    note_path = Path("docs/sources/sassari-operational-check-2026-09-15.md")
    note = note_path.read_text(encoding="utf-8")
    note = replace_once(
        note,
        "- company observations loaded into a national candidate: **not yet**;\n- `canonical_integration_validated`: **false**;\n- `durable_evidence_verified`: **false**.\n\nThe latter two flags must not be promoted by this source review alone. Canonical/public integration requires a successful national candidate build and its denominator gates. Independent durable-evidence verification remains a separate infrastructure/evidence concern.",
        "- company observations loaded into a national candidate: **yes** — the successful candidate build validated **51,566** national records, **46** published Prefectures, **47** published registers and **47** mapped Prefectures, including exactly **478** Sassari observations and **478** distinct locators;\n- `canonical_integration_validated`: **true**;\n- `durable_evidence_verified`: **false**.\n\nThe canonical/public integration flag is promoted only because the national candidate build, denominator checks, exact production-transaction recheck and integration commit all completed successfully. Independent durable-evidence verification remains a separate infrastructure/evidence concern and is not inferred from publication success.",
        "source note validation state",
    )
    note_path.write_text(note, encoding="utf-8")


def pages_gate() -> None:
    path = Path(".github/workflows/public-pages.yml")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "      - 'src/white_list_archive/parsers/potenza_webapp.py'\n",
        "      - 'src/white_list_archive/parsers/potenza_webapp.py'\n      - 'src/white_list_archive/parsers/sassari_openxml.py'\n",
        "Pages parser path",
    )
    for old, new, label in (
        ("assert reg['meta']['record_count'] == 51088", "assert reg['meta']['record_count'] == 51566", "Pages record count"),
        ("assert reg['meta']['authority_count'] == 45", "assert reg['meta']['authority_count'] == 46", "Pages authority count"),
        ("assert reg['meta']['register_count'] == 46", "assert reg['meta']['register_count'] == 47", "Pages register count"),
        ("assert pref['meta']['published_count'] == 45", "assert pref['meta']['published_count'] == 46", "Pages published count"),
    ):
        text = replace_once(text, old, new, label)

    authority_line = next((line for line in text.splitlines() if "assert set(reg['meta']['authority_counts'])" in line), None)
    if authority_line is None or not authority_line.endswith("'potenza'}") or "'sassari'" in authority_line:
        raise SystemExit(f"unexpected Pages authority set: {authority_line!r}")
    text = replace_once(text, authority_line, authority_line[:-1] + ",'sassari'}", "Pages authority set")

    if text.count("'potenza-ordinary'\n") != 1 or "'sassari-ordinary'" in text:
        raise SystemExit("unexpected Pages register-set boundary")
    text = text.replace("'potenza-ordinary'\n", "'potenza-ordinary','sassari-ordinary'\n", 1)

    marker = "          assert gap[0]['source_fields']['in_aggiornamento'] == '1'\n"
    block = """          sassari = [x for x in pref['prefectures'] if x['authority_key'] == 'sassari']
          assert len(sassari) == 1 and sassari[0]['mapped'] and sassari[0]['published'] and sassari[0]['series_count'] == 1
          sassari_records = [r for r in reg['records'] if r['authority_key'] == 'sassari']
          assert len(sassari_records) == 478
          assert all(r['source_key'] == 'sassari-combined' for r in sassari_records)
          assert sum(r['source_status'] == 'listed' for r in sassari_records) == 335
          assert sum(r['source_status'] == 'pending' for r in sassari_records) == 129
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in sassari_records) == 12
          assert sum(r['source_status'] == 'expired_observed' for r in sassari_records) == 1
          assert sum(r['source_status'] == 'other_or_unknown' for r in sassari_records) == 1
          assert len({r['record_locator'] for r in sassari_records}) == 478
          assert sum(bool(r['identifiers']) for r in sassari_records) == 472
          assert sum(bool(r['identifier_field_raw']) and not r['identifiers'] for r in sassari_records) == 6
          assert all(r['requested_activities'] for r in sassari_records)
          assert all(r['parser_name'] == 'sassari_combined' and r['parser_version'] == '1' for r in sassari_records)
          assert all(r['source_fields']['physical_locator'].startswith('Foglio1!') for r in sassari_records)
          malformed_date = [r for r in sassari_records if r['name'] == 'M.I.A. SRL']
          assert len(malformed_date) == 1
          assert malformed_date[0]['source_fields']['application_date_raw'] == '129.01.2025'
          assert malformed_date[0]['application_date'] == ''
          column_swap = [r for r in sassari_records if r['name'] == 'DE.SCA.RI DEL GEOM. CALIA GIANLUCA']
          assert len(column_swap) == 1
          assert column_swap[0]['registered_office'] == 'CLAGLC74B11E736M'
          assert column_swap[0]['identifier_field_raw'] == 'OLBIA'
"""
    text = replace_once(text, marker, marker + block, "Pages Sassari semantic block")
    path.write_text(text, encoding="utf-8")


def browser_gate() -> None:
    path = Path("tests/public_portal_browser.cjs")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "      assert.ok(labels.includes('White List ordinaria · Prefettura di Potenza'));\n",
        "      assert.ok(labels.includes('White List ordinaria · Prefettura di Potenza'));\n      assert.ok(labels.includes('White List — Prefettura di Sassari · Prefettura di Sassari'));\n",
        "browser Sassari label",
    )
    text = replace_once(text, "      assert.equal(stats.total,51088);", "      assert.equal(stats.total,51566);", "browser total")
    previous_line = next((line for line in text.splitlines() if line.lstrip().startswith("const previous=registry.records.filter")), None)
    if previous_line is None or "'potenza'].includes" not in previous_line or "'sassari'" in previous_line:
        raise SystemExit(f"unexpected browser baseline exclusion: {previous_line!r}")
    text = replace_once(text, previous_line, previous_line.replace("'potenza'].includes", "'potenza','sassari'].includes"), "browser baseline exclusions")

    marker = "      assert.equal(gap[0].source_fields.in_aggiornamento,'1');\n"
    block = """      const sassari=registry.records.filter(r=>r.authority_key==='sassari');
      assert.equal(sassari.length,478);
      assert.equal(sassari.filter(r=>r.source_key==='sassari-combined').length,478);
      assert.deepEqual(statusCounts(sassari),{expired_observed:1,listed:335,other_or_unknown:1,pending:129,renewal_update_in_progress:12});
      assert.equal(new Set(sassari.map(r=>r.record_locator)).size,478);
      assert.equal(sassari.filter(r=>r.identifiers.length>0).length,472);
      assert.equal(sassari.filter(r=>r.identifier_field_raw&&r.identifiers.length===0).length,6);
      assert.ok(sassari.every(r=>r.requested_activities.length>0));
      assert.ok(sassari.every(r=>r.parser_name==='sassari_combined'&&r.parser_version==='1'));
      assert.ok(sassari.every(r=>r.source_fields.physical_locator.startsWith('Foglio1!')));
      const mia=sassari.filter(r=>r.name==='M.I.A. SRL');
      assert.equal(mia.length,1);
      assert.equal(mia[0].source_fields.application_date_raw,'129.01.2025');
      assert.equal(mia[0].application_date,'');
      const descari=sassari.filter(r=>r.name==='DE.SCA.RI DEL GEOM. CALIA GIANLUCA');
      assert.equal(descari.length,1);
      assert.equal(descari[0].registered_office,'CLAGLC74B11E736M');
      assert.equal(descari[0].identifier_field_raw,'OLBIA');
"""
    text = replace_once(text, marker, marker + block, "browser Sassari semantic block")
    path.write_text(text, encoding="utf-8")


def cleanup() -> None:
    for filename in (
        ".github/workflows/sassari-national-candidate.yml",
        ".github/workflows/sassari-source-validation.yml",
        ".github/workflows/sassari-finalize.yml",
        "tmp/sassari_integrate_candidate.py",
        "tmp/sassari_finalize.py",
    ):
        path = Path(filename)
        if not path.exists():
            raise SystemExit(f"expected temporary file is missing: {filename}")
        path.unlink()


parser = argparse.ArgumentParser()
parser.add_argument("phase", choices=("coverage", "pages", "browser", "cleanup"))
args = parser.parse_args()
{"coverage": coverage_and_note, "pages": pages_gate, "browser": browser_gate, "cleanup": cleanup}[args.phase]()
