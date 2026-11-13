from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from white_list_archive.acquisition.published_monitoring import synchronise


def fixture():
    data = {'meta': {'record_count': 1, 'authority_count': 1, 'register_count': 1, 'source_count': 1,
                     'sources': [{'source_key': 'a-listed', 'authority_key': 'a', 'register_key': 'a-ordinary',
                                  'population_scope': 'listed', 'reference_date': '2026-11-05',
                                  'sha256': '1'*64, 'parser': 'a_parser'}]},
            'records': [{'source_key': 'a-listed', 'authority_key': 'a'}]}
    body = json.dumps(data).encode()
    manifest = {'release_tag': 'exact-reviewed', 'files': {'registry.json': {
        'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}}}
    state = {'prefectures': [{'authority_key': 'a', 'latest_source_reference_date': '2026-11-13',
                             'canonical_integration_validated': False, 'monitoring_status': 'SOURCE_CHANGED'},
                            {'authority_key': 'b', 'monitoring_status': 'NEVER_CHECKED'}]}
    return state, manifest, body


def test_selected_metadata_preserves_known_lag_and_independent_stages():
    state, manifest, body = fixture()
    original = deepcopy(state)
    result = synchronise(state, manifest, body)
    assert state == original
    a, b = result['prefectures']
    assert a['latest_source_reference_date'] == '2026-11-13'
    assert a['latest_selected_public_reference_date'] == '2026-11-05'
    assert a['canonical_integration_validated'] is False
    assert a['monitoring_status'] == 'SOURCE_CHANGED'
    assert b['latest_selected_public_reference_date'] is None
    assert b['selected_public_source_presences'] == 0
    assert result['selected_publication']['live_deployment_verified'] is None
    assert result['selected_publication']['freshness_of_all_sources_verified'] is False
    assert synchronise(result, manifest, body) == result


def test_mutated_public_bytes_cannot_update_monitoring():
    state, manifest, body = fixture()
    with pytest.raises(ValueError, match='byte identity'):
        synchronise(state, manifest, body + b' ')


def test_checked_in_monitoring_matches_exact_selected_release():
    root = Path(__file__).resolve().parents[1]
    state = json.loads((root/'data/monitoring/national_coverage.json').read_text())
    manifest = json.loads((root/'data/publication/public_snapshot.json').read_text())
    assert state['selected_publication']['release_tag'] == manifest['release_tag']
    assert state['selected_publication']['registry_sha256'] == manifest['files']['registry.json']['sha256']
    assert sum(row['selected_public_source_presences'] for row in state['prefectures']) == state['selected_publication']['source_presences']
