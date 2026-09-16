from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_RUN = "35058960470"
CURRENT_AUDIT_RUN = "35107286700"
OLD_COMBINED_SHA = "350e995ac06fc9525c1bd21cc2e2ad8b69224e4dd603e530a65553c21f44b044"
COMBINED_SHA = "1d84bda8cdcd7252fd2580af31489b0cc4361801a417125fbfade03c584bb474"
REGISTERED_SHA = "4509948e4baf91ed5c92bd5940a2fca1cd5f9a6fd21f553c4864e68735e36608"
COMOTER_NOTE = "Misura di prevenzione collaborativa ex art. 94 bis D.lgs.159/2011 in data 18/04/2024, per la durata di un anno"
CURRENT_SECTOR_ROWS = 4218
CURRENT_RECORDS = 2617
CURRENT_STATUS_COUNTS = {
    "listed": 941,
    "renewal_update_in_progress": 515,
    "pending": 1161,
}
CURRENT_NATIONAL_RECORDS = 54182


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one replacement in {path}: {old!r}; found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def approve_current_source_boundary() -> None:
    config_path = ROOT / "data/publication/multi_prefecture_pilot.json"
    data = json.loads(config_path.read_text(encoding="utf-8"))
    matches = [item for item in data["sources"] if item.get("source_key") == "milano-combined"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one Milano publication source, found {len(matches)}")
    source = matches[0]
    expected = {
        "parser": "milano_combined",
        "authority_key": "milano",
        "register_key": "milano-ordinary",
        "population_scope": "listed_and_applicant",
        "reference_date": "2026-09-16",
        "resource_url": "https://whitelist.prefmi.it/elenco/elenco.php",
        "sha256": OLD_COMBINED_SHA,
        "expected_sector_rows": 4214,
        "expected_source_rows": 2614,
    }
    for key, value in expected.items():
        if source.get(key) != value:
            raise RuntimeError(f"Milano publication pre-state drift: {key}={source.get(key)!r}; expected {value!r}")
    source["sha256"] = COMBINED_SHA
    source["expected_sector_rows"] = CURRENT_SECTOR_ROWS
    source["expected_source_rows"] = CURRENT_RECORDS
    source["notes"] = (
        "The current mutable combined operational table was revalidated later on 16 September 2026 after the first same-day capture drifted. "
        "Two independent no-cache GETs were byte-identical at 971,900 bytes with SHA-256 "
        f"{COMBINED_SHA}. The reviewed current boundary contains 4,218 statutory-sector rows and 2,617 logical observations: "
        "941 listed, 515 renewal/update in progress and 1,161 pending. All 2,617 identifiers are strict and every observation has explicit statutory activity coverage. "
        "Three pending observations are source-explicitly dated 16 September 2026: G.B.C. INDUSTRIAL TOOLS SPA (07639230155), "
        "VERNIA SRL (11967860153) and CARBON SUD TRASPORTI E SERVIZI S.R.L. (14302100962). "
        "The registered-only sibling was independently captured twice at 559,326 bytes with SHA-256 "
        f"{REGISTERED_SHA}; its 1,456-company identity set exactly matches the combined table's non-pending identity set. "
        "The sibling is not co-ingested, because it is an overlapping presentation of the same non-pending population and carries some note/status presentation differences."
    )
    config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    parser_path = ROOT / "src/white_list_archive/parsers/milano_webapp.py"
    replace_exact(parser_path, "_EXPECTED_SECTOR_ROWS = 4214\n", f"_EXPECTED_SECTOR_ROWS = {CURRENT_SECTOR_ROWS}\n")
    replace_exact(parser_path, "_EXPECTED_RECORDS = 2614\n", f"_EXPECTED_RECORDS = {CURRENT_RECORDS}\n")
    replace_exact(
        parser_path,
        '_EXPECTED_STATUS_COUNTS = {\n    "listed": 940,\n    "renewal_update_in_progress": 516,\n    "pending": 1158,\n}\n',
        '_EXPECTED_STATUS_COUNTS = {\n    "listed": 941,\n    "renewal_update_in_progress": 515,\n    "pending": 1161,\n}\n',
    )
    replace_exact(parser_path, "_EXPECTED_IDENTIFIER_COVERAGE = 2614\n", f"_EXPECTED_IDENTIFIER_COVERAGE = {CURRENT_RECORDS}\n")


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
    if item.get("known_content_sha256") != [OLD_COMBINED_SHA]:
        raise RuntimeError(f"Unexpected Milano content hash state: {item.get('known_content_sha256')!r}")
    item["known_content_sha256"] = [COMBINED_SHA]
    item["canonical_integration_validated"] = True
    item["last_successful_source_check_at"] = "2026-09-16T14:16:19Z"
    item["last_attempted_source_check_at"] = "2026-09-16T14:16:19Z"
    item["last_content_change_at"] = "2026-09-16T14:16:19Z"
    item["monitoring_status"] = "CURRENT"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def finalise_source_note() -> None:
    path = ROOT / "docs/sources/milano-operational-check-2026-09-16.md"
    note = f'''# Milano White List — operational source check (16 September 2026)

## Scope and conclusion

This check resolves the Milano source-population question using positive current official evidence. The Prefettura di Milano operates a dedicated White List application at `whitelist.prefmi.it` in addition to the Ministry landing page. The application exposes a combined public table at `https://whitelist.prefmi.it/elenco/elenco.php` containing registered-company, renewal/update and first-time applicant observations. The applicant population is therefore treated as positively published; this conclusion is not inferred from search failure or from the existence of an application-submission route.

The publication source is the combined current table, not a union with the registered-only sibling. The sibling contains exactly the same current non-pending company identity set and is retained as corroborating source evidence only. Co-ingestion would duplicate observations and could create conflicting note/status presentations.

## Official surfaces verified

- Ministry landing page: `https://prefettura.interno.gov.it/it/prefetture/milano/evidenza/white-list`.
- Dedicated application entry point: `https://whitelist.prefmi.it/elenco/inizio.php`.
- Combined operational table: `https://whitelist.prefmi.it/elenco/elenco.php`.
- Registered-company sibling view: `https://whitelist.prefmi.it/elenco/elenco_iscritte.php`.

The Ministry page positively describes the White List consultation and registration/renewal route. The dedicated application entry point identifies both an `ELENCO IMPRESE RICHIEDENTI ISCRIZIONE NELLA WHITE LIST PROVINCIALE` and an `ELENCO IMPRESE ISCRITTE NELLA WHITE LIST PROVINCIALE`. The combined operational table itself publishes source-explicit `RICHIESTA ISCRIZIONE (dd/mm/yyyy)` rows.

## Same-day mutable-source transition and byte identity

The source is a mutable current web application. An earlier independently stable capture on 16 September contained 4,214 sector rows and 2,614 logical observations at SHA-256 `{OLD_COMBINED_SHA}`. Before production finalisation, the fail-closed national build detected that the official source had changed. The project did not relax the denominator or substitute the new hash.

Current-source audit GitHub Actions run `{CURRENT_AUDIT_RUN}` then captured both official tables twice with no-cache headers and independently validated their structure and semantics. The paired captures were byte-identical:

- combined table: **971,900 bytes**, SHA-256 **`{COMBINED_SHA}`**;
- registered-company sibling: **559,326 bytes**, SHA-256 **`{REGISTERED_SHA}`**.

The current combined source contains **10** statutory tables, **4,218** physical sector-membership rows and **2,617** conservative logical observations. The registered-only sibling contains **1,456** logical identities, and that identity set exactly equals the **1,456 non-pending identities** in the combined table. No pending combined identity appears in the sibling.

Because both official resources are mutable, **2026-09-16 is a capture/reference boundary only**. It is not treated as an inferred application, decision, registration, expiry or legal-effect date for any company. Publication is byte-pinned to the reviewed current combined capture and fails closed again on further drift.

## Current parser boundary

The current combined boundary is:

- **10** section tables;
- **4,218** source sector-membership rows;
- **2,617** logical observations;
- **2,617/2,617** strict source identifiers, with one logical observation per identifier;
- **2,617/2,617** observations with at least one source-explicit statutory activity section;
- **941** `listed` observations;
- **515** `renewal_update_in_progress` observations;
- **1,161** `pending` observations.

All **1,161** pending observations have explicit application dates. All **941** listed observations have explicit listing and expiry dates. No date is manufactured for update rows. The latest positively observed applicant date is **16 September 2026**. The current source explicitly contains these three pending observations dated 16 September:

- G.B.C. INDUSTRIAL TOOLS SPA — `07639230155`;
- VERNIA SRL — `11967860153`;
- CARBON SUD TRASPORTI E SERVIZI S.R.L. — `14302100962`.

Relative to the first same-day capture, the aggregate current boundary is +3 logical observations and +4 sector rows; the status distribution moves from 940/516/1,158 to 941/515/1,161. The retained first-capture evidence is sufficient to prove the former approved aggregate and hash but does not preserve the old mutable response body, so the individual identity behind the aggregate one-row `renewal_update_in_progress` to `listed` shift is not reconstructed here. No identity or legal effect is inferred to fill that evidential gap.

Repeated section membership is retained as requested-activity provenance rather than published as duplicate company observations. Record locators use the source-published identifier and capture reference date rather than mutable HTML row position.

## Source-faithful treatment

No legal status is inferred beyond the source-explicit table semantics. In particular:

- `RICHIESTA ISCRIZIONE (...)` is mapped only to `pending`;
- `IN AGGIORNAMENTO` is mapped only to `renewal_update_in_progress`;
- rows with valid listing and expiry dates are mapped to `listed`;
- any previously unseen status/date pattern fails closed;
- company names, registered offices and identifiers are not repaired from external information;
- repeated sector memberships are grouped only under the reviewed identity/status/date rule.

One logical observation, **COMOTER SRL**, carries the combined-source note `{COMOTER_NOTE}`. It is retained strictly as source provenance and does not overwrite the table's explicit current status. The registered-only sibling exposes additional note presentations for some identities; those sibling notes are not imported into the chosen combined-series observation model.

## Validation and publication gate

The current-source validation ran Milano semantic tests and the full repository suite, required two byte-identical no-cache captures of each official table, independently audited all ten table headings/header geometry, strict identifiers, source status/date grammar and conservative grouping, verified the combined/non-pending identity set against the registered sibling, and rechecked positive Ministry/application-entry evidence.

The parser remains fail-closed on table count, section headings, expanded header geometry, row width, identifier syntax, unreviewed status/date patterns, logical-record denominator, status counts, identifier coverage and note denominator. The first production candidate run `{CANDIDATE_RUN}` had validly demonstrated the earlier source edition before subsequent official-source drift. The current production finalisation therefore revalidates the complete national boundary from the now-reviewed current source instead of treating that historical candidate as sufficient.

On successful current national build, the expected public boundary is **{CURRENT_NATIONAL_RECORDS:,} records / 47 published Prefectures / 48 published registers / 47 mapped Prefectures**, with exactly **{CURRENT_RECORDS:,} Milano observations / {CURRENT_RECORDS:,} distinct locators** and **48/48 register scopes source-complete**. `canonical_integration_validated` is promoted only inside the same production transaction and is committed only if those gates pass.

`durable_evidence_verified` remains **false** unless the project independently establishes the governed durable-evidence requirement; temporary workflow captures do not satisfy that requirement.
'''
    path.write_text(note, encoding="utf-8")


def update_pages_gate() -> None:
    path = ROOT / ".github/workflows/public-pages.yml"
    replace_exact(
        path,
        "      - 'src/white_list_archive/parsers/sassari_openxml.py'\n      - 'pyproject.toml'\n",
        "      - 'src/white_list_archive/parsers/sassari_openxml.py'\n      - 'src/white_list_archive/parsers/milano_webapp.py'\n      - 'pyproject.toml'\n",
    )
    replace_exact(path, "          assert reg['meta']['record_count'] == 51565\n", "          assert reg['meta']['record_count'] == 54182\n")
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
          assert len(milano_records) == 2617
          assert all(r['source_key'] == 'milano-combined' for r in milano_records)
          assert sum(r['source_status'] == 'listed' for r in milano_records) == 941
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in milano_records) == 515
          assert sum(r['source_status'] == 'pending' for r in milano_records) == 1161
          assert len({{r['record_locator'] for r in milano_records}}) == 2617
          assert sum(bool(r['identifiers']) for r in milano_records) == 2617
          assert all(r['requested_activities'] for r in milano_records)
          assert sum(bool(r['application_date']) for r in milano_records) == 1161
          assert sum(bool(r['observed_listing_date']) for r in milano_records) == 941
          assert sum(bool(r['observed_expiry_date']) for r in milano_records) == 941
          assert max(r['application_date'] for r in milano_records if r['application_date']) == '2026-09-16'
          pending_16 = {{(r['name'], r['identifier_field_raw']) for r in milano_records if r['source_status'] == 'pending' and r['application_date'] == '2026-09-16'}}
          assert pending_16 == {{
              ('G.B.C. INDUSTRIAL TOOLS SPA', '07639230155'),
              ('VERNIA SRL', '11967860153'),
              ('CARBON SUD TRASPORTI E SERVIZI S.R.L.', '14302100962'),
          }}
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
    replace_exact(path, "      assert.equal(stats.total,51565);\n", "      assert.equal(stats.total,54182);\n")
    replace_exact(path, "'potenza','sassari'].includes(r.authority_key)", "'potenza','sassari','milano'].includes(r.authority_key)")
    marker = (
        "      const descari=sassari.filter(r=>r.name==='DE.SCA.RI DEL GEOM. CALIA GIANLUCA');\n"
        "      assert.equal(descari.length,1);\n"
        "      assert.equal(descari[0].registered_office,'CLAGLC74B11E736M');\n"
        "      assert.equal(descari[0].identifier_field_raw,'OLBIA');\n"
    )
    block = marker + f"""      const milano=registry.records.filter(r=>r.authority_key==='milano');
      assert.equal(milano.length,2617);
      assert.equal(milano.filter(r=>r.source_key==='milano-combined').length,2617);
      assert.deepEqual(statusCounts(milano),{{listed:941,pending:1161,renewal_update_in_progress:515}});
      assert.equal(new Set(milano.map(r=>r.record_locator)).size,2617);
      assert.equal(milano.filter(r=>r.identifiers.length>0).length,2617);
      assert.ok(milano.every(r=>r.requested_activities.length>0));
      assert.equal(milano.filter(r=>r.application_date!=='').length,1161);
      assert.equal(milano.filter(r=>r.observed_listing_date!=='').length,941);
      assert.equal(milano.filter(r=>r.observed_expiry_date!=='').length,941);
      assert.equal(Math.max(...milano.filter(r=>r.application_date).map(r=>Date.parse(r.application_date))),Date.parse('2026-09-16'));
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
    approve_current_source_boundary()
    promote_monitoring()
    finalise_source_note()
    update_pages_gate()
    update_browser_gate()
    remove_temporary_machinery()
    print(
        "Milano production finalisation prepared from reviewed current source: "
        f"audit_run={CURRENT_AUDIT_RUN} records={CURRENT_RECORDS} national_target={CURRENT_NATIONAL_RECORDS}"
    )


if __name__ == "__main__":
    main()
