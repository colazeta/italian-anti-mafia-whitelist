"""Public robot directory: configuration/capability metadata, no company rows."""
import json
from pathlib import Path

from white_list_archive.acquisition.prefecture_robots import CATALOG


def public_directory(catalog):
    return {'schema_version': 1, 'schedule': 'daily', 'robots': [
        {'authority_key': r['authority_key'], 'name': r['name'], 'region': r['region'],
         'landing_pages': r['landing_pages'], 'reviewed_resources': len(r['sources']),
         'population_mapping_reviewed': r['population_mapping_reviewed']}
        for r in catalog['robots']]}


def validate_public_robots(data):
    expected = public_directory(json.loads(CATALOG.read_text()))
    if data != expected:
        raise ValueError('Public robot directory differs from reviewed robot configuration')


if __name__ == '__main__':
    Path('public-site/data/robots.json').write_text(json.dumps(public_directory(json.loads(CATALOG.read_text())), ensure_ascii=False, separators=(',', ':'))+'\n')
