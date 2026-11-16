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
    # Como's approved source review remains pinned after newer finite release
    # intents (Taranto, etc.) supersede Como's historical intent file.
    intent = json.loads((ROOT/'data/publication/incremental_release_intent.json').read_text())
    assert intent['source_config_sha256'] == _digest(config)
    assert (ROOT/intent['review_document']).is_file()
    assert (ROOT/'docs/sources/como-publication-review-2026-11-10.md').is_file()
    for cfg in selected:
        review.qualify_configuration(cfg)
        profile = review.PINS[cfg['source_key']]
        assert cfg['reference_date'] == review.REFERENCE_DATE
        assert cfg['sha256'] == profile['sha256']
        assert profile['records'] > 0
        assert len(review.PUBLIC_RECORD_DIGESTS[cfg['source_key']]) == 64
    if set(intent['changes']) == set(review.PINS):
        # Preserve the historical Como exact-intent regression when this is
        # the current review: a new source cannot borrow an older Como intent.
        assert intent['baseline_manifest_sha256'] == '0ac57b1838b4e6226572a7afc275ebb7b9e46c734fc98904330321f3cdfe7f28'
        for cfg in selected:
            profile = review.PINS[cfg['source_key']]
            assert intent['changes'][cfg['source_key']] == {
                'count': profile['records'], 'statuses': profile['statuses'],
                'reference_date': review.REFERENCE_DATE, 'sha256': profile['sha256'],
                'parser': cfg['parser'], 'records_sha256': review.PUBLIC_RECORD_DIGESTS[cfg['source_key']]}
    preserved = set(json.loads((ROOT/'data/publication/preserved_public_sources.json').read_text()))
    all_keys = {s['source_key'] for s in config['sources']}
    selected_manifest = json.loads((ROOT/'data/publication/public_snapshot.json').read_text())
    if intent['baseline_manifest_sha256'] == _digest(selected_manifest):
        # Only new reviewed scopes are rebuilt. Selected Como is immutable.
        assert preserved == all_keys - set(intent['changes'])
    else:
        assert preserved == all_keys
    assert set(review.PINS) <= preserved
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


def test_como_selected_scope_mode_skips_only_complete_prior_reviewed_release():
    command = _load_qualifier_command()
    config = configs()
    keys = {s['source_key'] for s in config['sources']}
    selected = {'schema_version': 1, 'release_tag': 'reviewed-release', 'files': {}}
    historic_intent = {'baseline_manifest_sha256': 'older-review-baseline',
                       'changes': {'como-listed': {}}}
    assert command.selected_como_mode(config, sorted(keys), selected, historic_intent) == 'preserved'
    assert command.selected_como_mode(config, sorted(keys - set(review.PINS)), selected,
                                       historic_intent) == 'fresh'
    with pytest.raises(ValueError, match='Partially preserved'):
        command.selected_como_mode(config, sorted(keys - {'como-applicants'}), selected, historic_intent)
    with pytest.raises(ValueError, match='Current Como release intent'):
        command.selected_como_mode(config, sorted(keys), selected,
                                   {'baseline_manifest_sha256': _digest(selected),
                                    'changes': {'como-applicants': {}}})
    with pytest.raises(ValueError, match='Duplicate'):
        command.selected_como_mode(config, sorted(keys) + ['como-listed'], selected, historic_intent)
    with pytest.raises(ValueError, match='unknown'):
        command.selected_como_mode(config, sorted(keys) + ['unreviewed'], selected, historic_intent)


def test_main_only_como_selected_pair_does_not_contact_mutable_originals(monkeypatch, tmp_path, capsys):
    command = _load_qualifier_command()
    config = configs()
    keys = sorted(s['source_key'] for s in config['sources'])
    root = tmp_path/'data'/'publication'
    root.mkdir(parents=True)
    (root/'multi_prefecture_pilot.json').write_text(json.dumps(config))
    (root/'preserved_public_sources.json').write_text(json.dumps(keys))
    (root/'public_snapshot.json').write_text(json.dumps({'release_tag': 'reviewed-release'}))
    (root/'incremental_release_intent.json').write_text(
        json.dumps({'baseline_manifest_sha256': 'prior-release', 'changes': {'como-listed': {}}}))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(review, 'main', lambda **kwargs:
                        (_ for _ in ()).throw(AssertionError('No live source request in selected-only mode')))
    assert command.main(['--reviewed-config', '--respect-selected-preservation']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['state'] == 'selected_immutable_pair_reused'
    assert result['publications'] == 0 and not result['approval_granted']


def _load_qualifier_command():
    # The GitHub Actions entry point is a standalone script, not an installed
    # package. Load it by its exact repository path for regression testing.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "white_list_como_qualification_entrypoint",
        ROOT/'scripts/qualify_como_candidate.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
