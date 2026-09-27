import json
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_archive_batch_preserves_independent_success_and_does_not_relabel_new_bytes(monkeypatch, tmp_path):
    archive = run_path(str(ROOT / 'scripts/audit_source_archive.py'))['archive_sources']
    namespace = archive.__globals__
    captures = []
    monkeypatch.setitem(namespace, 'reviewed_source_series_context', lambda *a, **kw: None)

    def capture(**kwargs):
        captures.append(kwargs)
        if kwargs['source_key'] == 'broken':
            raise RuntimeError('must not expose provider coordinates or credentials')
        return SimpleNamespace(sha256='new-hash')

    monkeypatch.setitem(namespace, 'acquire_and_archive', capture)
    monkeypatch.setitem(namespace, '_persist_if_configured', lambda *a: ('writer_unavailable', False))
    monkeypatch.setitem(namespace, 'public_capture_receipt', lambda *a, **kw: {'sha256': 'new-hash', 'database_capture_persistence_state': kw['database_persistence_state']})
    config = {'sources': [dict(source_key=key, resource_url='https://example.test/source', sha256='old-hash', reference_date='2020-01-01') for key in ('broken', 'good')]}
    output = tmp_path / 'public.json'
    result = archive(config, ['broken', 'good'], object(), tmp_path / 'private', output)
    assert result[0]['capture_failed'] is True
    assert result[1]['matches_reviewed_raw_bytes'] is False
    assert all(r['source_facts_promoted'] is False for r in result)
    assert all(c['reference_date'] is None for c in captures)
    assert 'provider coordinates' not in output.read_text()
    assert json.loads(output.read_text()) == result


def test_unknown_source_is_rejected_before_any_capture(tmp_path):
    archive = run_path(str(ROOT / 'scripts/audit_source_archive.py'))['archive_sources']
    with pytest.raises(ValueError, match='Unknown'):
        archive({'sources': []}, ['unreviewed'], object(), tmp_path, tmp_path / 'public.json')
    assert not list(tmp_path.iterdir())
