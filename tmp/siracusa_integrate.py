from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path('.')
LANDING = 'https://prefettura.interno.gov.it/it/prefetture/siracusa/evidenza/white-list'
LISTED_URL = 'https://prefettura.interno.gov.it/sites/default/files/10/2026-09/elenco-societa-iscritte-in-white-list-e-indicate-in-sezioni_02092026.pdf'
APPLICANT_URL = 'https://prefettura.interno.gov.it/sites/default/files/10/2026-09/societa-richiedenti-iscrizione-white-list-provinciale_31082026.pdf'
LISTED_SHA = '90e6bc87e6a3c6cfc46871473565fae8858d252e4be7787915a21978b0b963a9'
APPLICANT_SHA = 'c2e49fa6dc16da383c017b1c4ebed7c493d8013d53ea58d813fe4b4187375ba2'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected one anchor, got {count}')
    return text.replace(old, new, 1)


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def update_publication_config() -> None:
    path = ROOT / 'data/publication/multi_prefecture_pilot.json'
    config = json.loads(path.read_text(encoding='utf-8'))
    if any(source.get('authority_key') == 'siracusa' for source in config['sources']):
        raise RuntimeError('Siracusa already present in publication config')
    common = {
        'authority_key': 'siracusa',
        'authority_name': 'Prefettura di Siracusa',
        'register_key': 'siracusa-ordinary',
        'register_name': 'White List ordinaria',
        'source_page_url': LANDING,
        'approval_mode': 'raw_sha256',
        'reference_date': '2026-09-03',
        'last_source_update': '2026-09-03',
        'last_source_update_basis': "official landing reports update on 3 September 2026; source-observation boundary only, not promoted to a company legal-effect date",
    }
    config['sources'].extend([
        {
            **common,
            'source_key': 'siracusa-listed',
            'parser': 'siracusa_listed',
            'population_scope': 'listed',
            'resource_url': LISTED_URL,
            'sha256': LISTED_SHA,
            'expected_source_rows': 315,
            'notes': 'Dedicated official registered-company PDF positively exposed by the current landing page. The reviewed 81-page table contains 317 nonblank source segments and 315 company observations after exactly two approved note-only continuations are retained with their preceding company. Status boundary is 246 listed, 67 renewal/update in progress and 2 other/unknown; strict identifiers cover 312/315 and explicit expiry dates 315/315. Malformed identifiers and the two non-dispositive notes remain raw without legal inference.',
        },
        {
            **common,
            'source_key': 'siracusa-applicants',
            'parser': 'siracusa_applicants',
            'population_scope': 'applicant',
            'resource_url': APPLICANT_URL,
            'sha256': APPLICANT_SHA,
            'expected_source_rows': 104,
            'notes': 'Dedicated official applicant PDF positively exposed by the current landing page. All 104 reviewed observations are positive pending observations; strict identifiers cover 102/104 and normalised application dates 103/104. The malformed date 17.01/2024 and malformed identifier fields remain raw; annotated cells contribute only their source-explicit leading application date.',
        },
    ])
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def update_registries() -> None:
    path = ROOT / 'data/source_registry/verified_primary_pages.csv'
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle); rows = list(reader); fields = list(reader.fieldnames or [])
    if any(row['authority_key'] == 'siracusa' for row in rows):
        raise RuntimeError('Siracusa already present in verified_primary_pages')
    rows.append({'authority_key': 'siracusa', 'landing_url': LANDING, 'verification_date': '2026-09-20', 'verification_status': 'verified'})
    rows.sort(key=lambda row: row['authority_key'])
    write_csv(path, rows, fields)

    path = ROOT / 'data/source_registry/source_series_inventory.csv'
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle); rows = list(reader); fields = list(reader.fieldnames or [])
    if any(row['authority_key'] == 'siracusa' for row in rows):
        raise RuntimeError('Siracusa already present in source_series_inventory')
    rows.extend([
        {
            'source_series_key': 'siracusa-applicants',
            'authority_key': 'siracusa',
            'regime_code': 'WL-REGIME-L190-2012',
            'population_scope': 'applicant',
            'sector_scope': 'all',
            'publication_model': 'periodic_attachment',
            'series_url': LANDING,
            'resource_resolution_status': 'landing_page_resolved',
            'verified_date': '2026-09-20',
            'notes': f'Current official Siracusa landing positively exposes the applicant PDF. Two independent cache-bypassed captures are byte-identical at SHA-256 {APPLICANT_SHA}; the reviewed 104-observation boundary validates as 104 pending, with 102 strict identifiers and 103 normalised application dates. Exact evidence is documented in docs/sources/siracusa-operational-check-2026-09-20.md.',
        },
        {
            'source_series_key': 'siracusa-listed',
            'authority_key': 'siracusa',
            'regime_code': 'WL-REGIME-L190-2012',
            'population_scope': 'listed',
            'sector_scope': 'all',
            'publication_model': 'periodic_attachment',
            'series_url': LANDING,
            'resource_resolution_status': 'landing_page_resolved',
            'verified_date': '2026-09-20',
            'notes': f'Current official Siracusa landing positively exposes the registered-company PDF. Two independent cache-bypassed captures are byte-identical at SHA-256 {LISTED_SHA}; the reviewed 315-observation boundary validates as 246 listed, 67 renewal/update in progress and 2 other/unknown, with 312 strict identifiers and 315 explicit expiry dates. Exact evidence is documented in docs/sources/siracusa-operational-check-2026-09-20.md.',
        },
    ])
    rows.sort(key=lambda row: row['source_series_key'])
    write_csv(path, rows, fields)

    path = ROOT / 'data/catalog.csv'
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle); rows = list(reader); fields = list(reader.fieldnames or [])
    targets = {'verified-primary-pages': ('65', '66'), 'source-series-inventory': ('128', '130')}
    seen = set()
    for row in rows:
        if row['dataset_id'] in targets:
            old, new = targets[row['dataset_id']]
            if row['record_count'] != old:
                raise RuntimeError(f"Catalog anchor drift for {row['dataset_id']}: {row['record_count']!r}")
            row['record_count'] = new
            seen.add(row['dataset_id'])
    if seen != set(targets):
        raise RuntimeError(f'Catalog targets missing: {set(targets) - seen}')
    write_csv(path, rows, fields)


