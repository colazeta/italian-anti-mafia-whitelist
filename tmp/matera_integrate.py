from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path('.')
LANDING = 'https://prefettura.interno.gov.it/it/prefetture/matera/evidenza/white-list'
LISTED_URL = 'https://prefettura.interno.gov.it/sites/default/files/54/2026-08/iscritte-luglio-2026.xlsx'
APPLICANT_URL = 'https://prefettura.interno.gov.it/sites/default/files/54/2026-08/elenco-richiedenti-iscrizione.xlsx'
LISTED_SHA = '4a2a3fad0711f9d3c159d78c93210983b9f1699c2810d8154b60d8fc5d958d3f'
APPLICANT_SHA = 'e4dae926800d1c513e1274b8ae45267337987eaa5b62b1581cbbcc56f6da898c'


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
    if any(source.get('authority_key') == 'matera' for source in config['sources']):
        raise RuntimeError('Matera already present in publication config')
    common = {
        'authority_key': 'matera',
        'authority_name': 'Prefettura di Matera',
        'register_key': 'matera-ordinary',
        'register_name': 'White List ordinaria',
        'source_page_url': LANDING,
        'approval_mode': 'raw_sha256',
        'reference_date': '2026-07-31',
        'last_source_update': '2026-07-31',
        'last_source_update_basis': "official landing attachment label 'aggiornato al 31 Luglio 2026'; source-edition boundary only, not promoted to a company legal-effect date",
    }
    config['sources'].extend([
        {
            **common,
            'source_key': 'matera-listed',
            'parser': 'matera_listed',
            'population_scope': 'listed',
            'resource_url': LISTED_URL,
            'sha256': LISTED_SHA,
            'expected_source_rows': 248,
            'notes': 'Dedicated official listed XLSX positively exposed by the current landing page. Exact workbook shape is 249x10 with 248 source rows, all explicit ISCRITTA. Structured identifiers and explicit listing/expiry dates cover 248/248 observations. Formula-literal cells are decoded only from the exact ="literal" wrapper. One reviewed judicial-control note appears with and without a final full stop across repeated spill cells; both exact variants are preserved and any unreviewed multi-note disagreement fails closed.',
        },
        {
            **common,
            'source_key': 'matera-applicants',
            'parser': 'matera_applicants',
            'population_scope': 'applicant',
            'resource_url': APPLICANT_URL,
            'sha256': APPLICANT_SHA,
            'expected_source_rows': 90,
            'notes': 'Dedicated official request/update XLSX positively exposed by the current landing page. Exact workbook shape is 91x7 with 90 source rows: 41 RICHIEDENTE_ISCRIZIONE mapped to pending and 49 IN_AGGIORNAMENTO mapped to renewal/update in progress. Structured identifiers and explicit application dates cover 90/90 observations; two source dates are true Excel date cells and all others use the exact literal-formula wrapper.',
        },
    ])
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def update_registries() -> None:
    path = ROOT / 'data/source_registry/verified_primary_pages.csv'
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle); rows = list(reader); fields = list(reader.fieldnames or [])
    if any(row['authority_key'] == 'matera' for row in rows):
        raise RuntimeError('Matera already present in verified_primary_pages')
    rows.append({'authority_key': 'matera', 'landing_url': LANDING, 'verification_date': '2026-09-20', 'verification_status': 'verified'})
    rows.sort(key=lambda row: row['authority_key'])
    write_csv(path, rows, fields)

    path = ROOT / 'data/source_registry/source_series_inventory.csv'
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle); rows = list(reader); fields = list(reader.fieldnames or [])
    if any(row['authority_key'] == 'matera' for row in rows):
        raise RuntimeError('Matera already present in source_series_inventory')
    rows.extend([
        {
            'source_series_key': 'matera-applicants',
            'authority_key': 'matera',
            'regime_code': 'WL-REGIME-L190-2012',
            'population_scope': 'applicant',
            'sector_scope': 'all',
            'publication_model': 'periodic_attachment',
            'series_url': LANDING,
            'resource_resolution_status': 'landing_page_resolved',
            'verified_date': '2026-09-20',
            'notes': f'Current official Matera landing positively exposes the request/update XLSX labelled updated to 31 July 2026. Two independent cache-bypassed captures are byte-identical at SHA-256 {APPLICANT_SHA}; the 90-row source boundary validates as 41 pending and 49 renewal/update in progress, with 90 structured identifiers. Exact evidence is documented in docs/sources/matera-operational-check-2026-09-20.md.',
        },
        {
            'source_series_key': 'matera-listed',
            'authority_key': 'matera',
            'regime_code': 'WL-REGIME-L190-2012',
            'population_scope': 'listed',
            'sector_scope': 'all',
            'publication_model': 'periodic_attachment',
            'series_url': LANDING,
            'resource_resolution_status': 'landing_page_resolved',
            'verified_date': '2026-09-20',
            'notes': f'Current official Matera landing positively exposes the listed XLSX labelled updated to 31 July 2026. Two independent cache-bypassed captures are byte-identical at SHA-256 {LISTED_SHA}; all 248 source observations validate as listed, with complete structured identifiers and explicit listing/expiry dates. Exact evidence is documented in docs/sources/matera-operational-check-2026-09-20.md.',
        },
    ])
    rows.sort(key=lambda row: row['source_series_key'])
    write_csv(path, rows, fields)

    path = ROOT / 'data/catalog.csv'
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle); rows = list(reader); fields = list(reader.fieldnames or [])
    targets = {'verified-primary-pages': ('64', '65'), 'source-series-inventory': ('126', '128')}
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
    rows = [row for row in coverage['prefectures'] if row.get('authority_key') == 'matera']
    if len(rows) != 1:
        raise RuntimeError(f'Expected one Matera coverage row, got {len(rows)}')
    row = rows[0]
    if row.get('source_verified') is not False or row.get('public_export_enabled') is not False:
        raise RuntimeError('Matera monitoring anchor is no longer unresolved')
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
        'latest_source_reference_date': '2026-07-31',
        'last_successful_source_check_at': '2026-09-20T03:18:22Z',
        'last_attempted_source_check_at': '2026-09-20T03:18:22Z',
        'last_successful_investigation_on': '2026-09-20',
        'monitoring_status': 'CURRENT',
        'unresolved_issue': ['Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure.'],
        'actionable_issue': False,
        'coverage_status': 'VALIDATED',
        'terminal_reason': None,
        'completion_evidence': [
            'docs/sources/matera-operational-check-2026-09-20.md',
            'src/white_list_archive/parsers/matera_openxml.py',
            'tests/test_matera_parser_semantics.py',
            'data/publication/multi_prefecture_pilot.json',
        ],
        'known_content_sha256': [LISTED_SHA, APPLICANT_SHA],
        'evidence': [
            'data/source_registry/verified_primary_pages.csv',
            'data/source_registry/source_series_inventory.csv',
            'data/publication/multi_prefecture_pilot.json',
            'docs/sources/matera-operational-check-2026-09-20.md',
        ],
        'last_completed_coverage_stage': 'VALIDATED',
    })
    path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def update_registry_dispatch() -> None:
    path = ROOT / 'src/white_list_archive/publishing/public_national_registry.py'
    text = path.read_text(encoding='utf-8')
    text = replace_once(
        text,
        'from white_list_archive.parsers.palermo_positioned import PARSERS as PALERMO_PARSERS\nfrom white_list_archive.parsers.macerata_tables import PARSERS as MACERATA_PARSERS',
        'from white_list_archive.parsers.palermo_positioned import PARSERS as PALERMO_PARSERS\nfrom white_list_archive.parsers.matera_openxml import PARSERS as MATERA_PARSERS\nfrom white_list_archive.parsers.macerata_tables import PARSERS as MACERATA_PARSERS',
        'parser import',
    )
    adapter = '''\n\ndef _adapt_matera_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:\n    """Project audited Matera workbook evidence onto the closed public contract."""\n    adapted: list[dict[str, Any]] = []\n    for source_record in batch.records:\n        record = dict(source_record)\n        fields = record.get("source_fields")\n        if not isinstance(fields, dict):\n            raise RuntimeError("Matera source_fields must be a mapping")\n        if parser_name == "matera_listed":\n            expected = {\n                "source_row", "source_authority_code", "source_status_raw",\n                "listing_date_raw_variants", "expiry_date_raw_variants",\n                "notes", "note_variants", "note_cells_raw",\n            }\n            if set(fields) != expected:\n                raise RuntimeError(f"Matera listed source-field drift: {sorted(fields)!r}")\n            for key in ("listing_date_raw_variants", "expiry_date_raw_variants", "notes", "note_variants", "note_cells_raw"):\n                if not isinstance(fields[key], list) or any(not isinstance(value, str) for value in fields[key]):\n                    raise RuntimeError(f"Matera listed source-field type drift: {key}")\n            if type(fields["source_row"]) is not int or any(not isinstance(fields[key], str) for key in ("source_authority_code", "source_status_raw")):\n                raise RuntimeError("Matera listed source-locator/status type drift")\n            record["source_fields"] = {\n                "notes": list(fields["note_variants"]),\n                "listing_date_raw_variants": list(fields["listing_date_raw_variants"]),\n                "expiry_date_raw_variants": list(fields["expiry_date_raw_variants"]),\n            }\n        elif parser_name == "matera_applicants":\n            expected = {\n                "source_row", "source_authority_code", "source_status_raw",\n                "application_date_raw_variants", "requested_sections_raw",\n                "protocol_request", "application_date_cell_type",\n            }\n            if set(fields) != expected:\n                raise RuntimeError(f"Matera applicant source-field drift: {sorted(fields)!r}")\n            if type(fields["source_row"]) is not int:\n                raise RuntimeError("Matera applicant source-row type drift")\n            if not isinstance(fields["application_date_raw_variants"], list) or any(not isinstance(value, str) for value in fields["application_date_raw_variants"]):\n                raise RuntimeError("Matera applicant application-date evidence type drift")\n            for key in ("source_authority_code", "source_status_raw", "requested_sections_raw", "protocol_request", "application_date_cell_type"):\n                if not isinstance(fields[key], str):\n                    raise RuntimeError(f"Matera applicant source-field scalar drift: {key}")\n            record["source_fields"] = {\n                "sections": list(record.get("requested_activities", [])),\n                "requested_activities_source": fields["requested_sections_raw"],\n                "application_date_raw_variants": list(fields["application_date_raw_variants"]),\n            }\n        else:\n            raise RuntimeError(f"Unexpected Matera parser: {parser_name!r}")\n        adapted.append(record)\n    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)\n'''
    text = replace_once(text, '\n\ndef _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:\n', adapter + '\n\ndef _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:\n', 'Matera adapter insertion')
    text = replace_once(
        text,
        '        or PALERMO_PARSERS.get(cfg["parser"])\n        or MACERATA_PARSERS.get(cfg["parser"])',
        '        or PALERMO_PARSERS.get(cfg["parser"])\n        or MATERA_PARSERS.get(cfg["parser"])\n        or MACERATA_PARSERS.get(cfg["parser"])',
        'parser dispatch',
    )
    text = replace_once(
        text,
        '    if cfg["parser"] in ROMA_PARSERS:\n        batch = _adapt_roma_public_fields(batch, cfg["parser"])\n    for record in batch.records:',
        '    if cfg["parser"] in ROMA_PARSERS:\n        batch = _adapt_roma_public_fields(batch, cfg["parser"])\n    if cfg["parser"] in MATERA_PARSERS:\n        batch = _adapt_matera_public_fields(batch, cfg["parser"])\n    for record in batch.records:',
        'Matera public adapter dispatch',
    )
    path.write_text(text, encoding='utf-8')


