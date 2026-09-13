from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "tests/public_portal_browser.cjs"
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if text.count(old) != 1:
        raise RuntimeError(f"browser gate anchor drift for {label}: found {text.count(old)}")
    text = text.replace(old, new, 1)


replace_once(
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Frosinone'));\n",
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Frosinone'));\n"
    "      assert.ok(labels.includes('White List ordinaria · Prefettura di Gorizia'));\n",
    "Gorizia register label",
)
replace_once(
    "      assert.equal(stats.total,32543);\n",
    "      assert.equal(stats.total,32670);\n",
    "current national total",
)
replace_once(
    "'forli-cesena','frosinone'].includes(r.authority_key));\n",
    "'forli-cesena','frosinone','gorizia'].includes(r.authority_key));\n",
    "pre-expansion baseline exclusion set",
)
replace_once(
    "      assert.equal(frosinone.filter(r=>r.source_fields&&Array.isArray(r.source_fields.application_date_raw_variants)&&r.source_fields.application_date_raw_variants.includes('13/05/206')&&r.application_date==='').length,1);\n",
    "      assert.equal(frosinone.filter(r=>r.source_fields&&Array.isArray(r.source_fields.application_date_raw_variants)&&r.source_fields.application_date_raw_variants.includes('13/05/206')&&r.application_date==='').length,1);\n"
    "      const gorizia=registry.records.filter(r=>r.authority_key==='gorizia');\n"
    "      assert.equal(gorizia.length,127);\n"
    "      assert.equal(gorizia.filter(r=>r.source_key==='gorizia-listed').length,117);\n"
    "      assert.equal(gorizia.filter(r=>r.source_key==='gorizia-applicants').length,10);\n"
    "      assert.deepEqual(statusCounts(gorizia),{listed:86,pending:10,renewal_update_in_progress:31});\n",
    "Gorizia browser invariants",
)
path.write_text(text, encoding="utf-8")