def update_monitoring() -> None:
    path = ROOT / 'data/monitoring/national_coverage.json'
    coverage = json.loads(path.read_text(encoding='utf-8'))
    rows = [row for row in coverage['prefectures'] if row.get('authority_key') == 'siracusa']
    if len(rows) != 1:
        raise RuntimeError(f'Expected one Siracusa coverage row, got {len(rows)}')
    row = rows[0]
    if row.get('public_export_enabled') is not False:
        raise RuntimeError('Siracusa monitoring anchor is already public')
    row.update({
        'source_verified': True,
        'current_edition_identified': True,
        'capture_implemented': True,
        'parser_implemented': True,
        'parser_validated': True,
        'company_observations_loaded': True,
        'observation_layer': 'public_source_observations',
        'canonical_integration_validated': True,
        'public_export_enabled': True,
        'durable_evidence_verified': False,
        'population_scopes_complete': True,
        'latest_source_reference_date': '2026-09-03',
        'last_successful_source_check_at': '2026-09-20T05:25:59Z',
        'last_attempted_source_check_at': '2026-09-20T05:25:59Z',
        'last_successful_investigation_on': '2026-09-20',
        'monitoring_status': 'CURRENT',
        'unresolved_issue': ['Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure.'],
        'actionable_issue': False,
        'coverage_status': 'VALIDATED',
        'terminal_reason': None,
        'completion_evidence': [
            'docs/sources/siracusa-operational-check-2026-09-20.md',
            'src/white_list_archive/parsers/siracusa_tables.py',
            'tests/test_siracusa_parser_semantics.py',
            'data/publication/multi_prefecture_pilot.json',
        ],
        'known_content_sha256': [LISTED_SHA, APPLICANT_SHA],
        'evidence': [
            'data/source_registry/verified_primary_pages.csv',
            'data/source_registry/source_series_inventory.csv',
            'data/publication/multi_prefecture_pilot.json',
            'docs/sources/siracusa-operational-check-2026-09-20.md',
        ],
        'last_completed_coverage_stage': 'VALIDATED',
    })
    path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def update_registry_dispatch() -> None:
    path = ROOT / 'src/white_list_archive/publishing/public_national_registry.py'
    text = path.read_text(encoding='utf-8')
    text = replace_once(
        text,
        'from white_list_archive.parsers.matera_openxml import PARSERS as MATERA_PARSERS\nfrom white_list_archive.parsers.macerata_tables import PARSERS as MACERATA_PARSERS',
        'from white_list_archive.parsers.matera_openxml import PARSERS as MATERA_PARSERS\nfrom white_list_archive.parsers.siracusa_tables import PARSERS as SIRACUSA_PARSERS\nfrom white_list_archive.parsers.macerata_tables import PARSERS as MACERATA_PARSERS',
        'Siracusa parser import',
    )
    text = replace_once(
        text,
        '        or MATERA_PARSERS.get(cfg["parser"])\n        or MACERATA_PARSERS.get(cfg["parser"])',
        '        or MATERA_PARSERS.get(cfg["parser"])\n        or SIRACUSA_PARSERS.get(cfg["parser"])\n        or MACERATA_PARSERS.get(cfg["parser"])',
        'Siracusa parser dispatch',
    )
    path.write_text(text, encoding='utf-8')


