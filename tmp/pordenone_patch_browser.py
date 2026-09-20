from pathlib import Path

path = Path('tests/public_portal_browser.cjs')
text = path.read_text(encoding='utf-8')

def once(old, new):
    global text
    assert text.count(old) == 1, (old, text.count(old))
    text = text.replace(old, new, 1)

if "White List ordinaria · Prefettura di Pordenone" not in text:
    once("      assert.ok(labels.includes('White List ricostruzione · Prefettura di Ferrara'));\n", "      assert.ok(labels.includes('White List ricostruzione · Prefettura di Ferrara'));\n      assert.ok(labels.includes('White List ordinaria · Prefettura di Pordenone'));\n")
once("assert.equal(stats.total,71057);", "assert.equal(stats.total,71490);")
once("'macerata','trapani','palermo','matera','siracusa','ferrara'].includes(r.authority_key)", "'macerata','trapani','palermo','matera','siracusa','ferrara','pordenone'].includes(r.authority_key)")
block = """      const pordenone=registry.records.filter(r=>r.authority_key==='pordenone');
      assert.equal(pordenone.length,433);
      assert.equal(pordenone.filter(r=>r.source_key==='pordenone-provincial-listed').length,401);
      assert.equal(pordenone.filter(r=>r.source_key==='pordenone-provincial-applicants').length,32);
      assert.deepEqual(statusCounts(pordenone),{listed:335,other_or_unknown:1,pending:31,renewal_update_in_progress:66});
      assert.equal(new Set(pordenone.map(r=>r.record_locator)).size,433);
      assert.equal(pordenone.filter(r=>r.identifiers.length>0).length,266);
      assert.equal(pordenone.filter(r=>r.source_key==='pordenone-provincial-applicants'&&!r.name&&r.registered_office==='SEQUALS - VIA CECILIA DANIELI, 7'&&r.identifiers.includes('01456650934')).length,1);
"""
if "const pordenone=registry.records.filter(r=>r.authority_key==='pordenone');" not in text:
    once("      assert.equal(ferrara.filter(r=>r.identifiers.length>0).length,1563);\n", "      assert.equal(ferrara.filter(r=>r.identifiers.length>0).length,1563);\n" + block)
path.write_text(text, encoding='utf-8')
