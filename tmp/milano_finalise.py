from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_RUN = "35058960470"
COMBINED_SHA = "350e995ac06fc9525c1bd21cc2e2ad8b69224e4dd603e530a65553c21f44b044"
COMOTER_NOTE = "Misura di prevenzione collaborativa ex art. 94 bis D.lgs.159/2011 in data 18/04/2024, per la durata di un anno"


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one replacement in {path}: {old!r}; found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def promote_monitoring() -> None:
    path = ROOT / "data/monitoring/national_coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    matches = [item for item in data["prefectures"] if item.get("authority_key") == "milano"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one Milano monitoring entry, found {len(matches)}")
    item = matches[0]
    expected_true = (
        "source_verified",
        "current_edition_identified",
        "capture_implemented",
        "parser_implemented",
        "parser_validated",
        "company_observations_loaded",
        "public_export_enabled",
        "population_scopes_complete",
    )
    for key in expected_true:
        if item.get(key) is not True:
            raise RuntimeError(f"Milano monitoring pre-state drift: {key}={item.get(key)!r}")
    if item.get("canonical_integration_validated") is not False:
        raise RuntimeError("Milano canonical integration was not in the expected pre-promotion state")
    if item.get("durable_evidence_verified") is not False:
        raise RuntimeError("Milano durable evidence state changed unexpectedly")
    if item.get("known_content_sha256") != [COMBINED_SHA]:
        raise RuntimeError(f"Unexpected Milano content hash state: {item.get('known_content_sha256')!r}")
    item["canonical_integration_validated"] = True
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def finalise_source_note() -> None:
    path = ROOT / "docs/sources/milano-operational-check-2026-09-16.md"
    old = (
        "National publication remains a separate transaction and must prove the actual national registry denominators before `canonical_integration_validated` can be promoted.\n\n"
        "`durable_evidence_verified` must remain false unless the project independently establishes the governed durable-evidence requirement; temporary workflow captures do not satisfy that requirement.\n"
    )
    new = (
        "National publication was then exercised as a separate fail-closed transaction in GitHub Actions run `35058960470`. The actual national build completed successfully and validated **54,180 records / 47 published Prefectures / 48 published registers / 47 mapped Prefectures**, with exactly **2,614 Milano observations / 2,614 distinct record locators** and **48/48 register scopes source-complete**. The transaction rechecked the exact production diff before committing the integration, so `canonical_integration_validated` is now **true** for Milano.\n\n"
        "`durable_evidence_verified` remains **false** unless the project independently establishes the governed durable-evidence requirement; temporary workflow captures do not satisfy that requirement.\n"
    )
    replace_exact(path, old, new)


def update_pages_gate() -> None:
    path = ROOT / ".github/workflows/public-pages.yml"
    replace_exact(
        path,
        "      - 'src/white_list_archive/parsers/sassari_openxml.py'\n      - 'pyproject.toml'\n",
        "      - 'src/white_list_archive/parsers/sassari_openxml.py'\n      - 'src/white_list_archive/parsers/milano_webapp.py'\n      - 'pyproject.toml'\n",
    )
    replace_exact(path, "          assert reg['meta']['record_count'] == 51566\n", "          assert reg['meta']['record_count'] == 54180\n")
    replace_exact(path, "'potenza','sassari'}\n", "'potenza','sassari','milano'}\n")
    replace_exact(path, "'potenza-ordinary','sassari-ordinary'\n", "'potenza-ordinary','sassari-ordinary','milano-ordinary'\n")
    replace_exact(path, "          assert reg['meta']['authority_count'] == 46\n", "          assert reg['meta']['authority_count'] == 47\n")
    replace_exact(path, "          assert reg['meta']['register_count'] == 47\n", "          assert reg['meta']['register_count'] == 48\n")
    replace_exact(path, "          assert pref['meta']['published_count'] == 46\n", "          assert pref['meta']['published_count'] == 47\n")
    marker = (
        "          column_swap = [r for r in sassari_records if r['name'] == 'DE.SCA.RI DEL GEOM. CALIA GIANLUCA']\n"
        "          assert len(column_swap) == 1\n"
        "          assert column_swap[0]['registered_office'] == 'CLAGLC74B11E736M'\n"
        "          assert column_swap[0]['identifier_field_raw'] == 'OLBIA'\n"
    )
    block = marker + f"""          milano = [x for x in pref['prefectures'] if x['authority_key'] == 'milano']
          assert len(milano) == 1 and milano[0]['mapped'] and milano[0]['published'] and milano[0]['series_count'] == 1
          milano_records = [r for r in reg['records'] if r['authority_key'] == 'milano']
          assert len(milano_records) == 2614
          assert all(r['source_key'] == 'milano-combined' for r in milano_records)
          assert sum(r['source_status'] == 'listed' for r in milano_records) == 940
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in milano_records) == 516
          assert sum(r['source_status'] == 'pending' for r in milano_records) == 1158
          assert len({{r['record_locator'] for r in milano_records}}) == 2614
          assert sum(bool(r['identifiers']) for r in milano_records) == 2614
          assert all(r['requested_activities'] for r in milano_records)
          assert sum(bool(r['application_date']) for r in milano_records) == 1158
          assert sum(bool(r['observed_listing_date']) for r in milano_records) == 940
          assert sum(bool(r['observed_expiry_date']) for r in milano_records) == 940
          assert max(r['application_date'] for r in milano_records if r['application_date']) == '2026-09-15'
          noted_milano = [r for r in milano_records if r['source_fields']['notes']]
          assert len(noted_milano) == 1 and noted_milano[0]['name'] == 'COMOTER SRL'
          assert noted_milano[0]['source_fields']['notes'] == [{COMOTER_NOTE!r}]
          assert all(len(r['source_fields']['sections']) == len(r['source_fields']['physical_locators']) for r in milano_records)
          assert all(
              r['source_fields']['application_date_raw_variants']
              if r['source_status'] == 'pending'
              else not r['source_fields']['application_date_raw_variants']
              for r in milano_records
          )
          assert all(
              r['source_fields']['listing_date_raw_variants'] and r['source_fields']['expiry_date_raw_variants']
              if r['source_status'] == 'listed'
              else not r['source_fields']['listing_date_raw_variants'] and not r['source_fields']['expiry_date_raw_variants']
              for r in milano_records
          )
          assert all(
              r['source_fields']['in_aggiornamento'] == 'IN AGGIORNAMENTO'
              if r['source_status'] == 'renewal_update_in_progress'
              else r['source_fields']['in_aggiornamento'] == ''
              for r in milano_records
          )
"""
    replace_exact(path, marker, block)