def update_tests() -> None:
    path = ROOT / 'tests/test_source_registry.py'
    text = path.read_text(encoding='utf-8')
    text = replace_once(text, '    assert len(pages) == 65\n', '    assert len(pages) == 66\n', 'verified-page test denominator')
    path.write_text(text, encoding='utf-8')

    path = ROOT / 'tests/test_source_population_coverage.py'
    text = path.read_text(encoding='utf-8')
    text = replace_once(text, '    assert report["verified_authority_count"] == 65\n', '    assert report["verified_authority_count"] == 66\n', 'coverage authority denominator')
    text = replace_once(text, '    assert report["register_scope_count"] == 67\n', '    assert report["register_scope_count"] == 68\n', 'coverage register denominator')
    text = replace_once(text, '    assert report["complete_register_scope_count"] == 67\n', '    assert report["complete_register_scope_count"] == 68\n', 'coverage complete denominator')
    text = replace_once(text, '        "matera",\n    ):', '        "matera",\n        "siracusa",\n    ):', 'recently-resolved scope')
    path.write_text(text, encoding='utf-8')

    path = ROOT / 'tests/public_portal_browser.cjs'
    text = path.read_text(encoding='utf-8')
    text = replace_once(text, "      assert.ok(labels.includes('White List ordinaria · Prefettura di Matera'));\n", "      assert.ok(labels.includes('White List ordinaria · Prefettura di Matera'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Siracusa'));\n", 'browser label')
    text = replace_once(text, '      assert.equal(stats.total,69055);\n', '      assert.equal(stats.total,69474);\n', 'browser total')
    text = replace_once(text, "'macerata','trapani','palermo','matera'].includes(r.authority_key)", "'macerata','trapani','palermo','matera','siracusa'].includes(r.authority_key)", 'browser baseline exclusion')
    matera = """      const matera=registry.records.filter(r=>r.authority_key==='matera');
      assert.equal(matera.length,338);
      assert.equal(matera.filter(r=>r.source_key==='matera-listed').length,248);
      assert.equal(matera.filter(r=>r.source_key==='matera-applicants').length,90);
      assert.deepEqual(statusCounts(matera),{listed:248,pending:41,renewal_update_in_progress:49});
      assert.equal(new Set(matera.map(r=>r.record_locator)).size,338);
      assert.equal(matera.filter(r=>r.identifiers.length>0).length,338);
      assert.equal(matera.filter(r=>r.source_key==='matera-applicants'&&r.application_date).length,90);
      assert.equal(matera.filter(r=>r.source_key==='matera-listed'&&r.observed_listing_date&&r.observed_expiry_date).length,248);
      assert.equal(matera.filter(r=>r.source_key==='matera-listed'&&r.source_fields.notes.includes('Art. 34 bis d.lgs 159/2011 - Controllo giudiziario.')).length,1);
"""
    siracusa = """      const siracusa=registry.records.filter(r=>r.authority_key==='siracusa');
      assert.equal(siracusa.length,419);
      assert.equal(siracusa.filter(r=>r.source_key==='siracusa-listed').length,315);
      assert.equal(siracusa.filter(r=>r.source_key==='siracusa-applicants').length,104);
      assert.deepEqual(statusCounts(siracusa),{listed:246,other_or_unknown:2,pending:104,renewal_update_in_progress:67});
      assert.equal(new Set(siracusa.map(r=>r.record_locator)).size,419);
      assert.equal(siracusa.filter(r=>r.identifiers.length>0).length,414);
      assert.equal(siracusa.filter(r=>r.source_key==='siracusa-listed'&&r.observed_expiry_date).length,315);
      assert.equal(siracusa.filter(r=>r.source_key==='siracusa-applicants'&&r.application_date).length,103);
      assert.equal(siracusa.filter(r=>r.source_key==='siracusa-applicants'&&r.source_fields.application_date_raw_variants.includes('17.01/2024')&&r.application_date==='').length,1);
"""
    text = replace_once(text, matera, matera + siracusa, 'browser Siracusa boundary')
    path.write_text(text, encoding='utf-8')


