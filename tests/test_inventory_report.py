from copy import deepcopy
import gzip
import hashlib
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from white_list_archive.storage.inventory_report import persist_inventory_report


class Client:
    def __init__(self):
        self.objects = {}
        self.corrupt = False
        self.fail = False
    def put_object(self, **kwargs):
        assert kwargs['IfNoneMatch'] == '*'
        assert kwargs['Key'] not in self.objects
        self.objects[kwargs['Key']] = kwargs['Body']
    def get_object(self, **kwargs):
        if self.fail:
            raise RuntimeError('https://private.example/credential-material')
        return {'Body': BytesIO(self.objects[kwargs['Key']] + (b'!' if self.corrupt else b''))}


def payload():
    return {
        'inventory': {'schema_version': 1, 'generated_at': '2026-11-07T20:00:00Z',
                      'recovery_search_complete': False,
                      'metrics': {'denominator_items': 2},
                      'items': [{'status': 'verified', 'capture_id': 'control'},
                                {'status': 'not_verified', 'evidence_version_key': 'legacy'}]},
        'robot_metrics': {'robot_state_sha': 'a' * 40,
                          'discovery_capture_references_excluded': 3},
        'code_revision': 'b' * 40,
    }


def test_retains_full_denominator_exclusions_and_revision_with_exact_readback():
    client = Client()
    store = SimpleNamespace(client=client, config=SimpleNamespace(bucket='private'))
    args = payload()
    digest = persist_inventory_report(store, **args)
    key, body = next(iter(client.objects.items()))
    assert key.startswith('operations/v1/recovery-inventory/')
    assert key.endswith(".json.gz")
    raw = gzip.decompress(body)
    assert digest == hashlib.sha256(raw).hexdigest()
    document = json.loads(raw)
    assert document['inventory'] == args['inventory']
    assert document['robot_selection'] == args['robot_metrics']
    assert document['code_revision'] == args['code_revision']
    persist_inventory_report(store, **args)
    assert len(client.objects) == 2  # Attempts remain independent, no overwrite.


@pytest.mark.parametrize('failure', ['corrupt', 'fail'])
def test_failed_readback_never_erases_prior_attempts_or_exposes_provider_error(failure):
    client = Client()
    store = SimpleNamespace(client=client, config=SimpleNamespace(bucket='private'))
    persist_inventory_report(store, **payload())
    old = deepcopy(client.objects)
    setattr(client, failure, True)
    with pytest.raises(RuntimeError) as exc:
        persist_inventory_report(store, **payload())
    assert 'private.example' not in str(exc.value)
    assert all(client.objects[k] == value for k, value in old.items())
    assert len(client.objects) == 2


@pytest.mark.parametrize('change', ['code', 'robot', 'count', 'nan'])
def test_invalid_report_fails_before_storage(change):
    client = Client()
    store = SimpleNamespace(client=client, config=SimpleNamespace(bucket='private'))
    args = payload()
    if change == 'code':
        args['code_revision'] = 'main'
    elif change == 'robot':
        args['robot_metrics']['robot_state_sha'] = 'robot-state'
    elif change == 'count':
        args['inventory']['metrics']['denominator_items'] = 1
    else:
        args['robot_metrics']['unsafe_number'] = float('nan')
    with pytest.raises(ValueError):
        persist_inventory_report(store, **args)
    assert client.objects == {}


def test_workflow_dispatch_stays_main_only_private_and_persists_after_validation():
    workflow = Path('.github/workflows/lane-a-recovery-inventory-proof.yml').read_text()
    assert 'workflow_dispatch:' in workflow
    assert "if: github.ref == 'refs/heads/main'" in workflow
    assert 'environment: evidence-archive' in workflow
    assert 'upload-artifact@' not in workflow
    assert 'inventory_cycle merge' in workflow
    runtime = Path('src/white_list_archive/storage/inventory_cycle.py').read_text()
    assert runtime.index('persist_private_inventory_document(store, report,') > runtime.index('if version_key in known_keys:')
    assert runtime.index('digest = persist_inventory_report(') > runtime.index('inventory = merge_inventory_shards(documents, context, expected)')


@pytest.mark.parametrize('limit', ['raw', 'compressed'])
def test_size_bounds_fail_before_provider_write(monkeypatch, limit):
    import white_list_archive.storage.inventory_report as module
    client = Client()
    store = SimpleNamespace(client=client, config=SimpleNamespace(bucket='private'))
    monkeypatch.setattr(module, '_MAX_RAW_BYTES' if limit == 'raw' else '_MAX_COMPRESSED_BYTES', 1)
    with pytest.raises(ValueError, match=limit + ' bound'):
        persist_inventory_report(store, **payload())
    assert client.objects == {}


def test_large_repetitive_inventory_compresses_and_round_trips():
    client = Client()
    store = SimpleNamespace(client=client, config=SimpleNamespace(bucket='private'))
    args = payload()
    args['inventory']['items'] = [args['inventory']['items'][0]] * 300000
    args['inventory']['metrics']['denominator_items'] = 300000
    digest = persist_inventory_report(store, **args)
    compressed = next(iter(client.objects.values()))
    raw = gzip.decompress(compressed)
    assert len(raw) > 10_000_000
    assert len(compressed) < 100_000
    assert hashlib.sha256(raw).hexdigest() == digest
    assert json.loads(raw)['inventory'] == args['inventory']


def test_decompressed_readback_must_equal_full_canonical_inventory(monkeypatch):
    import white_list_archive.storage.inventory_report as module
    client = Client()
    store = SimpleNamespace(client=client, config=SimpleNamespace(bucket='private'))
    compress = gzip.compress
    monkeypatch.setattr(module.gzip, 'compress', lambda body, **kw: compress(b'{}', **kw))
    with pytest.raises(RuntimeError, match='decompressed readback'):
        persist_inventory_report(store, **payload())
    assert len(client.objects) == 1  # Failed attempt remains retained, no cleanup.
