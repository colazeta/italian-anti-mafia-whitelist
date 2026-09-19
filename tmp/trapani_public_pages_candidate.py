from pathlib import Path

SOURCE = Path('.github/workflows/public-pages.yml')
TARGET = Path('tmp/trapani-public-pages-candidate.yml')
text = SOURCE.read_text(encoding='utf-8')


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one anchor, found {count}')
    text = text.replace(old, new, 1)


replace_once(
    "      - 'src/white_list_archive/parsers/lucca_tables.py'\n",
    "      - 'src/white_list_archive/parsers/lucca_tables.py'\n      - 'src/white_list_archive/parsers/trapani_tables.py'\n",
    'Trapani workflow path trigger',
)
replace_once("assert reg['meta']['record_count'] == 66625", "assert reg['meta']['record_count'] == 67180", 'public record count')
replace_once("'imperia','lucca','macerata'}", "'imperia','lucca','macerata','trapani'}", 'public authority set')
replace_once("'imperia-ordinary','lucca-ordinary','macerata-ordinary'", "'imperia-ordinary','lucca-ordinary','macerata-ordinary','trapani-ordinary'", 'public register set')
replace_once("assert reg['meta']['authority_count'] == 62", "assert reg['meta']['authority_count'] == 63", 'public authority count')
replace_once("assert reg['meta']['register_count'] == 64", "assert reg['meta']['register_count'] == 65", 'public register count')
replace_once("assert pref['meta']['published_count'] == 62", "assert pref['meta']['published_count'] == 63", 'published count')
replace_once("assert pref['meta']['mapped_count'] == 62", "assert pref['meta']['mapped_count'] == 63", 'mapped count')

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
replace_once(anchor, block, 'Trapani public assertions')

TARGET.write_text(text, encoding='utf-8')
print(f'wrote {TARGET} ({TARGET.stat().st_size} bytes)')
