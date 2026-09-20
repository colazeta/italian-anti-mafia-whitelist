import json
from pathlib import Path

path = Path('data/monitoring/national_coverage.json')
data = json.loads(path.read_text(encoding='utf-8'))
rows = [row for row in data['prefectures'] if row['authority_key'] == 'pordenone']
assert len(rows) == 1
row = rows[0]
assert row['source_verified'] is True
assert row['parser_validated'] is True
assert row['company_observations_loaded'] is True
row['official_landing_page'] = 'https://prefettura.interno.gov.it/it/prefetture/pordenone/white-list-elenco-ditte-iscritte'
row['canonical_integration_validated'] = False
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
