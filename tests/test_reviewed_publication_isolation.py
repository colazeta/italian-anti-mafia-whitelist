import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bad_request_does_not_suppress_completed_or_later_bundles(tmp_path, monkeypatch):
    producer = script('stage_reviewed_national_candidate')
    out = tmp_path/'bundles'
    out.mkdir()
    for name in ['first', 'invalid', 'last']:
        (tmp_path/f'{name}.json').write_text(json.dumps({'publication': {}}))
    def stage(path, destination):
        if path.stem == 'invalid':
            raise ValueError('private validation error')
        (destination/path.stem).mkdir()
    monkeypatch.setattr(producer, 'stage', stage)
    assert producer.stage_requests(tmp_path.glob('*.json'), out) == ['invalid.json']
    assert {p.name for p in out.iterdir()} == {'first', 'last'}


def test_legacy_lookup_reaches_later_pages(monkeypatch):
    consumer = script('restore_protected_candidate')
    monkeypatch.setattr(consumer, 'api', lambda url: {'workflow_runs': list(range(100)) if url.endswith('page=1') else [101]})
    assert list(consumer.pages('runs?per_page=100', 'workflow_runs'))[-1] == 101


def test_review_bundle_is_exposed_only_after_exact_readback(tmp_path, monkeypatch):
    module = script('reviewed_bundle_release')
    bundle = tmp_path/('a'*64)
    bundle.mkdir()
    for name in module.ASSETS:
        (bundle/name).write_bytes(name.encode())
    state = {'info': None, 'bad': True, 'published': 0}
    monkeypatch.setattr(module, 'release', lambda tag: state['info'])
    def run(args, check):
        action = args[2]
        if action == 'create':
            state['info'] = dict(isDraft=True, isPrerelease=True, assets=[])
        elif action == 'upload':
            state['info']['assets'] = [{'name': n} for n in module.ASSETS]
        elif action == 'download':
            for name in module.ASSETS:
                (Path(args[-1])/name).write_bytes(b'corrupt' if state['bad'] else name.encode())
        elif action == 'edit':
            state['published'] += 1
            state['info']['isDraft'] = False
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(module.subprocess, 'run', run)
    with pytest.raises(ValueError, match='readback'):
        module.retain(bundle, 'b'*40)
    assert state['info']['isDraft']
    state['bad'] = False
    module.retain(bundle, 'b'*40)
    module.retain(bundle, 'b'*40)
    assert state['published'] == 1


def test_reviewable_build_requires_all_previous_checks_to_pass():
    workflow = (ROOT/'.github/workflows/public-registry-review.yml').read_text()
    step = workflow.split('- name: Save reviewable public build', 1)[1].split('with:', 1)[0]
    assert 'if: success()' in step


def test_published_bundle_corruption_is_rejected(tmp_path, monkeypatch):
    module = script('reviewed_bundle_release')
    bundle = tmp_path/('a'*64)
    bundle.mkdir()
    for name in module.ASSETS:
        (bundle/name).write_bytes(b'{}')
    monkeypatch.setattr(module, 'release', lambda tag: dict(
        isDraft=False, isPrerelease=True, assets=[{'name': n} for n in module.ASSETS]))
    def download(args, check):
        for n in module.ASSETS:
            (Path(args[-1])/n).write_bytes(b'{}' if n != 'registry.csv.gz' else b'corrupt')
    monkeypatch.setattr(module.subprocess, 'run', download)
    with pytest.raises(ValueError):
        module.retain(bundle, 'b'*40)


@pytest.mark.parametrize('selected_value,expected', [('new', 'complete'), ('old', 'rebase'), ('other', 'conflict')])
def test_reconcile_advanced_baseline(monkeypatch, selected_value, expected):
    module = script('stage_reviewed_national_candidate')
    config = {'sources': [{'source_key': 'one'}]}
    original, selected = {'v': 1}, {'v': 2}
    def rows(value):
        return [{'record_locator': '1', 'source_key': 'one', 'source_status': 'listed', 'value': value}]
    provenance = dict(parser='p', sha256='a'*64, reference_date='2026-11-01')
    request = {'publication': {'baseline_manifest_sha256': module.configuration_sha256(original),
                               'source_config_sha256': module.configuration_sha256(config)},
               'changes': {'one': {**provenance, 'count': 1, 'statuses': {'listed': 1},
                                   'records_sha256': module.publication_handoff.records_digest(rows('new'))}}}
    def restore(manifest, dest):
        dest.mkdir()
        registry = {'records': rows(selected_value if manifest == selected else 'old'),
                    'meta': {'sources': [dict(source_key='one', **provenance)]}}
        (dest/'registry.json').write_text(json.dumps(registry))
    monkeypatch.setattr(module.public_snapshot, 'restore', restore)
    monkeypatch.setattr(module, 'baseline_revision', lambda _: ('rev', original))
    monkeypatch.setattr(module, 'tracked_json', lambda *_: config.copy())
    args = request, selected, config, {'one': config['sources'][0]}
    if expected == 'conflict':
        with pytest.raises(ValueError, match='Concurrent'):
            module.reconcile(*args)
    elif expected == 'complete':
        assert module.reconcile(*args) is None
    else:
        assert module.reconcile(*args)['baseline_manifest_sha256'] == module.configuration_sha256(selected)