def update_tests() -> None:
    path = ROOT / 'tests/test_source_registry.py'
    text = path.read_text(encoding='utf-8')
    text = replace_once(text, '    assert len(pages) == 64\n', '    assert len(pages) == 65\n', 'verified-page test denominator')
    path.write_text(text, encoding='utf-8')

    path = ROOT / 'tests/test_source_population_coverage.py'
    text = path.read_text(encoding='utf-8')
    text = replace_once(text, '    assert report["verified_authority_count"] == 64\n', '    assert report["verified_authority_count"] == 65\n', 'coverage authority denominator')
    text = replace_once(text, '    assert report["register_scope_count"] == 66\n', '    assert report["register_scope_count"] == 67\n', 'coverage register denominator')
    text = replace_once(text, '    assert report["complete_register_scope_count"] == 66\n', '    assert report["complete_register_scope_count"] == 67\n', 'coverage complete denominator')
    text = replace_once(text, '        "palermo",\n    ):', '        "palermo",\n        "matera",\n    ):', 'recently-resolved scope')
    path.write_text(text, encoding='utf-8')

    path = ROOT / 'tests/public_portal_browser.cjs'
    text = path.read_text(encoding='utf-8')
    text = replace_once(text, "      assert.ok(labels.includes('White List ordinaria · Prefettura di Palermo'));\n", "      assert.ok(labels.includes('White List ordinaria · Prefettura di Palermo'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Matera'));\n", 'browser label')
    text = replace_once(text, '      assert.equal(stats.total,68717);\n', '      assert.equal(stats.total,69055);\n', 'browser total')
    text = replace_once(text, "'macerata','trapani','palermo'].includes(r.authority_key)", "'macerata','trapani','palermo','matera'].includes(r.authority_key)", 'browser baseline exclusion')
    palermo = """      const palermo=registry.records.filter(r=>r.authority_key==='palermo');
      assert.equal(palermo.length,1538);
      assert.equal(palermo.filter(r=>r.source_key==='palermo-listed').length,929);
      assert.equal(palermo.filter(r=>r.source_key==='palermo-applicants').length,609);
      assert.deepEqual(statusCounts(palermo),{listed:486,pending:609,renewal_update_in_progress:443});
      assert.equal(new Set(palermo.map(r=>r.record_locator)).size,1538);
      assert.equal(palermo.filter(r=>r.identifiers.length>0).length,1530);
      assert.equal(palermo.filter(r=>r.source_key==='palermo-listed'&&r.observed_expiry_date===''&&r.source_fields.expiry_date_raw_variants.some(v=>['28/072027','20/072027'].includes(v))).length,2);
"""
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
    text = replace_once(text, palermo, palermo + matera, 'browser Matera boundary')
    path.write_text(text, encoding='utf-8')


