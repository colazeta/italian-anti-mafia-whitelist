import json
from pathlib import Path

import pytest

from white_list_archive.publishing import como_review as review
from white_list_archive.publishing.publication_handoff import _digest

ROOT = Path(__file__).resolve().parents[1]


def configs():
    return json.loads((ROOT/'data/publication/multi_prefecture_pilot.json').read_text())


def test_como_review_binds_both_populations_to_the_independent_source_and_public_census():
    config = configs()
    selected = [s for s in config['sources'] if s['authority_key'] == 'como']
    assert {s['source_key'] for s in selected} == set(review.PINS)
    assert {s['population_scope'] for s in selected} == {'listed', 'applicant'}
    intent = json.loads((ROOT/'data/publication/incremental_release_intent.json').read_text())
    assert intent['baseline_manifest_sha256'] == '0ac57b1838b4e6226572a7afc275ebb7b9e46c734fc98904330321f3cdfe7f28'
    assert intent['source_config_sha256'] == _digest(config)
    assert (ROOT/intent['review_document']).is_file()
    assert set(intent['changes']) == set(review.PINS)
    for cfg in selected:
        review.qualify_configuration(cfg)
        spec, profile = intent['changes'][cfg['source_key']], review.PINS[cfg['source_key']]
        assert spec == {'count': profile['records'], 'statuses': profile['statuses'],
                        'reference_date': review.REFERENCE_DATE, 'sha256': profile['sha256'],
                        'parser': cfg['parser'], 'records_sha256': review.PUBLIC_RECORD_DIGESTS[cfg['source_key']]}
    preserved = set(json.loads((ROOT/'data/publication/preserved_public_sources.json').read_text()))
    all_keys = {s['source_key'] for s in config['sources']}
    selected_manifest = json.loads((ROOT/'data/publication/public_snapshot.json').read_text())
    if intent['baseline_manifest_sha256'] == _digest(selected_manifest):
        # Pending publication: only the explicitly reviewed changed scopes are fresh.
        assert preserved == all_keys - set(review.PINS)
    else:
        # The prior finite intent has already been selected: revalidate every
        # approved scope from exact immutable public derivatives, not live URLs.
        assert preserved == all_keys
    assert {'biella-listed', 'biella-applicants'} <= preserved


@pytest.mark.parametrize('field,value', [
    ('reference_date', '2026-11-11'), ('parser', 'unreviewed'), ('population_scope', 'applicant'),
    ('resource_url', 'https://example.invalid/source'), ('source_page_url', 'https://example.invalid/page'),
    ('approval_mode', 'semantic_sha256'), ('expected_source_rows', 399), ('sha256', '0'*64),
    ('semantic_sha256', '0'*64), ('resources', {'new': {}}), ('register_key', 'different-register'),
])
def test_production_source_binding_cannot_drift_from_the_review(field, value):
    cfg = next(s for s in configs()['sources'] if s['source_key'] == 'como-listed')
    with pytest.raises(ValueError, match='binding drift'):
        review.qualify_configuration({**cfg, field: value})


def test_production_qa_rejects_unreviewed_public_values_even_if_source_inspection_returns(monkeypatch, capsys):
    monkeypatch.setattr(review, '_download', lambda url, path: path.write_bytes(b'synthetic'))
    monkeypatch.setattr(review, 'inspect', lambda *a, **k: {'public_records_sha256': '0'*64})
    assert review.main(reviewed_config=True) == 1
    result = json.loads(capsys.readouterr().out)
    assert {s['failure_code'] for s in result['sources']} == {'public_records_mismatch'}
    assert result['publications'] == 0 and result['approval_granted'] is False
