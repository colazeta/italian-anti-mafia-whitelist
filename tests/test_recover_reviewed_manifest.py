from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from white_list_archive.acquisition import recover_reviewed_manifest as recovery


def test_recovers_only_exact_reviewed_captures(monkeypatch):
    request = json.loads(Path('data/publication/archive_replay_requests/taranto-2026-11-06.json').read_text())
    conn = Mock()
    conn.execute.return_value.fetchall.return_value = [('capture-id',)]
    by_key = {row['source_key']: row for row in request['config']['sources']}
    def load(catalogue, *, source_key, capture_id):
        return dict(by_key[source_key]), {}
    monkeypatch.setattr(recovery, 'load_catalogued_capture', load)
    bindings = recovery.selection(request, conn, object())
    assert [b['source_key'] for b in bindings] == list(by_key)
    altered = deepcopy(request)
    altered['changes']['taranto-listed']['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='inconsistent'):
        recovery.selection(altered, conn, object())
    conn.execute.return_value.fetchall.return_value = []
    with pytest.raises(ValueError, match='no capture'):
        recovery.selection(request, conn, object())


def test_private_handoff_requires_exact_readback():
    store = Mock()
    store.client.get_object.return_value = {'Body': BytesIO(b'{}')}
    assert len(recovery.retain_manifest(store, {})) == 64
    assert store.client.put_object.call_args.kwargs['IfNoneMatch'] == '*'
    store.client.get_object.return_value = {'Body': BytesIO(b'incomplete')}
    with pytest.raises(ValueError, match='exact readback'):
        recovery.retain_manifest(store, {})
