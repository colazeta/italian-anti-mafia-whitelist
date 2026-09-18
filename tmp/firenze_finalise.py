from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one occurrence, got {count}")
    return text.replace(old, new, 1)


workflow = Path('.github/workflows/public-pages.yml')
x = workflow.read_text(encoding='utf-8')
x = replace_once(
    x,
    "      - 'src/white_list_archive/parsers/como_html.py'\n",
    "      - 'src/white_list_archive/parsers/como_html.py'\n      - 'src/white_list_archive/parsers/firenze_sources.py'\n",
    'Firenze parser path trigger',
)
x = replace_once(x, "assert reg['meta']['record_count'] == 58378", "assert reg['meta']['record_count'] == 59042", 'record total')
x = replace_once(x, "'milano','modena','como'}", "'milano','modena','como','firenze'}", 'authority set')
x = replace_once(x, "'modena-post-sisma','como-ordinary'\n", "'modena-post-sisma','como-ordinary','firenze-ordinary'\n", 'register set')
x = replace_once(x, "assert reg['meta']['authority_count'] == 49", "assert reg['meta']['authority_count'] == 50", 'authority count')
x = replace_once(x, "assert reg['meta']['register_count'] == 51", "assert reg['meta']['register_count'] == 52", 'register count')
x = replace_once(x, "assert pref['meta']['published_count'] == 49", "assert pref['meta']['published_count'] == 50", 'published count')
x = replace_once(x, "assert pref['meta']['mapped_count'] == 49", "assert pref['meta']['mapped_count'] == 50", 'mapped count')

como_block = """          como = [x for x in pref['prefectures'] if x['authority_key'] == 'como']
          assert len(como) == 1 and como[0]['mapped'] and como[0]['published'] and como[0]['series_count'] == 2
          como_records = [r for r in reg['records'] if r['authority_key'] == 'como']
          assert len(como_records) == 409
          assert sum(r['source_key'] == 'como-listed' for r in como_records) == 391
          assert sum(r['source_key'] == 'como-applicants' for r in como_records) == 18
          assert sum(r['source_status'] == 'listed' for r in como_records) == 359
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in como_records) == 32
          assert sum(r['source_status'] == 'pending' for r in como_records) == 18
          assert len({r['record_locator'] for r in como_records}) == 409
          assert sum(bool(r['identifiers']) for r in como_records) == 405
          assert sum(bool(r['identifier_field_raw']) and not r['identifiers'] for r in como_records) == 3
          assert sum(not bool(r['identifier_field_raw']) and not r['identifiers'] for r in como_records) == 1
"""
firenze_block = """          firenze = [x for x in pref['prefectures'] if x['authority_key'] == 'firenze']
          assert len(firenze) == 1 and firenze[0]['mapped'] and firenze[0]['published'] and firenze[0]['series_count'] == 2
          firenze_records = [r for r in reg['records'] if r['authority_key'] == 'firenze']
          assert len(firenze_records) == 664
          assert sum(r['source_key'] == 'firenze-listed' for r in firenze_records) == 539
          assert sum(r['source_key'] == 'firenze-applicants' for r in firenze_records) == 125
          assert sum(r['source_status'] == 'listed' for r in firenze_records) == 429
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in firenze_records) == 110
          assert sum(r['source_status'] == 'pending' for r in firenze_records) == 125
          assert len({r['record_locator'] for r in firenze_records}) == 664
          assert sum(bool(r['identifiers']) for r in firenze_records) == 660
          assert sum(bool(r['identifier_field_raw']) and not r['identifiers'] for r in firenze_records) == 4
          firenze_applicants = [r for r in firenze_records if r['source_key'] == 'firenze-applicants']
          assert sum(not bool(r['registered_office']) for r in firenze_applicants) == 2
"""
x = replace_once(x, como_block, como_block + firenze_block, 'workflow Firenze exact assertions')
staging = Path('staging/firenze-public-pages.yml')
staging.parent.mkdir(parents=True, exist_ok=True)
staging.write_text(x, encoding='utf-8')

browser = Path('tests/public_portal_browser.cjs')
y = browser.read_text(encoding='utf-8')
y = replace_once(
    y,
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Como'));\n",
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Como'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Firenze'));\n",
    'browser register label',
)
y = replace_once(y, '      assert.equal(stats.total,58378);', '      assert.equal(stats.total,59042);', 'browser total')
y = replace_once(
    y,
    "'milano','modena','como'].includes(r.authority_key));",
    "'milano','modena','como','firenze'].includes(r.authority_key));",
    'browser baseline exclusion',
)
browser_como = """      const como=registry.records.filter(r=>r.authority_key==='como');
      assert.equal(como.length,409);
      assert.equal(como.filter(r=>r.source_key==='como-listed').length,391);
      assert.equal(como.filter(r=>r.source_key==='como-applicants').length,18);
      assert.deepEqual(statusCounts(como),{listed:359,pending:18,renewal_update_in_progress:32});
"""
browser_firenze = """      const firenze=registry.records.filter(r=>r.authority_key==='firenze');
      assert.equal(firenze.length,664);
      assert.equal(firenze.filter(r=>r.source_key==='firenze-listed').length,539);
      assert.equal(firenze.filter(r=>r.source_key==='firenze-applicants').length,125);
      assert.deepEqual(statusCounts(firenze),{listed:429,pending:125,renewal_update_in_progress:110});
      assert.equal(new Set(firenze.map(r=>r.record_locator)).size,664);
      assert.equal(firenze.filter(r=>r.identifiers.length>0).length,660);
      assert.equal(firenze.filter(r=>r.identifier_field_raw&&r.identifiers.length===0).length,4);
      assert.equal(firenze.filter(r=>r.source_key==='firenze-applicants'&&!r.registered_office).length,2);
"""
y = replace_once(y, browser_como, browser_como + browser_firenze, 'browser Firenze assertions')
browser.write_text(y, encoding='utf-8')
