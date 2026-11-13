from copy import deepcopy

import pytest

from test_auto_transform import _scalar, H1, H2
from white_list_archive.acquisition.auto_transform import select_reviewed_jobs, _parse_config
from white_list_archive.acquisition.approved_snapshot_backfill import backfill, existing_snapshot


def approved_job():
    state, cfg = _scalar()
    jobs, _ = select_reviewed_jobs(state, cfg, approved_only=True)
    return jobs[0]


def test_approved_backfill_selects_exact_older_bytes_without_relabelling_discovery():
    state, cfg = _scalar()
    jobs, _ = select_reviewed_jobs(state, cfg, approved_only=True)
    assert jobs[0]['captures']['primary']['state']['sha256'] == H1
    assert _parse_config(jobs[0]) == cfg['sources'][0]
    normal, _ = select_reviewed_jobs(state, cfg)
    assert normal[0]['captures']['primary']['state']['sha256'] == H2
    assert _parse_config(normal[0])['reference_date'] == ''
    history = state['robots']['sample']['resources'][cfg['sources'][0]['resource_url']]['capture_history']
    history[0]['source_key'] = 'sample-robot-discovery'
    jobs, deferred = select_reviewed_jobs(state, cfg, approved_only=True)
    assert not jobs and deferred[0]['reason'] == 'missing_verified_capture'


def test_changed_bundle_member_cannot_inherit_approved_date():
    job = approved_job()
    cfg = job['config']
    cfg['resources'] = {'a': {'sha256': H1, 'resource_url': 'https://example.org/a'},
                        'b': {'sha256': H1, 'resource_url': 'https://example.org/b'}}
    member = job['captures']['primary']
    job['captures'] = {'a': deepcopy(member), 'b': deepcopy(member)}
    job['captures']['b']['state']['sha256'] = H2
    assert _parse_config(job)['reference_date'] == ''
    assert cfg['reference_date'] == '2026-10-01'


def test_missing_snapshot_work_is_bounded_and_newest_first_and_existing_is_not_reparsed():
    jobs = []
    for day in range(1, 7):
        job = deepcopy(approved_job())
        job['source_key'] = f'source-{day}'
        job['config']['reference_date'] = f'2026-11-0{day}'
        jobs.append(job)
    processed = []
    def materialise(job):
        processed.append(job['source_key'])
        return {'database_readback': 'verified', 'qa_flags': [], 'publication_approved': False}
    result = backfill(jobs, limit=2, lookup=lambda j: j['source_key'] == 'source-6', materialise=materialise)
    assert processed == ['source-5', 'source-4']
    assert result['existing_verified'] == 1
    assert result['deferred'] == 3
    assert result['materialised'] == 2
    assert result['publications'] == result['quarantined'] == 0


def test_changed_input_or_failed_readback_never_counts_as_materialised():
    job = approved_job()
    job['captures']['primary']['state']['sha256'] = H2
    def forbidden(_):
        pytest.fail('Changed bytes must not be processed by approved backfill')
    assert backfill([job], limit=1, lookup=forbidden, materialise=forbidden)['quarantined'] == 1
    result = backfill([approved_job()], limit=1, lookup=lambda _: False,
                      materialise=lambda _: {'database_readback': 'unverified'})
    assert result['materialised'] == 0 and result['quarantined'] == 1


def test_existing_lookup_compares_complete_labels_and_rehashes_matching_snapshot(monkeypatch):
    job = approved_job()
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def execute(self, sql, args):
            assert 'configuration_hash' in sql
            assert args[0] == job['config']['parser']
        def fetchall(self):
            return [('wrong-label', {'other': H1}), ('exact', {'primary': H1})]
    class Connection:
        def cursor(self): return Cursor()
    read = []
    def verify(conn, identity):
        read.append(identity)
        return [{'source_status': 'listed'}], {}
    monkeypatch.setattr('white_list_archive.acquisition.auto_transform.read_snapshot_verified', verify)
    assert existing_snapshot(Connection(), job)
    assert read == ['exact']