def build_pages_candidate() -> None:
    workflow = (ROOT / '.github/workflows/public-pages.yml').read_text(encoding='utf-8')
    workflow = replace_once(workflow, "      - 'src/white_list_archive/parsers/palermo_positioned.py'\n", "      - 'src/white_list_archive/parsers/palermo_positioned.py'\n      - 'src/white_list_archive/parsers/matera_openxml.py'\n", 'pages parser trigger')
    workflow = replace_once(workflow, "          assert reg['meta']['record_count'] == 68717\n", "          assert reg['meta']['record_count'] == 69055\n", 'pages record denominator')
    workflow = replace_once(workflow, "'macerata','trapani','palermo'}\n", "'macerata','trapani','palermo','matera'}\n", 'pages authority set')
    workflow = replace_once(workflow, "'macerata-ordinary','trapani-ordinary','palermo-ordinary'\n", "'macerata-ordinary','trapani-ordinary','palermo-ordinary','matera-ordinary'\n", 'pages register set')
    workflow = replace_once(workflow, "          assert reg['meta']['authority_count'] == 64\n", "          assert reg['meta']['authority_count'] == 65\n", 'pages authority denominator')
    workflow = replace_once(workflow, "          assert reg['meta']['register_count'] == 66\n", "          assert reg['meta']['register_count'] == 67\n", 'pages register denominator')
    workflow = replace_once(workflow, "          assert pref['meta']['published_count'] == 64\n", "          assert pref['meta']['published_count'] == 65\n", 'pages published denominator')
    workflow = replace_once(workflow, "          assert pref['meta']['mapped_count'] == 64\n", "          assert pref['meta']['mapped_count'] == 65\n", 'pages mapped denominator')
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
    workflow = replace_once(workflow, palermo, palermo + matera, 'pages Matera boundary')
    (ROOT / 'tmp/matera-public-pages.yml').write_text(workflow, encoding='utf-8')


def main() -> None:
    update_publication_config()
    update_registries()
    update_monitoring()
    update_registry_dispatch()
    update_tests()
    build_pages_candidate()
    print('MATERIALISED Matera candidate 69055 / 65 / 67 / 65')


if __name__ == '__main__':
    main()
