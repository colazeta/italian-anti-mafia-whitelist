from copy import deepcopy
from pathlib import Path

import pytest

from test_auto_transform import _scalar, _history, H1, H2, H3
from white_list_archive.acquisition.historical_transform import (
    digest, execute_batch, select_batch, select_historical_jobs, selection_manifest,
)


def test_scalar_history_includes_approved_old_and_changed_versions_without_duplicate_checks():
    state, config = _scalar()
    repeated = deepcopy(state)
    url = config['sources'][0]['resource_url']
    repeated['robots']['sample']['resources'][url]['capture_history'].append(
        _history('sample-listed', H2, 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'))
    jobs, issues = select_historical_jobs([('a'*40, state), ('b'*40, repeated)], config, shards=1)
    assert len(jobs) == 2
    assert {job['captures']['primary']['state']['sha256'] for job in jobs} == {H1, H2}
    assert not issues
    assert config['sources'][0]['sha256'] == H1
    assert config['sources'][0]['reference_date'] == '2026-10-01'
    assert all(job['first_history_revision'] == 'a'*40 for job in jobs)
    assert digest(selection_manifest(jobs)) == digest(selection_manifest(jobs))
    assert all(job['config']['reference_date'] == '2026-10-01' for job in jobs)
    # Common transformer explicitly clears dates instead of assigning this old date
    # to historical bytes that have not passed edition review.
    from white_list_archive.acquisition.auto_transform import _parse_config
    assert all(_parse_config(job)['reference_date'] == '' for job in jobs)


def test_bundle_selection_uses_only_labelled_inputs_that_coexisted_in_a_real_state():
    state, config = _scalar()
    cfg = config['sources'][0]
    cfg.pop('resource_url')
    cfg['resources'] = {'listed': {'resource_url': 'https://official/listed', 'sha256': H1},
                        'applicants': {'resource_url': 'https://official/applicants', 'sha256': H3}}
    def bundle(left, right):
        result = deepcopy(state)
        result['robots']['sample']['resources'] = {
            url: {'capture_ids': [cid], 'capture_history': [_history('sample-listed', sha, cid)]}
            for url, sha, cid in [
                ('https://official/listed', left, '11111111-1111-4111-8111-111111111111'),
                ('https://official/applicants', right, '22222222-2222-4222-8222-222222222222')]
        }
        return result
    first = bundle(H1, H3)
    second = bundle(H2, H3)
    second['robots']['sample']['resources']['https://official/listed']['capture_ids'] = ['33333333-3333-4333-8333-333333333333']
    second['robots']['sample']['resources']['https://official/listed']['capture_history'][0]['capture_id'] = '33333333-3333-4333-8333-333333333333'
    jobs, issues = select_historical_jobs([('a'*40, first), ('b'*40, second)], config, shards=1)
    assert not issues
    assert len(jobs) == 2
    assert {(j['captures']['listed']['state']['sha256'], j['captures']['applicants']['state']['sha256'])
            for j in jobs} == {(H1, H3), (H2, H3)}
    second['robots']['sample']['resources']['https://official/applicants'].pop('capture_ids')
    jobs, issues = select_historical_jobs([('a'*40, first), ('b'*40, second)], config, shards=1)
    assert len(jobs) == 1
    assert issues[0]['reason'] == 'bundle_active_capture_identity_unresolved'


def test_partial_metadata_unreviewed_states_and_conflicting_capture_ids_remain_visible():
    state, config = _scalar()
    url = config['sources'][0]['resource_url']
    state['robots']['sample']['resources'][url]['capture_history'].append(
        {'source_key': 'sample-listed', 'capture_id': 'unknown-digest'})
    jobs, issues = select_historical_jobs([('a'*40, state)], config, shards=1)
    assert len(jobs) == 2
    assert issues[0]['reason'] == 'retained_capture_metadata_unresolved'
    changed = deepcopy(state)
    changed['robots']['sample']['resources'][url]['capture_history'][0]['sha256'] = H3
    with pytest.raises(ValueError, match='conflicting provenance'):
        select_historical_jobs([('a'*40, state), ('b'*40, changed)], config, shards=1)
    state['robots']['sample']['population_mapping_reviewed'] = False
    jobs, issues = select_historical_jobs([('a'*40, state)], config, shards=1)
    assert not jobs and issues[0]['reason'] == 'unreviewed_authority_at_retained_state'


def test_bounded_cursor_accounts_for_every_pending_interpretation_and_rejects_invalid_bounds():
    state, config = _scalar()
    jobs, _ = select_historical_jobs([('a'*40, state)], config, shards=1)
    batch, coverage = select_batch(jobs, cursor=0, max_jobs=1)
    assert batch == jobs[:1]
    assert coverage['denominator_interpretations'] == 2
    assert coverage['next_cursor'] == 1 and coverage['pending_interpretations'] == 1
    batch, coverage = select_batch(jobs, cursor=1, max_jobs=1)
    assert batch == jobs[1:]
    assert coverage['pending_interpretations'] == 0
    with pytest.raises(ValueError):
        select_batch(jobs, cursor=3, max_jobs=1)
    with pytest.raises(ValueError):
        select_batch(jobs, cursor=0, max_jobs=11)


def test_execution_uses_common_transformer_retry_and_explicit_edition_quarantine(monkeypatch):
    import white_list_archive.acquisition.historical_transform as module
    from white_list_archive.acquisition.auto_transform import EditionReviewRequired
    state, config = _scalar()
    jobs, _ = select_historical_jobs([('a'*40, state)], config, shards=1)
    seen = []
    monkeypatch.setattr(module, 'hydrate_selected_job', lambda job, store: job)
    def transform(job, **kwargs):
        seen.append(job['interpretation_key'])
        kwargs['progress']['stage'] = 'parser_compatibility'
        if len(seen) == 1:
            raise EditionReviewRequired('private content must not be copied into a report')
        return {'source_key': job['source_key'], 'status': 'parsed_private_review_required',
                'database_readback': 'verified', 'database_tls_verified': True}
    monkeypatch.setattr(module, 'transform_one', transform)
    monkeypatch.setattr(module, 'quarantine_age', lambda *a: {'verified': True, 'age_seconds': 0})
    outcomes = execute_batch(jobs, store=object(), dsn='private', code_revision='c'*40,
        authority_registry=Path('authority.csv'), series_registry=Path('series.csv'))
    assert seen == [job['interpretation_key'] for job in jobs]
    assert outcomes[0]['reason'] == 'edition_bound_parser_requires_review'
    assert outcomes[0]['stage'] == 'parser_compatibility'
    assert outcomes[0]['attempts'] == 1
    assert 'private content' not in str(outcomes)
    assert outcomes[1]['database_readback'] == 'verified'
    assert all(row['capture_inputs'] for row in outcomes)


def test_historical_workflow_is_bounded_main_only_unscheduled_and_uses_shared_serialisation():
    text = Path('.github/workflows/transform-historical-captures.yml').read_text()
    assert "if: github.ref == 'refs/heads/main'" in text
    assert "'transform-reviewed-captures'" in text
    assert 'environment: evidence-archive' in text
    assert 'schedule:' not in text
    assert 'upload-artifact@' not in text
    assert 'selection_sha256:' in text and 'cursor:' in text and 'max_jobs:' in text


def test_missing_legacy_metadata_is_filled_only_by_exact_immutable_catalogue(tmp_path):
    from datetime import datetime, timezone
    from test_archive_inventory import store
    from white_list_archive.acquisition.archive_first import archive_payload
    from white_list_archive.acquisition.historical_transform import hydrate_selected_job
    evidence = store()
    result = archive_payload(data=b'original historical bytes', source_key='sample-listed',
        resource_url='https://official.example/white-list.pdf', reference_date=None,
        content_type='application/pdf', store=evidence, work_dir=tmp_path,
        capture_id='aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa',
        captured_at=datetime(2026, 11, 7, tzinfo=timezone.utc), http_status=200)
    state, config = _scalar()
    row = {'source_key': 'sample-listed', 'capture_id': result.manifest['capture_id'],
           'sha256': result.manifest['sha256'], 'byte_size': None, 'captured_at': None}
    state['robots']['sample']['resources'][config['sources'][0]['resource_url']]['capture_history'] = [row]
    jobs, _ = select_historical_jobs([('a'*40, state)], config, shards=1)
    before = deepcopy(evidence.client.objects)
    hydrated = hydrate_selected_job(jobs[0], evidence)
    assert evidence.client.objects == before  # Read-only hydration, no migration.
    actual = hydrated['captures']['primary']['state']
    assert actual['byte_size'] == len(b'original historical bytes')
    assert actual['captured_at'] == result.manifest['captured_at']
    assert jobs[0]['captures']['primary']['state']['captured_at'] is None
    jobs[0]['captures']['primary']['state']['sha256'] = 'f'*64
    with pytest.raises(ValueError, match='conflicts with immutable provenance'):
        hydrate_selected_job(jobs[0], evidence)


def test_transient_historical_io_retries_through_the_common_bounded_operation(monkeypatch):
    from botocore.exceptions import ReadTimeoutError
    import white_list_archive.acquisition.historical_transform as module
    from white_list_archive.acquisition.transform_resilience import with_bounded_retry
    state, config = _scalar()
    jobs, _ = select_historical_jobs([('a'*40, state)], config, shards=1)
    calls = []
    monkeypatch.setattr(module, 'hydrate_selected_job', lambda job, store: job)
    def transform(job, **kwargs):
        calls.append(job['interpretation_key'])
        kwargs['progress']['stage'] = 'snapshot_readback'
        if len(calls) == 1:
            raise ReadTimeoutError(endpoint_url='https://private-coordinate.example')
        return {'source_key': job['source_key'], 'status': 'reused_private_interpretation',
                'database_readback': 'verified'}
    monkeypatch.setattr(module, 'transform_one', transform)
    monkeypatch.setattr(module, 'with_bounded_retry', lambda operation, progress:
        with_bounded_retry(operation, progress, sleep=lambda delay: None))
    outcomes = execute_batch(jobs[:1], store=object(), dsn='private', code_revision='c'*40,
        authority_registry=Path('authority.csv'), series_registry=Path('series.csv'))
    assert calls == [jobs[0]['interpretation_key']] * 2
    assert outcomes[0]['attempts'] == 2
    assert outcomes[0]['status'] == 'reused_private_interpretation'
    assert 'private-coordinate' not in str(outcomes)


def test_continuation_refuses_unpinned_history_before_reading_or_writing():
    from white_list_archive.acquisition.historical_transform import main
    with pytest.raises(ValueError, match='exact frozen robot revision'):
        main(['--robot-head', 'refs/remotes/origin/robot-state', '--cursor', '1'])
