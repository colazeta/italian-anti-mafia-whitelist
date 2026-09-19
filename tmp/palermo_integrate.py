from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path('.')
LANDING = 'https://prefettura.interno.gov.it/it/prefetture/palermo/evidenza/white-list'
LISTED_URL = 'https://prefettura.interno.gov.it/sites/default/files/61/2026-09/whitelistelencounicoimpreseiscritte_10.pdf'
APPLICANT_URL = 'https://prefettura.interno.gov.it/sites/default/files/61/2026-09/elencoimpreserichiedentiliscrizione-1_0.pdf'
LISTED_SHA = '2349d3ae3dcd37e5da7fc5fdec1326a9408e00fcc0b3b78b0a0809ad75c0837f'
APPLICANT_SHA = '82dd288c21c85ea563c75cbfc8346c528b603e54c3a78283a0ae67983e97f2f5'


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
    if any(source.get('authority_key') == 'palermo' for source in config['sources']):
        raise RuntimeError('Palermo already present in publication config')
    common = {
        'authority_key': 'palermo',
        'authority_name': 'Prefettura di Palermo',
        'register_key': 'palermo-ordinary',
        'register_name': 'White List ordinaria',
        'source_page_url': LANDING,
        'approval_mode': 'raw_sha256',
    }
    config['sources'].extend([
        {
            **common,
            'reference_date': '2026-09-18',
            'last_source_update': '2026-09-18',
            'last_source_update_basis': "explicit source marker 'Ultima modifica: 18/09/2026'; source-edition boundary only, not promoted to a company legal-effect date",
            'source_key': 'palermo-listed',
            'parser': 'palermo_listed',
            'population_scope': 'listed',
            'resource_url': LISTED_URL,
            'sha256': LISTED_SHA,
            'expected_source_rows': 929,
            'notes': 'Dedicated official listed PDF positively exposed by the current landing page. The 929 observable company rows retain source numbering gaps N° 252 and N° 316; status boundary is 486 listed and 443 renewal/update in progress, with structured identifiers for 924 observations. Nine malformed identifier fields and printed expiry values 28/072027 and 20/072027 are preserved without inferential repair.',
        },
        {
            **common,
            'reference_date': '2026-09-17',
            'last_source_update': '2026-09-17',
            'last_source_update_basis': "explicit source marker 'Ultima modifica: 17/09/2026'; source-edition boundary only, not promoted to a company decision or legal-effect date",
            'source_key': 'palermo-applicants',
            'parser': 'palermo_applicants',
            'population_scope': 'applicant',
            'resource_url': APPLICANT_URL,
            'sha256': APPLICANT_SHA,
            'expected_source_rows': 609,
            'notes': 'Dedicated official applicant PDF positively exposed by the current landing page. It yields 609 positive pending observations across the complete numbered source population, with structured identifiers for 606 observations. Observed spelling variants and malformed identifier fields remain source evidence; no application date is inferred because the source has no application-date column.',
        },
    ])
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def update_registries() -> None:
    path = ROOT / 'data/source_registry/verified_primary_pages.csv'
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    if any(row['authority_key'] == 'palermo' for row in rows):
        raise RuntimeError('Palermo already present in verified_primary_pages')
    rows.append({'authority_key': 'palermo', 'landing_url': LANDING, 'verification_date': '2026-09-19', 'verification_status': 'verified'})
    rows.sort(key=lambda row: row['authority_key'])
    write_csv(path, rows, fields)

    path = ROOT / 'data/source_registry/source_series_inventory.csv'
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    if any(row['authority_key'] == 'palermo' for row in rows):
        raise RuntimeError('Palermo already present in source_series_inventory')
    rows.extend([
        {
            'source_series_key': 'palermo-applicants',
            'authority_key': 'palermo',
            'regime_code': 'WL-REGIME-L190-2012',
            'population_scope': 'applicant',
            'sector_scope': 'all',
            'publication_model': 'periodic_attachment',
            'series_url': LANDING,
            'resource_resolution_status': 'landing_page_resolved',
            'verified_date': '2026-09-19',
            'notes': f'Current official Palermo landing positively exposes the applicant PDF explicitly marked Ultima modifica: 17/09/2026. Two independent cache-bypassed captures are byte-identical at SHA-256 {APPLICANT_SHA}; the complete numbered population yields 609 pending observations with 606 structured identifiers. Exact evidence is documented in docs/sources/palermo-operational-check-2026-09-19.md.',
        },
        {
            'source_series_key': 'palermo-listed',
            'authority_key': 'palermo',
            'regime_code': 'WL-REGIME-L190-2012',
            'population_scope': 'listed',
            'sector_scope': 'all',
            'publication_model': 'periodic_attachment',
            'series_url': LANDING,
            'resource_resolution_status': 'landing_page_resolved',
            'verified_date': '2026-09-19',
            'notes': f'Current official Palermo landing positively exposes the listed PDF explicitly marked Ultima modifica: 18/09/2026. Two independent cache-bypassed captures are byte-identical at SHA-256 {LISTED_SHA}; 929 observations validate as 486 listed and 443 renewal/update in progress, with source numbering gaps and malformed fields preserved without repair. Exact evidence is documented in docs/sources/palermo-operational-check-2026-09-19.md.',
        },
    ])
    rows.sort(key=lambda row: row['source_series_key'])
    write_csv(path, rows, fields)

    path = ROOT / 'data/catalog.csv'
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    targets = {'verified-primary-pages': ('63', '64'), 'source-series-inventory': ('124', '126')}
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
    rows = [row for row in coverage['authorities'] if row.get('authority_key') == 'palermo']
    if len(rows) != 1:
        raise RuntimeError(f'Expected one Palermo coverage row, got {len(rows)}')
    row = rows[0]
    if row.get('source_verified') is not False or row.get('public_export_enabled') is not False:
        raise RuntimeError('Palermo monitoring anchor is no longer unresolved')
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
        'latest_source_reference_date': '2026-09-18',
        'last_successful_source_check_at': '2026-09-19T21:36:40Z',
        'last_attempted_source_check_at': '2026-09-19T21:36:40Z',
        'last_successful_investigation_on': '2026-09-19',
        'monitoring_status': 'CURRENT',
        'unresolved_issue': ['Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure.'],
        'actionable_issue': False,
        'coverage_status': 'VALIDATED',
        'terminal_reason': None,
        'completion_evidence': [
            'docs/sources/palermo-operational-check-2026-09-19.md',
            'src/white_list_archive/parsers/palermo_positioned.py',
            'tests/test_palermo_parser_semantics.py',
            'data/publication/multi_prefecture_pilot.json',
        ],
        'known_content_sha256': [LISTED_SHA, APPLICANT_SHA],
        'evidence': [
            'data/source_registry/verified_primary_pages.csv',
            'data/source_registry/source_series_inventory.csv',
            'data/publication/multi_prefecture_pilot.json',
            'docs/sources/palermo-operational-check-2026-09-19.md',
        ],
        'last_completed_coverage_stage': 'VALIDATED',
    })
    path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def update_registry_dispatch() -> None:
    path = ROOT / 'src/white_list_archive/publishing/public_national_registry.py'
    text = path.read_text(encoding='utf-8')
    text = replace_once(
        text,
        'from white_list_archive.parsers.trapani_tables import PARSERS as TRAPANI_PARSERS\nfrom white_list_archive.parsers.macerata_tables import PARSERS as MACERATA_PARSERS',
        'from white_list_archive.parsers.trapani_tables import PARSERS as TRAPANI_PARSERS\nfrom white_list_archive.parsers.palermo_positioned import PARSERS as PALERMO_PARSERS\nfrom white_list_archive.parsers.macerata_tables import PARSERS as MACERATA_PARSERS',
        'parser import',
    )
    text = replace_once(
        text,
        '        or TRAPANI_PARSERS.get(cfg["parser"])\n        or MACERATA_PARSERS.get(cfg["parser"])',
        '        or TRAPANI_PARSERS.get(cfg["parser"])\n        or PALERMO_PARSERS.get(cfg["parser"])\n        or MACERATA_PARSERS.get(cfg["parser"])',
        'parser dispatch',
    )
    path.write_text(text, encoding='utf-8')


