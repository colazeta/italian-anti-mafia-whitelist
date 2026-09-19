from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path('.')
LANDING = 'https://prefettura.interno.gov.it/it/prefetture/trapani/evidenza/white-list'
LISTED_URL = 'https://prefettura.interno.gov.it/sites/default/files/97/2026-09/elenco-ditte-iscritte-negli-elenchi-delle-white-list-aggiornato-all-11.09.2026.pdf'
APPLICANTS_URL = 'https://prefettura.interno.gov.it/sites/default/files/97/2026-09/elenco-ditte-richiedenti-iscrizione-negli-elenchi-delle-white-list-aggiornato-all-11.09.2026.pdf'
LISTED_SHA = '060c5ddb20b24f733066b59f27aa1ea98a8fdc04d22b0196b90c9e383253b476'
APPLICANTS_SHA = 'd42720c3ebf9c24055371fc42b1de89060604fc98d60861ec72a54e650412ae9'


def expect_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one anchor, found {count}')
    return text.replace(old, new, 1)


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


# Positive official landing-page evidence.
path = ROOT / 'data/source_registry/verified_primary_pages.csv'
rows, fields = read_csv(path)
if fields != ['authority_key', 'landing_url', 'verification_date', 'verification_status']:
    raise SystemExit(f'verified-primary-pages schema drift: {fields!r}')
if any(row['authority_key'] == 'trapani' for row in rows):
    raise SystemExit('Trapani verified primary page already exists unexpectedly')
rows.append({
    'authority_key': 'trapani',
    'landing_url': LANDING,
    'verification_date': '2026-09-19',
    'verification_status': 'verified',
})
rows.sort(key=lambda row: row['authority_key'])
write_csv(path, rows, fields)

# Listed and applicant source series are both positively exposed by the official landing page.
path = ROOT / 'data/source_registry/source_series_inventory.csv'
rows, fields = read_csv(path)
if any(row['authority_key'] == 'trapani' for row in rows):
    raise SystemExit('Trapani source series already exists unexpectedly')
rows.extend([
    {
        'source_series_key': 'trapani-applicants',
        'authority_key': 'trapani',
        'regime_code': 'WL-REGIME-L190-2012',
        'population_scope': 'applicant',
        'sector_scope': 'all',
        'publication_model': 'periodic_attachment',
        'series_url': LANDING,
        'resource_resolution_status': 'landing_page_resolved',
        'verified_date': '2026-09-19',
        'notes': 'Current official Trapani landing positively exposes the applicant PDF marked 11 September 2026. Two independent cache-bypassed captures are byte-identical at SHA-256 ' + APPLICANTS_SHA + '; 222 source-backed pending observations are validated, all with structured identifiers. Exact evidence is documented in docs/sources/trapani-operational-check-2026-09-19.md.',
    },
    {
        'source_series_key': 'trapani-listed',
        'authority_key': 'trapani',
        'regime_code': 'WL-REGIME-L190-2012',
        'population_scope': 'listed',
        'sector_scope': 'all',
        'publication_model': 'periodic_attachment',
        'series_url': LANDING,
        'resource_resolution_status': 'landing_page_resolved',
        'verified_date': '2026-09-19',
        'notes': 'Current official Trapani landing positively exposes the listed PDF marked 11 September 2026. Two independent cache-bypassed captures are byte-identical at SHA-256 ' + LISTED_SHA + '; 658 sector rows resolve conservatively to 333 observations (177 listed, 156 renewal/update in progress), all with structured identifiers. Exact evidence is documented in docs/sources/trapani-operational-check-2026-09-19.md.',
    },
])
rows.sort(key=lambda row: row['source_series_key'])
write_csv(path, rows, fields)

# Byte-pinned publication configuration. The 11 September date is source-edition provenance only.
path = ROOT / 'data/publication/multi_prefecture_pilot.json'
cfg = json.loads(path.read_text(encoding='utf-8'))
if any(source['authority_key'] == 'trapani' for source in cfg['sources']):
    raise SystemExit('Trapani publication source already exists unexpectedly')
