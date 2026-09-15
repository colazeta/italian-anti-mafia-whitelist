from __future__ import annotations

from pathlib import Path


def replace_one(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


pages_path = Path(".github/workflows/public-pages.yml")
pages = pages_path.read_text(encoding="utf-8")
pages = replace_one(
    pages,
    "      - 'src/white_list_archive/parsers/pisa_tables.py'\n",
    "      - 'src/white_list_archive/parsers/pisa_tables.py'\n"
    "      - 'src/white_list_archive/parsers/catanzaro_tables.py'\n",
    label="public-pages parser trigger",
)
pages = replace_one(
    pages,
    "assert reg['meta']['record_count'] == 47248",
    "assert reg['meta']['record_count'] == 48135",
    label="record count",
)
pages = replace_one(
    pages,
    "'lodi','roma','pisa'}",
    "'lodi','roma','pisa','catanzaro'}",
    label="authority set",
)
pages = replace_one(
    pages,
    "'lodi-ordinary','roma-ordinary','pisa-white-list'",
    "'lodi-ordinary','roma-ordinary','pisa-white-list','catanzaro-ordinary'",
    label="register set",
)
pages = replace_one(
    pages,
    "assert reg['meta']['authority_count'] == 41",
    "assert reg['meta']['authority_count'] == 42",
    label="authority count",
)
pages = replace_one(
    pages,
    "assert reg['meta']['register_count'] == 42",
    "assert reg['meta']['register_count'] == 43",
    label="register count",
)
pages = replace_one(
    pages,
    "assert pref['meta']['published_count'] == 41",
    "assert pref['meta']['published_count'] == 42",
    label="published count",
)
pages = replace_one(
    pages,
    "assert pref['meta']['mapped_count'] == 45",
    "assert pref['meta']['mapped_count'] == 46",
    label="mapped count",
)
pisa_tail = """          assert sum(bool(r['identifiers']) for r in pisa_records if r['source_key'] == 'pisa-listed') == 397
          assert sum(bool(r['identifiers']) for r in pisa_records if r['source_key'] == 'pisa-applicants') == 18
          assert sum(bool(r['identifiers']) for r in pisa_records if r['source_key'] == 'pisa-renewal-update') == 33
"""
catanzaro_block = pisa_tail + """          catanzaro = [x for x in pref['prefectures'] if x['authority_key'] == 'catanzaro']
          assert len(catanzaro) == 1 and catanzaro[0]['mapped'] and catanzaro[0]['published'] and catanzaro[0]['series_count'] == 2
          catanzaro_records = [r for r in reg['records'] if r['authority_key'] == 'catanzaro']
          assert len(catanzaro_records) == 887
          assert sum(r['source_key'] == 'catanzaro-listed' for r in catanzaro_records) == 610
          assert sum(r['source_key'] == 'catanzaro-applicants' for r in catanzaro_records) == 277
          assert sum(r['source_status'] == 'listed' for r in catanzaro_records) == 377
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in catanzaro_records) == 233
          assert sum(r['source_status'] == 'pending' for r in catanzaro_records) == 277
          assert len({r['record_locator'] for r in catanzaro_records}) == 887
          assert sum(bool(r['identifiers']) for r in catanzaro_records if r['source_key'] == 'catanzaro-listed') == 601
          assert sum(bool(r['identifiers']) for r in catanzaro_records if r['source_key'] == 'catanzaro-applicants') == 272
          assert sum(
              r['source_key'] == 'catanzaro-applicants'
              and r.get('source_fields', {}).get('application_date_raw') == '1/8/12/2025'
              and r.get('application_date') == ''
              for r in catanzaro_records
          ) == 1
"""
pages = replace_one(
    pages,
    pisa_tail,
    catanzaro_block,
    label="Catanzaro public invariants",
)
pages_path.write_text(pages, encoding="utf-8")

browser_path = Path("tests/public_portal_browser.cjs")
browser = browser_path.read_text(encoding="utf-8")
browser = replace_one(
    browser,
    "      assert.ok(labels.includes('White List — Prefettura di Pisa · Prefettura di Pisa'));\n",
    "      assert.ok(labels.includes('White List — Prefettura di Pisa · Prefettura di Pisa'));\n"
    "      assert.ok(labels.includes('White List — Prefettura di Catanzaro · Prefettura di Catanzaro'));\n",
    label="browser Catanzaro selector",
)
browser = replace_one(
    browser,
    "assert.equal(stats.total,47248);",
    "assert.equal(stats.total,48135);",
    label="browser total",
)
browser = replace_one(
    browser,
    "'lodi','roma','pisa'].includes(r.authority_key)",
    "'lodi','roma','pisa','catanzaro'].includes(r.authority_key)",
    label="browser expansion exclusion",
)
pisa_browser_tail = """      assert.equal(pisa.filter(r=>r.source_key==='pisa-renewal-update'&&r.identifiers.length>0).length,33);
      assert.equal(pisa.filter(r=>r.name==='ROHDE NIELSEN A/S'&&r.source_key==='pisa-listed'&&r.identifiers.length===0).length,1);
"""
catanzaro_browser = pisa_browser_tail + """      const catanzaro=registry.records.filter(r=>r.authority_key==='catanzaro');
      assert.equal(catanzaro.length,887);
      assert.equal(catanzaro.filter(r=>r.source_key==='catanzaro-listed').length,610);
      assert.equal(catanzaro.filter(r=>r.source_key==='catanzaro-applicants').length,277);
      assert.deepEqual(statusCounts(catanzaro),{listed:377,pending:277,renewal_update_in_progress:233});
      assert.equal(new Set(catanzaro.map(r=>r.record_locator)).size,887);
      assert.equal(catanzaro.filter(r=>r.source_key==='catanzaro-listed'&&r.identifiers.length>0).length,601);
      assert.equal(catanzaro.filter(r=>r.source_key==='catanzaro-applicants'&&r.identifiers.length>0).length,272);
      assert.equal(catanzaro.filter(r=>r.source_key==='catanzaro-listed'&&Array.isArray(r.source_fields?.physical_locators)).length,610);
      assert.equal(catanzaro.filter(r=>r.source_key==='catanzaro-applicants'&&typeof r.source_fields?.physical_locator==='string').length,277);
      assert.equal(catanzaro.filter(r=>r.source_key==='catanzaro-applicants'&&r.source_fields?.application_date_raw==='1/8/12/2025'&&r.application_date==='').length,1);
"""
browser = replace_one(
    browser,
    pisa_browser_tail,
    catanzaro_browser,
    label="browser Catanzaro invariants",
)
browser_path.write_text(browser, encoding="utf-8")
