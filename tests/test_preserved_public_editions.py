"""A failed live scope cannot silently become a fresh observation via reuse."""
import copy
import json

import pytest

from white_list_archive.publishing import public_national_build as build


def edition(key, status='listed'):
    cfg = dict(source_key=key, authority_key=key, register_key=key, parser='reviewed_parser',
               population_scope='listed_and_applicant', reference_date='2026-09-21',
               sha256='a' * 64, source_page_url='https://example.test/page',
               resource_url='https://example.test/source', expected_source_rows=1)
    report = {field: cfg[field] for field in ('source_key', 'authority_key', 'register_key', 'parser',
              'population_scope', 'reference_date', 'sha256')}
    report['document_checked_at'] = '2026-09-22T07:49:10+00:00'
    record = {field: cfg[field] for field in ('source_key', 'authority_key', 'register_key',
              'population_scope', 'reference_date', 'source_page_url', 'resource_url')}
    record.update(record_locator=key+':1', source_row_ordinal=1, source_status=status,
                  capture_sha256=cfg['sha256'], parser_name=cfg['parser'], parser_version='1')
    registry = dict(records=[record], meta=dict(record_count=1, authority_count=1, register_count=1,
        source_count=1, authority_counts={key:1}, register_counts={key:1}, status_counts={status:1}, sources=[report]))
    return cfg, registry


def setup(monkeypatch, tmp_path):
    cfg, approved = edition('preserved')
    fresh_cfg, fresh = edition('fresh', 'pending')
    def restore(manifest, destination):
        (destination/'registry.json').write_text(json.dumps(approved))
    monkeypatch.setattr(build, 'restore', restore)
    calls = []
    def acquire(config, work_dir):
        calls.append(config)
        (work_dir/'fresh.diagnostics.json').write_text(json.dumps({'parser':'reviewed_parser','parser_version':'7'}))
        return copy.deepcopy(fresh)
    monkeypatch.setattr(build, 'build_registry', acquire)
    manifest = tmp_path/'manifest.json'
    manifest.write_text('{}')
    return {'sources':[cfg, fresh_cfg]}, approved, calls, manifest


def test_preserves_records_and_verification_time_without_fetching_scope(monkeypatch, tmp_path):
    config, approved, calls, manifest = setup(monkeypatch, tmp_path)
    original = copy.deepcopy(approved)
    result = build._build_registry_from_selected_inputs(config, tmp_path, None,
        preserved_source_keys=('preserved',), public_snapshot_manifest=manifest)
    assert [s['source_key'] for s in calls[0]['sources']] == ['fresh']
    assert result['records'][1] == original['records'][0]
    assert result['meta']['sources'][1] == original['meta']['sources'][0]
    assert result['records'][0]['parser_version'] == '7'
    assert result['meta']['status_counts'] == {'pending':1,'listed':1}
    assert result['meta']['record_count'] == result['meta']['source_count'] == 2
    assert approved == original


@pytest.mark.parametrize('field,value', [('sha256','b'*64),('reference_date','2026-09-27'),
    ('parser','new_parser'),('resource_url','https://example.test/another'),('expected_source_rows',2),
    ('approval_mode','semantic_sha256')])
def test_configuration_change_requires_new_source_review(monkeypatch, tmp_path, field, value):
    config, _, calls, manifest = setup(monkeypatch, tmp_path)
    config['sources'][0][field] = value
    with pytest.raises(ValueError):
        build._build_registry_from_selected_inputs(config, tmp_path, None,
            preserved_source_keys=('preserved',), public_snapshot_manifest=manifest)
    assert calls == []


def test_no_automatic_fallback_or_mixing_with_original_replay(monkeypatch, tmp_path):
    config, _, calls, manifest = setup(monkeypatch, tmp_path)
    for keys, path, frozen in [(('preserved',),None,None),((),manifest,None),
                              (('preserved',),manifest,tmp_path/'frozen.json'),
                              (('absent',),manifest,None),(('preserved','preserved'),manifest,None)]:
        with pytest.raises(ValueError):
            build._build_registry_from_selected_inputs(config, tmp_path, frozen,
                preserved_source_keys=keys, public_snapshot_manifest=path)
    assert calls == []