common = {
    'authority_key': 'trapani',
    'authority_name': 'Prefettura di Trapani',
    'register_key': 'trapani-ordinary',
    'register_name': 'White List ordinaria',
    'reference_date': '2026-09-11',
    'source_page_url': LANDING,
    'last_source_update': '2026-09-11',
    'last_source_update_basis': 'date explicitly carried in the official attachment filenames; used as the source edition/reference boundary only and not promoted to a company decision or legal-effect date',
    'approval_mode': 'raw_sha256',
}
cfg['sources'].extend([
    common | {
        'source_key': 'trapani-listed',
        'parser': 'trapani_listed',
        'population_scope': 'listed',
        'resource_url': LISTED_URL,
        'sha256': LISTED_SHA,
        'expected_source_rows': 333,
        'expected_sector_rows': 658,
        'notes': 'Dedicated official listed PDF positively exposed by the current landing page. 658 statutory-sector rows resolve to 333 source-backed observations: 177 listed and 156 renewal/update in progress. Structured identifier coverage is 333/333. The unique non-date expiry text for CALCESTRUZZI DI ROMANO ALESSANDRO is preserved raw while observed_expiry_date remains blank; continuation rows and source variants are handled only through exact fail-closed evidence bindings.',
    },
    common | {
        'source_key': 'trapani-applicants',
        'parser': 'trapani_applicants',
        'population_scope': 'applicant',
        'resource_url': APPLICANTS_URL,
        'sha256': APPLICANTS_SHA,
        'expected_source_rows': 222,
        'notes': 'Dedicated official applicant PDF positively exposed by the current landing page. 222 source-backed observations are pending and structured identifier coverage is 222/222. Twenty-three page-boundary continuation rows are joined only through exact fail-closed evidence bindings; applicant coverage is positive source evidence and is never inferred from absence.',
    },
])
path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# National monitoring checkpoint, preserving the independent durable-evidence governance boundary.
path = ROOT / 'data/monitoring/national_coverage.json'
monitoring = json.loads(path.read_text(encoding='utf-8'))
matches = [row for row in monitoring['prefectures'] if row['authority_key'] == 'trapani']
if len(matches) != 1:
    raise SystemExit(f'Trapani monitoring row count drift: {len(matches)}')
