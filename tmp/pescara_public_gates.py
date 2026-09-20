from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


public_path = ROOT / ".github/workflows/public-pages.yml"
public = public_path.read_text(encoding="utf-8")
public = replace_once(
    public,
    "      - 'src/white_list_archive/parsers/ravenna_combined.py'\n      - 'src/white_list_archive/parsers/macerata_tables.py'",
    "      - 'src/white_list_archive/parsers/ravenna_combined.py'\n      - 'src/white_list_archive/parsers/pescara_legacy_doc.py'\n      - 'src/white_list_archive/parsers/macerata_tables.py'",
    "public parser watch",
)
public = replace_once(public, "assert reg['meta']['record_count'] == 72456", "assert reg['meta']['record_count'] == 73098", "public record count")
public = replace_once(public, "'viterbo','ravenna'}", "'viterbo','ravenna','pescara'}", "public authority set")
public = replace_once(public, "'viterbo-ordinary','ravenna-ordinary'\n          }", "'viterbo-ordinary','ravenna-ordinary','pescara-ordinary'\n          }", "public register set")
public = replace_once(public, "assert reg['meta']['authority_count'] == 70", "assert reg['meta']['authority_count'] == 71", "public authority count")
public = replace_once(public, "assert reg['meta']['register_count'] == 73", "assert reg['meta']['register_count'] == 74", "public register count")
public = replace_once(public, "assert pref['meta']['published_count'] == 70", "assert pref['meta']['published_count'] == 71", "public published count")
public = replace_once(public, "assert pref['meta']['mapped_count'] == 70", "assert pref['meta']['mapped_count'] == 71", "public mapped count")
public_anchor = "          assert len({r['record_locator'] for r in ravenna_records}) == 706\n"
public_block = public_anchor + """          pescara = [x for x in pref['prefectures'] if x['authority_key'] == 'pescara']
          assert len(pescara) == 1 and pescara[0]['mapped'] and pescara[0]['published'] and pescara[0]['series_count'] == 2
          pescara_records = [r for r in reg['records'] if r['authority_key'] == 'pescara']
          assert len(pescara_records) == 642
          assert sum(r['source_key'] == 'pescara-listed' for r in pescara_records) == 607
          assert sum(r['source_key'] == 'pescara-applicants' for r in pescara_records) == 35
          assert sum(r['source_status'] == 'listed' for r in pescara_records) == 456
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in pescara_records) == 150
          assert sum(r['source_status'] == 'other_or_unknown' for r in pescara_records) == 1
          assert sum(r['source_status'] == 'pending' for r in pescara_records) == 35
          assert sum(bool(r['identifiers']) for r in pescara_records) == 613
          assert len({r['record_locator'] for r in pescara_records}) == 642
"""
public = replace_once(public, public_anchor, public_block, "public Pescara assertions")

browser_path = ROOT / "tests/public_portal_browser.cjs"
browser = browser_path.read_text(encoding="utf-8")
browser = replace_once(
    browser,
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Ravenna'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Macerata'));",
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Ravenna'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Pescara'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Macerata'));",
    "browser Pescara label",
)
browser = replace_once(browser, "assert.equal(stats.total,72456);", "assert.equal(stats.total,73098);", "browser total")
browser = replace_once(browser, "'viterbo','ravenna'].includes", "'viterbo','ravenna','pescara'].includes", "browser exclusion list")
browser_anchor = "      assert.equal(ravenna.filter(r=>Object.prototype.hasOwnProperty.call(r.source_fields,'source_progressive')||Object.prototype.hasOwnProperty.call(r.source_fields,'reviewed_extraction_repair')).length,0);\n"
browser_block = browser_anchor + """      const pescara=registry.records.filter(r=>r.authority_key==='pescara');
      assert.equal(pescara.length,642);
      assert.equal(pescara.filter(r=>r.source_key==='pescara-listed').length,607);
      assert.equal(pescara.filter(r=>r.source_key==='pescara-applicants').length,35);
      assert.deepEqual(statusCounts(pescara),{listed:456,other_or_unknown:1,pending:35,renewal_update_in_progress:150});
      assert.equal(new Set(pescara.map(r=>r.record_locator)).size,642);
      assert.equal(pescara.filter(r=>r.identifiers.length>0).length,613);
"""
browser = replace_once(browser, browser_anchor, browser_block, "browser Pescara assertions")

out = ROOT / "tmp"
out.mkdir(exist_ok=True)
(out / "pescara-public-pages-candidate.yml").write_text(public, encoding="utf-8")
(out / "pescara-public-browser-candidate.cjs").write_text(browser, encoding="utf-8")
print("Pescara public gate candidates staged")
