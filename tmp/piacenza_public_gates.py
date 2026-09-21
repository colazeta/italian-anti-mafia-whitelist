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
    "      - 'src/white_list_archive/parsers/pescara_legacy_doc.py'\n      - 'src/white_list_archive/parsers/macerata_tables.py'",
    "      - 'src/white_list_archive/parsers/pescara_legacy_doc.py'\n      - 'src/white_list_archive/parsers/piacenza_legacy_xls.py'\n      - 'src/white_list_archive/parsers/macerata_tables.py'",
    "public parser watch",
)
public = replace_once(public, "assert reg['meta']['record_count'] == 73098", "assert reg['meta']['record_count'] == 73668", "public record count")
public = replace_once(public, "'viterbo','ravenna','pescara'}", "'viterbo','ravenna','pescara','piacenza'}", "public authority set")
public = replace_once(public, "'viterbo-ordinary','ravenna-ordinary','pescara-ordinary'\n          }", "'viterbo-ordinary','ravenna-ordinary','pescara-ordinary','piacenza-ordinary'\n          }", "public register set")
public = replace_once(public, "assert reg['meta']['authority_count'] == 71", "assert reg['meta']['authority_count'] == 72", "public authority count")
public = replace_once(public, "assert reg['meta']['register_count'] == 74", "assert reg['meta']['register_count'] == 75", "public register count")
public = replace_once(public, "assert pref['meta']['published_count'] == 71", "assert pref['meta']['published_count'] == 72", "public published count")
public = replace_once(public, "assert pref['meta']['mapped_count'] == 71", "assert pref['meta']['mapped_count'] == 72", "public mapped count")
public_anchor = "          assert len({r['record_locator'] for r in pescara_records}) == 642\n"
public_block = public_anchor + """          piacenza = [x for x in pref['prefectures'] if x['authority_key'] == 'piacenza']
          assert len(piacenza) == 1 and piacenza[0]['mapped'] and piacenza[0]['published'] and piacenza[0]['series_count'] == 2
          piacenza_records = [r for r in reg['records'] if r['authority_key'] == 'piacenza']
          assert len(piacenza_records) == 570
          assert sum(r['source_key'] == 'piacenza-listed' for r in piacenza_records) == 552
          assert sum(r['source_key'] == 'piacenza-applicants' for r in piacenza_records) == 18
          assert sum(r['source_status'] == 'listed' for r in piacenza_records) == 455
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in piacenza_records) == 97
          assert sum(r['source_status'] == 'pending' for r in piacenza_records) == 18
          assert sum(bool(r['identifiers']) for r in piacenza_records) == 558
          assert len({r['record_locator'] for r in piacenza_records}) == 570
"""
public = replace_once(public, public_anchor, public_block, "public Piacenza assertions")

browser_path = ROOT / "tests/public_portal_browser.cjs"
browser = browser_path.read_text(encoding="utf-8")
browser = replace_once(
    browser,
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Pescara'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Macerata'));",
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Pescara'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Piacenza'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Macerata'));",
    "browser Piacenza label",
)
browser = replace_once(browser, "assert.equal(stats.total,73098);", "assert.equal(stats.total,73668);", "browser total")
browser = replace_once(browser, "'viterbo','ravenna','pescara'].includes", "'viterbo','ravenna','pescara','piacenza'].includes", "browser exclusion list")
browser_anchor = "      assert.equal(pescara.filter(r=>r.identifiers.length>0).length,613);\n"
browser_block = browser_anchor + """      const piacenza=registry.records.filter(r=>r.authority_key==='piacenza');
      assert.equal(piacenza.length,570);
      assert.equal(piacenza.filter(r=>r.source_key==='piacenza-listed').length,552);
      assert.equal(piacenza.filter(r=>r.source_key==='piacenza-applicants').length,18);
      assert.deepEqual(statusCounts(piacenza),{listed:455,pending:18,renewal_update_in_progress:97});
      assert.equal(new Set(piacenza.map(r=>r.record_locator)).size,570);
      assert.equal(piacenza.filter(r=>r.identifiers.length>0).length,558);
"""
browser = replace_once(browser, browser_anchor, browser_block, "browser Piacenza assertions")

out = ROOT / "tmp"
out.mkdir(exist_ok=True)
(out / "piacenza-public-pages-candidate.yml").write_text(public, encoding="utf-8")
(out / "piacenza-public-browser-candidate.cjs").write_text(browser, encoding="utf-8")
print("Piacenza public gate candidates staged")