row = matches[0]
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
    'latest_source_reference_date': '2026-09-11',
    'last_successful_source_check_at': '2026-09-19T16:08:37Z',
    'last_attempted_source_check_at': '2026-09-19T16:08:37Z',
    'last_content_change_at': None,
    'last_successful_investigation_on': '2026-09-19',
    'monitoring_status': 'CURRENT',
    'unresolved_issue': ['Canonical hosted-database integration and independent durable-evidence verification remain governed under #16; public source observations are validated independently of that infrastructure.'],
    'actionable_issue': False,
    'coverage_status': 'VALIDATED',
    'terminal_reason': None,
    'completion_evidence': [
        'docs/sources/trapani-operational-check-2026-09-19.md',
        'src/white_list_archive/parsers/trapani_tables.py',
        'tests/test_trapani_parser_semantics.py',
        'data/publication/multi_prefecture_pilot.json',
    ],
    'known_content_sha256': [LISTED_SHA, APPLICANTS_SHA],
    'evidence': [
        'data/source_registry/verified_primary_pages.csv',
        'data/source_registry/source_series_inventory.csv',
        'data/publication/multi_prefecture_pilot.json',
        'docs/sources/trapani-operational-check-2026-09-19.md',
    ],
    'last_completed_coverage_stage': 'VALIDATED',
})
path.write_text(json.dumps(monitoring, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# Catalog denominators.
path = ROOT / 'data/catalog.csv'
rows, fields = read_csv(path)
by_id = {row['dataset_id']: row for row in rows}
if by_id['verified-primary-pages']['record_count'] != '61' or by_id['source-series-inventory']['record_count'] != '120':
    raise SystemExit('Catalog denominator anchor drift')
by_id['verified-primary-pages']['record_count'] = '62'
by_id['source-series-inventory']['record_count'] = '122'
write_csv(path, rows, fields)

# Permanent parser binding into the national public registry builder.
path = ROOT / 'src/white_list_archive/publishing/public_national_registry.py'
text = path.read_text(encoding='utf-8')
text = expect_once(
    text,
    'from white_list_archive.parsers.lucca_tables import PARSERS as LUCCA_PARSERS\n',
    'from white_list_archive.parsers.lucca_tables import PARSERS as LUCCA_PARSERS\nfrom white_list_archive.parsers.trapani_tables import PARSERS as TRAPANI_PARSERS\n',
    'Trapani parser import',
)
text = expect_once(
    text,
    '        or LUCCA_PARSERS.get(cfg["parser"])\n',
    '        or LUCCA_PARSERS.get(cfg["parser"])\n        or TRAPANI_PARSERS.get(cfg["parser"])\n',
    'Trapani parser resolution',
)
path.write_text(text, encoding='utf-8')

# Source-population completeness denominators.
path = ROOT / 'tests/test_source_population_coverage.py'
text = path.read_text(encoding='utf-8')
for old, new, label in [
    ('assert report["verified_authority_count"] == 61', 'assert report["verified_authority_count"] == 62', 'verified authority denominator'),
    ('assert report["register_scope_count"] == 63', 'assert report["register_scope_count"] == 64', 'register scope denominator'),
    ('assert report["complete_register_scope_count"] == 63', 'assert report["complete_register_scope_count"] == 64', 'complete scope denominator'),
]:
    text = expect_once(text, old, new, label)
path.write_text(text, encoding='utf-8')

# Public Pages exact national assertions.
path = ROOT / '.github/workflows/public-pages.yml'
text = path.read_text(encoding='utf-8')
text = expect_once(
    text,
    "      - 'src/white_list_archive/parsers/lucca_tables.py'\n",
    "      - 'src/white_list_archive/parsers/lucca_tables.py'\n      - 'src/white_list_archive/parsers/trapani_tables.py'\n",
    'public workflow path trigger',
)
text = expect_once(text, "assert reg['meta']['record_count'] == 65267", "assert reg['meta']['record_count'] == 65822", 'public record count')
text = expect_once(text, "'imperia','lucca'}", "'imperia','lucca','trapani'}", 'public authority set')
text = expect_once(text, "'imperia-ordinary','lucca-ordinary'", "'imperia-ordinary','lucca-ordinary','trapani-ordinary'", 'public register set')
text = expect_once(text, "assert reg['meta']['authority_count'] == 61", "assert reg['meta']['authority_count'] == 62", 'public authority count')
text = expect_once(text, "assert reg['meta']['register_count'] == 63", "assert reg['meta']['register_count'] == 64", 'public register count')
text = expect_once(text, "assert pref['meta']['published_count'] == 61", "assert pref['meta']['published_count'] == 62", 'published count')
text = expect_once(text, "assert pref['meta']['mapped_count'] == 61", "assert pref['meta']['mapped_count'] == 62", 'mapped count')
anchor = "          assert len({r['record_locator'] for r in lucca_records}) == 402\n"
block = anchor + """          trapani = [x for x in pref['prefectures'] if x['authority_key'] == 'trapani']
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
text = expect_once(text, anchor, block, 'Trapani public assertions')
path.write_text(text, encoding='utf-8')

# Browser acceptance assertions, preserving the fixed historical baseline while adding Trapani explicitly.
path = ROOT / 'tests/public_portal_browser.cjs'
text = path.read_text(encoding='utf-8')
text = expect_once(
    text,
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Lucca'));\n",
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Lucca'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Trapani'));\n",
    'browser label',
)
text = expect_once(text, 'assert.equal(stats.total,65267);', 'assert.equal(stats.total,65822);', 'browser total')
text = expect_once(text, "'imperia','lucca'].includes(r.authority_key)", "'imperia','lucca','trapani'].includes(r.authority_key)", 'browser baseline exclusion')
anchor = "      assert.equal(lucca.filter(r=>r.identifiers.length>0).length,393);\n"
block = anchor + """      const trapani=registry.records.filter(r=>r.authority_key==='trapani');
      assert.equal(trapani.length,555);
      assert.equal(trapani.filter(r=>r.source_key==='trapani-listed').length,333);
      assert.equal(trapani.filter(r=>r.source_key==='trapani-applicants').length,222);
      assert.deepEqual(statusCounts(trapani),{listed:177,pending:222,renewal_update_in_progress:156});
      assert.equal(new Set(trapani.map(r=>r.record_locator)).size,555);
      assert.equal(trapani.filter(r=>r.identifiers.length>0).length,555);
"""
text = expect_once(text, anchor, block, 'browser Trapani block')
path.write_text(text, encoding='utf-8')

# Reproducible source/provenance note.
doc = ROOT / 'docs/sources/trapani-operational-check-2026-09-19.md'
if doc.exists():
    raise SystemExit('Trapani operational note already exists unexpectedly')
doc.write_text(f'''# Trapani White List operational check — 19 September 2026

## Official publication surface

The current official Prefettura di Trapani White List landing page is `{LANDING}`. It positively exposes two dedicated populations: the registered-company list and the list of companies requesting registration. Applicant coverage is therefore based on positive official-source evidence and is not inferred from search results or absence.

The source edition boundary used by the integration is 11 September 2026 because that date is explicitly carried in both official attachment filenames. It is a source reference boundary only and is not promoted to a company decision date, registration date, expiry date, or legal-effect date.

## Byte-pinned sources

- Listed PDF: `{LISTED_URL}` — SHA-256 `{LISTED_SHA}`.
- Applicant PDF: `{APPLICANTS_URL}` — SHA-256 `{APPLICANTS_SHA}`.

The validation worker performed two independent cache-bypassed GETs for each official attachment and required byte identity and exact SHA-256 before parsing.

## Listed population

The listed PDF has 41 pages. Its 658 statutory-sector rows resolve conservatively to 333 company observations after exact handling of repeated sector membership and ten explicitly bound continuation rows. The validated status boundary is 177 `listed` and 156 `renewal_update_in_progress`; structured identifier coverage is 333/333.

One source cell is intentionally not parsed as an expiry date. For `CALCESTRUZZI DI ROMANO ALESSANDRO` (identifier `05913370820`, Marsala), the source prints `In amministrazio ne giudiziaria e fermo restando fino al permanere della stessa` in the expiry column. The parser binds that exact identity/page/name/office/listing-date evidence, preserves the literal value in the raw expiry variants, and leaves `observed_expiry_date` blank. No date is inferred.

The page-boundary `SILVESTRO` fragment is likewise treated only through exact evidence: it completes `IMPRESA EDILE DI MANGANO SILVESTRO` and carries the source marker `per rinnovo`, yielding `In aggiornamento per rinnovo`. Generic continuation heuristics are not used to silently absorb unexpected semantic content.

## Applicant population

The applicant PDF has 44 pages and yields 222 pending observations with 222/222 structured identifiers. Twenty-three page-boundary continuation rows are joined only where exact prior-row identity and continuation content are bound in the parser. No applicant status, legal outcome, or completeness claim is inferred from failed retrieval or search.

## Validation boundary

The exact-head validation on 19 September 2026 required 333 listed-side observations, 222 applicant observations, 555 unique structured identifiers across the two source populations, exact status denominators, exact continuation counts, the unique raw non-date expiry case, and byte-identical repeated official-source captures. Repository CI, the source probe, shape diagnostics and focused parser validation were green before national integration was attempted.
''', encoding='utf-8')
