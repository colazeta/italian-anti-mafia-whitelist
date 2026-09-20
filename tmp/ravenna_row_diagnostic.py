import json
from pathlib import Path

pages = json.loads(Path('tmp/ravenna-extracted-tables.json').read_text(encoding='utf-8'))
rows = []
for p in pages:
    for row in p['tables'][0][1:]:
        rows.append({'page': p['page'], 'row': row})

selected = []
for ordinal, item in enumerate(rows, 1):
    cells = item['row']
    if cells and cells[0] == '1199':
        selected.append({'ordinal': ordinal, 'page': item['page'], 'cells': cells})
assert len(selected) == 1, selected
Path('tmp/ravenna-row-diagnostic.json').write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(selected, ensure_ascii=False, indent=2))
