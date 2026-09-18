from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / '.github/workflows/public-pages.yml'
out = ROOT / 'tmp/public-pages-taranto.yml'
text = source.read_text(encoding='utf-8')

def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected one anchor, found {count}')
    text = text.replace(old, new, 1)

replace_once("      - 'src/white_list_archive/parsers/firenze_sources.py'\n", "      - 'src/white_list_archive/parsers/firenze_sources.py'\n      - 'src/white_list_archive/parsers/taranto_html.py'\n", 'parser path')
replace_once("          assert reg['meta']['record_count'] == 59042\n", "          assert reg['meta']['record_count'] == 59642\n", 'record count')
replace_once("'como','firenze'}\n", "'como','firenze','taranto'}\n", 'authority set')
replace_once("'como-ordinary','firenze-ordinary'\n", "'como-ordinary','firenze-ordinary','taranto-ordinary'\n", 'register set')
replace_once("          assert reg['meta']['authority_count'] == 50\n", "          assert reg['meta']['authority_count'] == 51\n", 'authority count')
replace_once("          assert reg['meta']['register_count'] == 52\n", "          assert reg['meta']['register_count'] == 53\n", 'register count')
replace_once("          assert pref['meta']['published_count'] == 50\n", "          assert pref['meta']['published_count'] == 51\n", 'published count')
replace_once("          assert pref['meta']['mapped_count'] == 50\n", "          assert pref['meta']['mapped_count'] == 51\n", 'mapped count')
marker = "          assert sum(not bool(r['registered_office']) for r in firenze_applicants) == 2\n"
taranto = """          taranto = [x for x in pref['prefectures'] if x['authority_key'] == 'taranto']
          assert len(taranto) == 1 and taranto[0]['mapped'] and taranto[0]['published'] and taranto[0]['series_count'] == 2
          taranto_records = [r for r in reg['records'] if r['authority_key'] == 'taranto']
          assert len(taranto_records) == 600
          assert sum(r['source_key'] == 'taranto-listed' for r in taranto_records) == 388
          assert sum(r['source_key'] == 'taranto-applicants' for r in taranto_records) == 212
          assert sum(r['source_status'] == 'listed' for r in taranto_records) == 212
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in taranto_records) == 176
          assert sum(r['source_status'] == 'pending' for r in taranto_records) == 212
          assert len({r['record_locator'] for r in taranto_records}) == 600
          assert sum(bool(r['identifiers']) for r in taranto_records) == 592
          assert sum(bool(r['identifier_field_raw']) and not r['identifiers'] for r in taranto_records) == 8
          assert sum(bool(r.get('source_fields', {}).get('malformed_date_pairs')) for r in taranto_records if r['source_key'] == 'taranto-listed') == 8
"""
replace_once(marker, marker + taranto, 'Taranto exact assertions')
out.write_text(text, encoding='utf-8')
