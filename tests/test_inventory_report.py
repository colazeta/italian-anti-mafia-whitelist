from copy import deepcopy
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
    assert digest == hashlib.sha256(body).hexdigest()
    document = json.loads(body)
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
    assert 'report_sha256 = persist_inventory_report(' in workflow
    assert workflow.index('report_sha256 = persist_inventory_report(') > workflow.index('if version_key in known_keys:')
