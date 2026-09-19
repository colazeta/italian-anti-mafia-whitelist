from pathlib import Path

src = Path('.github/workflows/public-pages.yml')
text = src.read_text(encoding='utf-8')


def once(old: str, new: str, label: str) -> None:
    global text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected one anchor, found {n}')
    text = text.replace(old, new, 1)


once("      - 'src/white_list_archive/parsers/cuneo_positioned.py'\n", "      - 'src/white_list_archive/parsers/cuneo_positioned.py'\n      - 'src/white_list_archive/parsers/fermo_openxml.py'\n", 'parser path')
once("assert reg['meta']['record_count'] == 63925", "assert reg['meta']['record_count'] == 64174", 'record count')
once("'chieti','cremona','cuneo'}", "'chieti','cremona','cuneo','fermo'}", 'authority set')
once("'chieti-ordinary','cremona-ordinary','cuneo-ordinary'", "'chieti-ordinary','cremona-ordinary','cuneo-ordinary','fermo-ordinary'", 'register set')
once("assert reg['meta']['authority_count'] == 57", "assert reg['meta']['authority_count'] == 58", 'authority count')
once("assert reg['meta']['register_count'] == 59", "assert reg['meta']['register_count'] == 60", 'register count')
once("assert pref['meta']['published_count'] == 57", "assert pref['meta']['published_count'] == 58", 'published count')
once("assert pref['meta']['mapped_count'] == 57", "assert pref['meta']['mapped_count'] == 58", 'mapped count')
anchor = "          assert len({r['record_locator'] for r in cuneo_records}) == 516\n"
addition = """          fermo = [x for x in pref['prefectures'] if x['authority_key'] == 'fermo']
          assert len(fermo) == 1 and fermo[0]['mapped'] and fermo[0]['published'] and fermo[0]['series_count'] == 2
          fermo_records = [r for r in reg['records'] if r['authority_key'] == 'fermo']
          assert len(fermo_records) == 249
          assert sum(r['source_key'] == 'fermo-listed' for r in fermo_records) == 174
          assert sum(r['source_key'] == 'fermo-applicants' for r in fermo_records) == 75
          assert sum(r['source_status'] == 'listed' for r in fermo_records) == 97
          assert sum(r['source_status'] == 'pending' for r in fermo_records) == 75
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in fermo_records) == 77
          assert sum(bool(r['identifiers']) for r in fermo_records) == 233
          assert len({r['record_locator'] for r in fermo_records}) == 249
"""
once(anchor, anchor + addition, 'Fermo assertions')

out = Path('tmp/fermo-public-pages-candidate.yml')
out.parent.mkdir(exist_ok=True)
out.write_text(text, encoding='utf-8')
