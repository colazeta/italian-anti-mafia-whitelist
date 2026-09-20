import json
from pathlib import Path

pages = json.loads(Path('tmp/ravenna-extracted-tables.json').read_text(encoding='utf-8'))
rows = []
for p in pages:
    table = p['tables'][0]
    for row in table[1:]:
        rows.append({'page': p['page'], 'row': row})

target_ordinals = {13,116,191,230,268,339,504,562,579,643,664,665,666,703}
selected = []
for ordinal in sorted(target_ordinals):
    for current in range(max(1, ordinal-1), min(len(rows), ordinal+1)+1):
        item = rows[current-1]
        cells = item['row']
        selected.append({
            'target': ordinal,
            'ordinal': current,
            'page': item['page'],
            'cells': cells,
            'company_repr': repr(cells[1] if len(cells)>1 else ''),
            'company_codepoints': [ord(c) for c in (cells[1] if len(cells)>1 else '')],
        })
Path('tmp/ravenna-row-diagnostic.json').write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(selected, ensure_ascii=False, indent=2))