def update_tests() -> None:
    path = ROOT / 'tests/test_source_registry.py'
    text = path.read_text(encoding='utf-8')
    text = replace_once(text, '    assert len(pages) == 63\n', '    assert len(pages) == 64\n', 'verified-page test denominator')
    path.write_text(text, encoding='utf-8')

    path = ROOT / 'tests/test_source_population_coverage.py'
    text = path.read_text(encoding='utf-8')
    text = replace_once(text, '    assert report["verified_authority_count"] == 63\n', '    assert report["verified_authority_count"] == 64\n', 'coverage authority denominator')
    text = replace_once(text, '    assert report["register_scope_count"] == 65\n', '    assert report["register_scope_count"] == 66\n', 'coverage register denominator')
    text = replace_once(text, '    assert report["complete_register_scope_count"] == 65\n', '    assert report["complete_register_scope_count"] == 66\n', 'coverage complete denominator')
    text = replace_once(text, '        "trapani",\n    ):', '        "trapani",\n        "palermo",\n    ):', 'recently-resolved scope')
    path.write_text(text, encoding='utf-8')

    path = ROOT / 'tests/public_portal_browser.cjs'
    text = path.read_text(encoding='utf-8')
    text = replace_once(text, "      assert.ok(labels.includes('White List ordinaria · Prefettura di Trapani'));\n", "      assert.ok(labels.includes('White List ordinaria · Prefettura di Trapani'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Palermo'));\n", 'browser label')
    text = replace_once(text, '      assert.equal(stats.total,67180);\n', '      assert.equal(stats.total,68718);\n', 'browser total')
    text = replace_once(text, "'macerata','trapani'].includes(r.authority_key)", "'macerata','trapani','palermo'].includes(r.authority_key)", 'browser baseline exclusion')
    trapani = """      const trapani=registry.records.filter(r=>r.authority_key==='trapani');
      assert.equal(trapani.length,555);
      assert.equal(trapani.filter(r=>r.source_key==='trapani-listed').length,333);
      assert.equal(trapani.filter(r=>r.source_key==='trapani-applicants').length,222);
      assert.deepEqual(statusCounts(trapani),{listed:177,pending:222,renewal_update_in_progress:156});
      assert.equal(new Set(trapani.map(r=>r.record_locator)).size,555);
      assert.equal(trapani.filter(r=>r.identifiers.length>0).length,555);
"""
    palermo = """      const palermo=registry.records.filter(r=>r.authority_key==='palermo');
      assert.equal(palermo.length,1538);
      assert.equal(palermo.filter(r=>r.source_key==='palermo-listed').length,929);
      assert.equal(palermo.filter(r=>r.source_key==='palermo-applicants').length,609);
      assert.deepEqual(statusCounts(palermo),{listed:486,pending:609,renewal_update_in_progress:443});
      assert.equal(new Set(palermo.map(r=>r.record_locator)).size,1538);
      assert.equal(palermo.filter(r=>r.identifiers.length>0).length,1530);
      assert.equal(palermo.filter(r=>r.source_key==='palermo-listed'&&r.observed_expiry_date===''&&r.source_fields.expiry_date_raw_variants.some(v=>['28/072027','20/072027'].includes(v))).length,2);
"""
    text = replace_once(text, trapani, trapani + palermo, 'browser Palermo boundary')
    path.write_text(text, encoding='utf-8')


