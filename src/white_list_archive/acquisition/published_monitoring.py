"""Synchronise selected-public-source metadata without claiming source freshness."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path


def synchronise(state, manifest, registry_bytes):
    """Use the actual SHA-pinned derivative, never the prospective source config."""
    pin = manifest['files']['registry.json']
    if len(registry_bytes) != pin['bytes'] or hashlib.sha256(registry_bytes).hexdigest() != pin['sha256']:
        raise ValueError('Selected public registry fails exact byte identity')
    data = json.loads(registry_bytes)
    meta, records = data['meta'], data['records']
    authorities = {row['authority_key'] for row in records}
    sources = meta['sources']
    if (len(records) != meta['record_count'] or len(authorities) != meta['authority_count']
            or len(sources) != meta['source_count']):
        raise ValueError('Selected public registry aggregate contract drift')
    keys = [source['source_key'] for source in sources]
    counts = Counter(row['source_key'] for row in records)
    if len(keys) != len(set(keys)) or set(counts) != set(keys):
        raise ValueError('Public source identities are missing or duplicated')
    known = {row['authority_key'] for row in state['prefectures']}
    if not authorities <= known:
        raise ValueError('Public authority lies outside monitoring universe')
    scopes = defaultdict(list)
    for source in sources:
        reference = source['reference_date']
        if reference and date.fromisoformat(reference).isoformat() != reference:
            raise ValueError('Non-canonical source reference date')
        scopes[source['authority_key']].append({
            name: source[name] for name in ('source_key', 'register_key', 'population_scope',
                                           'reference_date', 'sha256', 'parser')})
    result = deepcopy(state)
    result['selected_publication'] = {
        'release_tag': manifest['release_tag'], 'registry_sha256': pin['sha256'],
        'source_presences': len(records), 'authority_count': len(authorities),
        'register_count': meta['register_count'], 'source_count': len(sources),
        'unit': 'source_document_presences_not_distinct_businesses',
        'live_deployment_verified': None,
        'freshness_of_all_sources_verified': False,
    }
    for row in result['prefectures']:
        source_rows = sorted(scopes.get(row['authority_key'], []), key=lambda s: s['source_key'])
        row['selected_public_sources'] = source_rows
        row['selected_public_source_presences'] = sum(counts[s['source_key']] for s in source_rows)
        dates = [s['reference_date'] for s in source_rows if s['reference_date']]
        row['latest_selected_public_reference_date'] = max(dates, default=None)
        # Keep any independently recorded later source date; publication does not
        # erase known lag. Do not change capture, canonical or monitoring states.
        if dates:
            row['latest_source_reference_date'] = max(
                [*dates, *([row['latest_source_reference_date']] if row.get('latest_source_reference_date') else [])])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=Path('data/monitoring/national_coverage.json'))
    parser.add_argument('--manifest', type=Path, default=Path('data/publication/public_snapshot.json'))
    parser.add_argument('--registry', type=Path, required=True)
    args = parser.parse_args(argv)
    result = synchronise(json.loads(args.state.read_text()), json.loads(args.manifest.read_text()), args.registry.read_bytes())
    args.state.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result['selected_publication'], sort_keys=True))


if __name__ == '__main__':
    main()
