from pathlib import Path

source = Path('.github/workflows/public-pages.yml')
path = Path('tmp/pordenone-public-pages.yml')
text = source.read_text(encoding='utf-8')

def once(old, new):
    global text
    assert text.count(old) == 1, (old, text.count(old))
    text = text.replace(old, new, 1)

if "src/white_list_archive/parsers/pordenone_tables.py" not in text:
    once("      - 'src/white_list_archive/parsers/ferrara_tables.py'\n", "      - 'src/white_list_archive/parsers/ferrara_tables.py'\n      - 'src/white_list_archive/parsers/pordenone_tables.py'\n")
once("assert reg['meta']['record_count'] == 71057", "assert reg['meta']['record_count'] == 71490")
once("assert reg['meta']['authority_count'] == 67", "assert reg['meta']['authority_count'] == 68")
once("assert reg['meta']['register_count'] == 70", "assert reg['meta']['register_count'] == 71")
once("assert pref['meta']['published_count'] == 67", "assert pref['meta']['published_count'] == 68")
once("assert pref['meta']['mapped_count'] == 67", "assert pref['meta']['mapped_count'] == 68")
once("'macerata','trapani','palermo','matera','siracusa','ferrara'}", "'macerata','trapani','palermo','matera','siracusa','ferrara','pordenone'}")
once("'ferrara-ordinary','ferrara-reconstruction'\n          }", "'ferrara-ordinary','ferrara-reconstruction','pordenone-ordinary'\n          }")
block = """          pordenone = [x for x in pref['prefectures'] if x['authority_key'] == 'pordenone']
          assert len(pordenone) == 1 and pordenone[0]['mapped'] and pordenone[0]['published'] and pordenone[0]['series_count'] == 2
          pordenone_records = [r for r in reg['records'] if r['authority_key'] == 'pordenone']
          assert len(pordenone_records) == 433
          assert sum(r['source_key'] == 'pordenone-provincial-listed' for r in pordenone_records) == 401
          assert sum(r['source_key'] == 'pordenone-provincial-applicants' for r in pordenone_records) == 32
          assert sum(r['source_status'] == 'listed' for r in pordenone_records) == 335
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in pordenone_records) == 66
          assert sum(r['source_status'] == 'other_or_unknown' for r in pordenone_records) == 1
          assert sum(r['source_status'] == 'pending' for r in pordenone_records) == 31
          assert sum(bool(r['identifiers']) for r in pordenone_records) == 266
          assert len({r['record_locator'] for r in pordenone_records}) == 433
"""
if "pordenone_records = [r for r in reg['records'] if r['authority_key'] == 'pordenone']" not in text:
    once("          assert len({r['record_locator'] for r in ferrara_records}) == 1583\n", "          assert len({r['record_locator'] for r in ferrara_records}) == 1583\n" + block)
path.write_text(text, encoding='utf-8')
