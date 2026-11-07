from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from white_list_archive.persistence.legacy_cosenza import (
    SPECS, classification_for, retain_classification,
)


def legacy_example():
    name, cid, _ = SPECS[0]
    root = Path(__file__).resolve().parents[1]
    historical = json.loads((root / 'data/captures/cosenza' / name).read_text())
    manifest = {k: historical[k] for k in (
        'sha256', 'byte_size', 'captured_at', 'reference_date', 'resource_url',
        'content_type', 'http_status', 'etag', 'last_modified', 'origin_type',
    )}
    manifest.update(capture_id=cid, source_key='cosenza-combined', resolved_url=historical['final_url'])
    return name, manifest, historical


def test_later_classification_does_not_rewrite_legacy_capture():
    name, manifest, historical = legacy_example()
    original = deepcopy(manifest)
    result = classification_for(manifest, historical, filename=name)
    assert manifest == original
    assert 'authority_rank_code' not in manifest
    assert result['assessment'] == {'authority_rank_code': 'primary_official', 'resource_type_code': 'pdf'}
    assert result['capture_id'] == manifest['capture_id']
    assert result['sha256'] == manifest['sha256']


@pytest.mark.parametrize('field,value', [
    ('sha256', '0' * 64), ('captured_at', '2026-11-07T00:00:00Z'),
    ('capture_id', '00000000-0000-4000-8000-000000000001'),
    ('source_key', 'another-authority'), ('authority_rank_code', 'secondary'),
])
def test_conflicting_identity_or_provenance_fails_closed(field, value):
    name, manifest, historical = legacy_example()
    manifest[field] = value
    with pytest.raises(ValueError):
        classification_for(manifest, historical, filename=name)


def test_classification_is_idempotent_and_never_overwrites_conflict():
    class Existing(Exception):
        response = {'Error': {'Code': 'PreconditionFailed'}}
    class Client:
        body = None
        def put_object(self, **kw):
            assert kw['IfNoneMatch'] == '*'
            if self.body is not None:
                raise Existing()
            self.body = kw['Body']
        def get_object(self, **kw):
            return {'Body': BytesIO(self.body)}
    name, manifest, historical = legacy_example()
    decision = classification_for(manifest, historical, filename=name)
    client = Client()
    store = SimpleNamespace(client=client, config=SimpleNamespace(bucket='private'))
    retain_classification(store, decision)
    original = client.body
    retain_classification(store, decision)
    changed = deepcopy(decision)
    changed['assessment']['resource_type_code'] = 'html'
    with pytest.raises(ValueError, match='readback'):
        retain_classification(store, changed)
    assert client.body == original


def test_reconciliation_never_uses_live_source_or_public_artifacts():
    root = Path(__file__).resolve().parents[1]
    module = (root / 'src/white_list_archive/persistence/legacy_cosenza.py').read_text()
    workflow = (root / '.github/workflows/reconcile-frozen-cosenza.yml').read_text()
    assert 'urlopen' not in module
    assert 'requests.get' not in module
    assert 'actions/upload-artifact' not in workflow
    assert workflow.count('python -m white_list_archive.persistence.legacy_cosenza') == 2
    assert 'environment: evidence-archive' in workflow