def update_browser_gate() -> None:
    path = ROOT / "tests/public_portal_browser.cjs"
    replace_exact(
        path,
        "      assert.ok(labels.includes('White List — Prefettura di Sassari · Prefettura di Sassari'));\n",
        "      assert.ok(labels.includes('White List — Prefettura di Sassari · Prefettura di Sassari'));\n      assert.ok(labels.includes('White List — Prefettura di Milano · Prefettura di Milano'));\n",
    )
    replace_exact(path, "      assert.equal(stats.total,51566);\n", "      assert.equal(stats.total,54180);\n")
    replace_exact(path, "'potenza','sassari'].includes(r.authority_key)", "'potenza','sassari','milano'].includes(r.authority_key)")
    marker = (
        "      const descari=sassari.filter(r=>r.name==='DE.SCA.RI DEL GEOM. CALIA GIANLUCA');\n"
        "      assert.equal(descari.length,1);\n"
        "      assert.equal(descari[0].registered_office,'CLAGLC74B11E736M');\n"
        "      assert.equal(descari[0].identifier_field_raw,'OLBIA');\n"
    )
    block = marker + f"""      const milano=registry.records.filter(r=>r.authority_key==='milano');
      assert.equal(milano.length,2614);
      assert.equal(milano.filter(r=>r.source_key==='milano-combined').length,2614);
      assert.deepEqual(statusCounts(milano),{{listed:940,pending:1158,renewal_update_in_progress:516}});
      assert.equal(new Set(milano.map(r=>r.record_locator)).size,2614);
      assert.equal(milano.filter(r=>r.identifiers.length>0).length,2614);
      assert.ok(milano.every(r=>r.requested_activities.length>0));
      assert.equal(milano.filter(r=>r.application_date!=='').length,1158);
      assert.equal(milano.filter(r=>r.observed_listing_date!=='').length,940);
      assert.equal(milano.filter(r=>r.observed_expiry_date!=='').length,940);
      assert.equal(Math.max(...milano.filter(r=>r.application_date).map(r=>Date.parse(r.application_date))),Date.parse('2026-09-15'));
      assert.ok(milano.every(r=>Array.isArray(r.source_fields.notes)));
      const notedMilano=milano.filter(r=>r.source_fields.notes.length>0);
      assert.equal(notedMilano.length,1);
      assert.equal(notedMilano[0].name,'COMOTER SRL');
      assert.deepEqual(notedMilano[0].source_fields.notes,[{COMOTER_NOTE!r}]);
      assert.ok(milano.every(r=>r.source_fields.sections.length===r.source_fields.physical_locators.length));
"""
    replace_exact(path, marker, block)


def remove_temporary_machinery() -> None:
    for rel in (
        ".github/workflows/milano-national-candidate.yml",
        ".github/workflows/milano-source-probe.yml",
        ".github/workflows/milano-finalise.yml",
        "tmp/fix_operations_priority_test.py",
        "tmp/milano_integrate_candidate.py",
        "tmp/milano_finalise.py",
    ):
        path = ROOT / rel
        if not path.exists():
            raise RuntimeError(f"Expected temporary file missing before cleanup: {rel}")
        path.unlink()


def main() -> None:
    promote_monitoring()
    finalise_source_note()
    update_pages_gate()
    update_browser_gate()
    remove_temporary_machinery()
    print(f"Milano production finalisation prepared after successful candidate run {CANDIDATE_RUN}")


if __name__ == "__main__":
    main()
