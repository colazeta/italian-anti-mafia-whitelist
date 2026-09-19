from __future__ import annotations

from pathlib import Path

SCRIPT = Path('tmp/trapani_integration_materialize.py')
source = SCRIPT.read_text(encoding='utf-8')


def patch(old: str, new: str, label: str) -> None:
    global source
    count = source.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one materializer anchor, found {count}')
    source = source.replace(old, new, 1)


# Rebase only the old Lucca-era materializer anchors onto the current Macerata main.
patch(
    "if by_id['verified-primary-pages']['record_count'] != '61' or by_id['source-series-inventory']['record_count'] != '120':",
    "if by_id['verified-primary-pages']['record_count'] != '62' or by_id['source-series-inventory']['record_count'] != '122':",
    'catalog denominator guard',
)
patch("by_id['verified-primary-pages']['record_count'] = '62'", "by_id['verified-primary-pages']['record_count'] = '63'", 'catalog primary-page target')
patch("by_id['source-series-inventory']['record_count'] = '122'", "by_id['source-series-inventory']['record_count'] = '124'", 'catalog series target')

patch(
    "('assert report[\"verified_authority_count\"] == 61', 'assert report[\"verified_authority_count\"] == 62', 'verified authority denominator'),",
    "('assert report[\"verified_authority_count\"] == 62', 'assert report[\"verified_authority_count\"] == 63', 'verified authority denominator'),",
    'coverage authority denominator',
)
patch(
    "('assert report[\"register_scope_count\"] == 63', 'assert report[\"register_scope_count\"] == 64', 'register scope denominator'),",
    "('assert report[\"register_scope_count\"] == 64', 'assert report[\"register_scope_count\"] == 65', 'register scope denominator'),",
    'coverage register denominator',
)
patch(
    "('assert report[\"complete_register_scope_count\"] == 63', 'assert report[\"complete_register_scope_count\"] == 64', 'complete scope denominator'),",
    "('assert report[\"complete_register_scope_count\"] == 64', 'assert report[\"complete_register_scope_count\"] == 65', 'complete scope denominator'),",
    'coverage complete denominator',
)

patch(
    "text = expect_once(text, \"assert reg['meta']['record_count'] == 65267\", \"assert reg['meta']['record_count'] == 65822\", 'public record count')",
    "text = expect_once(text, \"assert reg['meta']['record_count'] == 66625\", \"assert reg['meta']['record_count'] == 67180\", 'public record count')",
    'public record count',
)
patch(
    "text = expect_once(text, \"'imperia','lucca'}\", \"'imperia','lucca','trapani'}\", 'public authority set')",
    "text = expect_once(text, \"'imperia','lucca','macerata'}\", \"'imperia','lucca','macerata','trapani'}\", 'public authority set')",
    'public authority set',
)
patch(
    "text = expect_once(text, \"'imperia-ordinary','lucca-ordinary'\", \"'imperia-ordinary','lucca-ordinary','trapani-ordinary'\", 'public register set')",
    "text = expect_once(text, \"'imperia-ordinary','lucca-ordinary','macerata-ordinary'\", \"'imperia-ordinary','lucca-ordinary','macerata-ordinary','trapani-ordinary'\", 'public register set')",
    'public register set',
)
patch(
    "text = expect_once(text, \"assert reg['meta']['authority_count'] == 61\", \"assert reg['meta']['authority_count'] == 62\", 'public authority count')",
    "text = expect_once(text, \"assert reg['meta']['authority_count'] == 62\", \"assert reg['meta']['authority_count'] == 63\", 'public authority count')",
    'public authority count',
)
patch(
    "text = expect_once(text, \"assert reg['meta']['register_count'] == 63\", \"assert reg['meta']['register_count'] == 64\", 'public register count')",
    "text = expect_once(text, \"assert reg['meta']['register_count'] == 64\", \"assert reg['meta']['register_count'] == 65\", 'public register count')",
    'public register count',
)
patch(
    "text = expect_once(text, \"assert pref['meta']['published_count'] == 61\", \"assert pref['meta']['published_count'] == 62\", 'published count')",
    "text = expect_once(text, \"assert pref['meta']['published_count'] == 62\", \"assert pref['meta']['published_count'] == 63\", 'published count')",
    'published count',
)
patch(
    "text = expect_once(text, \"assert pref['meta']['mapped_count'] == 61\", \"assert pref['meta']['mapped_count'] == 62\", 'mapped count')",
    "text = expect_once(text, \"assert pref['meta']['mapped_count'] == 62\", \"assert pref['meta']['mapped_count'] == 63\", 'mapped count')",
    'mapped count',
)

patch(
    "text = expect_once(text, 'assert.equal(stats.total,65267);', 'assert.equal(stats.total,65822);', 'browser total')",
    "text = expect_once(text, 'assert.equal(stats.total,66625);', 'assert.equal(stats.total,67180);', 'browser total')",
    'browser total',
)
patch(
    "text = expect_once(text, \"'imperia','lucca'].includes(r.authority_key)\", \"'imperia','lucca','trapani'].includes(r.authority_key)\", 'browser baseline exclusion')",
    "text = expect_once(text, \"'imperia','lucca','macerata'].includes(r.authority_key)\", \"'imperia','lucca','macerata','trapani'].includes(r.authority_key)\", 'browser baseline exclusion')",
    'browser baseline exclusion',
)

# Execute the reviewed materializer only after all stale anchors are reconciled exactly once.
exec(compile(source, str(SCRIPT), 'exec'), {'__name__': '__main__', '__file__': str(SCRIPT)})

# The old branch carried the next source-registry denominator before materialisation.
# Current main is now legitimately at 62 after Macerata; Trapani advances it to 63.
path = Path('tests/test_source_registry.py')
text = path.read_text(encoding='utf-8')
old = '    assert len(pages) == 62\n'
new = '    assert len(pages) == 63\n'
if text.count(old) != 1:
    raise SystemExit(f'source-registry denominator: expected exactly one anchor, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')

# Make the explicit recently-resolved coverage regression list include Trapani.
path = Path('tests/test_source_population_coverage.py')
text = path.read_text(encoding='utf-8')
old = '        "macerata",\n'
new = '        "macerata",\n        "trapani",\n'
if text.count(old) != 1:
    raise SystemExit(f'recently-resolved authority list: expected exactly one anchor, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
