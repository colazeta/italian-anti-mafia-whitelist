from collections import Counter
import json
from pathlib import Path

reg = json.loads(Path('/tmp/trapani-national/registry.json').read_text())
pref = json.loads(Path('/tmp/trapani-national/prefectures.json').read_text())

assert reg['meta']['record_count'] == 67180, reg['meta']
assert reg['meta']['authority_count'] == 63, reg['meta']
assert reg['meta']['register_count'] == 65, reg['meta']
assert pref['meta']['published_count'] == 63, pref['meta']
assert pref['meta']['mapped_count'] == 63, pref['meta']

rows = [row for row in reg['records'] if row['authority_key'] == 'trapani']
assert len(rows) == 555
assert Counter(row['source_key'] for row in rows) == Counter({'trapani-listed': 333, 'trapani-applicants': 222})
assert Counter(row['source_status'] for row in rows) == Counter({'pending': 222, 'listed': 177, 'renewal_update_in_progress': 156})
assert sum(bool(row['identifiers']) for row in rows) == 555
assert len({row['record_locator'] for row in rows}) == 555

special = [row for row in rows if row['source_key'] == 'trapani-listed' and row['identifier_field_raw'] == '05913370820']
assert len(special) == 1
assert special[0]['observed_expiry_date'] == ''
assert special[0]['source_fields']['expiry_date_raw_variants'] == ['In amministrazio ne giudiziaria e fermo restando fino al permanere della stessa']

print({
    'national_records': len(reg['records']),
    'authority_count': reg['meta']['authority_count'],
    'register_count': reg['meta']['register_count'],
    'trapani_records': len(rows),
    'trapani_status': dict(Counter(row['source_status'] for row in rows)),
})