def build_pages_candidate() -> None:
    workflow = (ROOT / '.github/workflows/public-pages.yml').read_text(encoding='utf-8')
    workflow = replace_once(workflow, "      - 'src/white_list_archive/parsers/trapani_tables.py'\n", "      - 'src/white_list_archive/parsers/trapani_tables.py'\n      - 'src/white_list_archive/parsers/palermo_positioned.py'\n", 'pages parser trigger')
    workflow = replace_once(workflow, "          assert reg['meta']['record_count'] == 67180\n", "          assert reg['meta']['record_count'] == 68718\n", 'pages record denominator')
    workflow = replace_once(workflow, "'macerata','trapani'}\n", "'macerata','trapani','palermo'}\n", 'pages authority set')
    workflow = replace_once(workflow, "'macerata-ordinary','trapani-ordinary'\n", "'macerata-ordinary','trapani-ordinary','palermo-ordinary'\n", 'pages register set')
    workflow = replace_once(workflow, "          assert reg['meta']['authority_count'] == 63\n", "          assert reg['meta']['authority_count'] == 64\n", 'pages authority denominator')
    workflow = replace_once(workflow, "          assert reg['meta']['register_count'] == 65\n", "          assert reg['meta']['register_count'] == 66\n", 'pages register denominator')
    workflow = replace_once(workflow, "          assert pref['meta']['published_count'] == 63\n", "          assert pref['meta']['published_count'] == 64\n", 'pages published denominator')
    workflow = replace_once(workflow, "          assert pref['meta']['mapped_count'] == 63\n", "          assert pref['meta']['mapped_count'] == 64\n", 'pages mapped denominator')
    trapani = """          trapani = [x for x in pref['prefectures'] if x['authority_key'] == 'trapani']
          assert len(trapani) == 1 and trapani[0]['mapped'] and trapani[0]['published'] and trapani[0]['series_count'] == 2
          trapani_records = [r for r in reg['records'] if r['authority_key'] == 'trapani']
          assert len(trapani_records) == 555
          assert sum(r['source_key'] == 'trapani-listed' for r in trapani_records) == 333
          assert sum(r['source_key'] == 'trapani-applicants' for r in trapani_records) == 222
          assert sum(r['source_status'] == 'listed' for r in trapani_records) == 177
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in trapani_records) == 156
          assert sum(r['source_status'] == 'pending' for r in trapani_records) == 222
          assert sum(bool(r['identifiers']) for r in trapani_records) == 555
          assert len({r['record_locator'] for r in trapani_records}) == 555
"""
    palermo = """          palermo = [x for x in pref['prefectures'] if x['authority_key'] == 'palermo']
          assert len(palermo) == 1 and palermo[0]['mapped'] and palermo[0]['published'] and palermo[0]['series_count'] == 2
          palermo_records = [r for r in reg['records'] if r['authority_key'] == 'palermo']
          assert len(palermo_records) == 1538
          assert sum(r['source_key'] == 'palermo-listed' for r in palermo_records) == 929
          assert sum(r['source_key'] == 'palermo-applicants' for r in palermo_records) == 609
          assert sum(r['source_status'] == 'listed' for r in palermo_records) == 486
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in palermo_records) == 443
          assert sum(r['source_status'] == 'pending' for r in palermo_records) == 609
          assert sum(bool(r['identifiers']) for r in palermo_records) == 1530
          assert len({r['record_locator'] for r in palermo_records}) == 1538
"""
    workflow = replace_once(workflow, trapani, trapani + palermo, 'pages Palermo boundary')
    (ROOT / 'tmp/palermo-public-pages.yml').write_text(workflow, encoding='utf-8')


def main() -> None:
    update_publication_config()
    update_registries()
    update_monitoring()
    update_registry_dispatch()
    update_tests()
    build_pages_candidate()
    print('MATERIALISED Palermo candidate 68718 / 64 / 66 / 64')


if __name__ == '__main__':
    main()