def build_pages_candidate() -> None:
    workflow = (ROOT / '.github/workflows/public-pages.yml').read_text(encoding='utf-8')
    workflow = replace_once(workflow, "      - 'src/white_list_archive/parsers/matera_openxml.py'\n", "      - 'src/white_list_archive/parsers/matera_openxml.py'\n      - 'src/white_list_archive/parsers/siracusa_tables.py'\n", 'pages parser trigger')
    workflow = replace_once(workflow, "          assert reg['meta']['record_count'] == 69055\n", "          assert reg['meta']['record_count'] == 69474\n", 'pages record denominator')
    workflow = replace_once(workflow, "'macerata','trapani','palermo','matera'}\n", "'macerata','trapani','palermo','matera','siracusa'}\n", 'pages authority set')
    workflow = replace_once(workflow, "'macerata-ordinary','trapani-ordinary','palermo-ordinary','matera-ordinary'\n", "'macerata-ordinary','trapani-ordinary','palermo-ordinary','matera-ordinary','siracusa-ordinary'\n", 'pages register set')
    workflow = replace_once(workflow, "          assert reg['meta']['authority_count'] == 65\n", "          assert reg['meta']['authority_count'] == 66\n", 'pages authority denominator')
    workflow = replace_once(workflow, "          assert reg['meta']['register_count'] == 67\n", "          assert reg['meta']['register_count'] == 68\n", 'pages register denominator')
    workflow = replace_once(workflow, "          assert pref['meta']['published_count'] == 65\n", "          assert pref['meta']['published_count'] == 66\n", 'pages published denominator')
    workflow = replace_once(workflow, "          assert pref['meta']['mapped_count'] == 65\n", "          assert pref['meta']['mapped_count'] == 66\n", 'pages mapped denominator')
    matera = """          matera = [x for x in pref['prefectures'] if x['authority_key'] == 'matera']
          assert len(matera) == 1 and matera[0]['mapped'] and matera[0]['published'] and matera[0]['series_count'] == 2
          matera_records = [r for r in reg['records'] if r['authority_key'] == 'matera']
          assert len(matera_records) == 338
          assert sum(r['source_key'] == 'matera-listed' for r in matera_records) == 248
          assert sum(r['source_key'] == 'matera-applicants' for r in matera_records) == 90
          assert sum(r['source_status'] == 'listed' for r in matera_records) == 248
          assert sum(r['source_status'] == 'pending' for r in matera_records) == 41
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in matera_records) == 49
          assert sum(bool(r['identifiers']) for r in matera_records) == 338
          assert sum(bool(r['application_date']) for r in matera_records) == 90
          assert sum(bool(r['observed_listing_date']) for r in matera_records) == 248
          assert sum(bool(r['observed_expiry_date']) for r in matera_records) == 248
          assert len({r['record_locator'] for r in matera_records}) == 338
"""
    siracusa = """          siracusa = [x for x in pref['prefectures'] if x['authority_key'] == 'siracusa']
          assert len(siracusa) == 1 and siracusa[0]['mapped'] and siracusa[0]['published'] and siracusa[0]['series_count'] == 2
          siracusa_records = [r for r in reg['records'] if r['authority_key'] == 'siracusa']
          assert len(siracusa_records) == 419
          assert sum(r['source_key'] == 'siracusa-listed' for r in siracusa_records) == 315
          assert sum(r['source_key'] == 'siracusa-applicants' for r in siracusa_records) == 104
          assert sum(r['source_status'] == 'listed' for r in siracusa_records) == 246
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in siracusa_records) == 67
          assert sum(r['source_status'] == 'other_or_unknown' for r in siracusa_records) == 2
          assert sum(r['source_status'] == 'pending' for r in siracusa_records) == 104
          assert sum(bool(r['identifiers']) for r in siracusa_records) == 414
          assert sum(bool(r['observed_expiry_date']) for r in siracusa_records) == 315
          assert sum(bool(r['application_date']) for r in siracusa_records) == 103
          assert len({r['record_locator'] for r in siracusa_records}) == 419
"""
    workflow = replace_once(workflow, matera, matera + siracusa, 'pages Siracusa boundary')
    (ROOT / 'tmp/siracusa-public-pages.yml').write_text(workflow, encoding='utf-8')


def main() -> None:
    update_publication_config()
    update_registries()
    update_monitoring()
    update_registry_dispatch()
    update_tests()
    build_pages_candidate()
    print('MATERIALISED Siracusa candidate 69474 / 66 / 68 / 66')


if __name__ == '__main__':
    main()
