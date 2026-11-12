from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from white_list_archive.normalisation.source_command import PAIRS, REPOSITORY, authorise
from white_list_archive.normalisation.source_queue import ledger_requests, drain_requests, PREFIX


def comment(identifier=1, command=next(iter(PAIRS))):
    return {'id': identifier, 'body': command, 'created_at': '2026-11-08T01:00:00Z',
            'updated_at': '2026-11-08T01:00:00Z', 'user': {'login': 'colazeta', 'type': 'User'}}


def ledger(pages, issue=None):
    def fetch(path):
        if path.endswith('/225'):
            return issue or {'number': 225}
        return pages[int(path.split('page=')[-1]) - 1]
    return ledger_requests(fetch)


def test_paginate_past_irrelevant_comments_and_keep_every_authored_request():
    irrelevant = [dict(comment(i + 100), body='irrelevant') for i in range(100)]
    requests = ledger([irrelevant, [comment(1), comment(2), comment(3, list(PAIRS)[1])]])
    assert [r['comment_id'] for r in requests] == [1, 2, 3]
    assert requests[0]['capture_id'] == requests[1]['capture_id']
    assert ledger([[dict(comment(), user={'login': 'outsider', 'type': 'User'})]]) == []


def test_edited_commands_and_pull_request_ledgers_fail_closed():
    with pytest.raises(ValueError, match='unedited'):
        ledger([[dict(comment(), updated_at='2026-11-08T02:00:00Z')]])
    with pytest.raises(ValueError, match='designated issue'):
        ledger([[]], {'number':225,'pull_request':{}})


def test_incomplete_pagination_never_becomes_empty_success(monkeypatch):
    import white_list_archive.normalisation.source_queue as module
    monkeypatch.setattr(module, 'MAX_PAGES', 1)
    with pytest.raises(ValueError, match='incomplete'):
        ledger([[dict(comment(i + 100), body='irrelevant') for i in range(100)]])


class Client:
    def __init__(self): self.objects = {}
    def get_object(self, **kw):
        if kw['Key'] not in self.objects:
            raise ClientError({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
        return {'Body':BytesIO(self.objects[kw['Key']])}
    def put_object(self, **kw):
        assert kw['IfNoneMatch'] == '*'
        if kw['Key'] in self.objects:
            raise ClientError({'Error': {'Code': 'PreconditionFailed'}}, 'PutObject')
        self.objects[kw['Key']] = kw['Body']


def store(): return SimpleNamespace(client=Client(),config=SimpleNamespace(bucket='private'))


def test_replacement_worker_drains_all_requests_and_repeated_pair_has_own_receipt():
    requests = ledger([[comment(1), comment(2), comment(3,list(PAIRS)[1])]])
    archive, calls = store(), []
    def execute(revision, request, saved=None):
        calls.append((revision,request['capture_id'],saved is not None))
        return saved or {'synthetic_result':request['capture_id']}
    result = drain_requests(archive, requests, 'a'*40, execute=execute, qa=lambda *args: None)
    assert result['requests_verified'] == 3 and result['requests_pending'] == 0
    assert len(calls) == 2
    assert len(archive.client.objects) == 6  # accepted+completed for EACH request
    result = drain_requests(archive, requests, 'b'*40, execute=execute, qa=lambda *args: None)
    assert result['requests_verified'] == 3
    assert all(revision == 'a'*40 for revision,_,_ in calls)
    assert len(calls) == 4  # old frozen completions independently reverified per pair


def test_interrupted_commit_replays_original_revision_before_marking_completion():
    requests = ledger([[comment()]])
    archive = store()
    calls = []
    def interrupted(revision, request, saved=None):
        raise RuntimeError('private driver details')
    first = drain_requests(archive, requests, 'a'*40, execute=interrupted, qa=lambda *args: None)
    assert first['diagnostic_failures'] == 1 and first['requests_verified'] == 0
    assert len(archive.client.objects) == 1  # no false completion
    def resume(revision,request,saved=None):
        calls.append(revision)
        return {'synthetic_result':1}
    second = drain_requests(archive,requests,'b'*40,execute=resume, qa=lambda *args: None)
    assert calls == ['a'*40] and second['requests_pending'] == 0


def test_bounded_drain_does_not_starve_later_requests_on_next_wakeup():
    requests = ledger([[comment(i) for i in range(1,5)]])
    archive = store()
    execute = lambda *args: {'synthetic_result':1}
    first = drain_requests(archive,requests,'a'*40,execute=execute,qa=lambda *args: None,limit=2)
    assert first['requests_verified'] == 2 and first['requests_pending'] == 2
    second = drain_requests(archive,requests,'b'*40,execute=execute,qa=lambda *args: None,limit=3)
    assert second['requests_verified'] == 4 and second['requests_pending'] == 0


def test_only_trusted_ordinary_robots_run_can_recover_queue():
    run = {'name':'Prefecture robots','conclusion':'success','head_branch':'main',
           'head_repository':{'full_name':REPOSITORY},'event':'schedule'}
    kwargs = dict(repository=REPOSITORY,actor='colazeta',ref='refs/heads/main')
    assert authorise('workflow_run',{'workflow_run':run},**kwargs)['mode']=='drain-owner-queue'
    for key,value in [('name','Untrusted'),('conclusion','failure'),('head_branch','fork'),('event','pull_request')]:
        invalid=deepcopy(run);invalid[key]=value
        with pytest.raises(ValueError):authorise('workflow_run',{'workflow_run':invalid},**kwargs)


def test_irrelevant_comments_never_occupy_protected_concurrency():
    from pathlib import Path
    text=(Path(__file__).resolve().parents[1]/'.github/workflows/cosenza-rich-preflight.yml').read_text()
    before,jobs=text.split('jobs:',1)
    authorisation,protected=jobs.split('  preflight:',1)
    assert 'concurrency:' not in before and 'concurrency:' not in authorisation
    assert 'concurrency:' in protected and 'needs: authorise' in protected
    assert "github.event.comment.body == '/cosenza-source-only 2026-06-28'" in authorisation
    assert "workflows: ['Prefecture robots']" in before
    assert 'fetch-depth: 0' in protected


def test_qa_failure_cannot_be_recorded_as_completed_request():
    requests = ledger([[comment()]])
    archive = store()
    def failed_qa(*args): raise RuntimeError('private QA facts')
    result = drain_requests(archive,requests,'a'*40,
        execute=lambda *args: {'synthetic_result':1},qa=failed_qa)
    assert result['requests_verified'] == 0 and result['requests_pending'] == 1
    assert result['qa_reports_verified'] == 0
    assert not any(key.endswith('/completed.json') for key in archive.client.objects)


def test_frozen_operation_executes_actual_ancestor_checkout_and_suppresses_failures(tmp_path,monkeypatch):
    import subprocess
    import white_list_archive.normalisation.source_queue as module
    root = tmp_path/'repository'
    package = root/'src/white_list_archive/normalisation'
    package.mkdir(parents=True)
    (package/'__init__.py').write_text('')
    (package.parent/'__init__.py').write_text('')
    path=package/'cosenza_capture_rich.py'
    path.write_text('''import subprocess

def materialise(*,capture_id,parse_run_id,code_revision):
    actual=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    assert actual==code_revision
    return dict(parse_run_id='synthetic-run',record_count=1,field_value_count=7,
        entity_mention_count=1,snapshot_sha256='a'*64,rich_readback_verified=True,
        committed_readback_verified=True,capture_id=capture_id,
        prerequisite_parse_run_id=parse_run_id,code_revision=actual,
        editions_created=0,publications=0,semantic_writes=0,canonical_writes=0,edition_approvals=0)
''')
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=root,text=True,stderr=subprocess.DEVNULL).strip()
    git('init');git('config','user.name','Synthetic CI');git('config','user.email','ci@example.invalid')
    git('add','.');git('commit','-m','synthetic source implementation')
    old=git('rev-parse','HEAD')
    path.write_text("def materialise(**kwargs):\n    print('PRIVATE-ROW')\n    raise ValueError('PRIVATE-TOKEN')\n")
    git('add','.');git('commit','-m','synthetic failing later implementation')
    current=git('rev-parse','HEAD')
    monkeypatch.setattr(module,'__file__',str(package/'source_queue.py'))
    request=ledger([[comment()]])[0]
    result=module.frozen_operation(old,request)
    assert result['code_revision']==old
    with pytest.raises(RuntimeError,match='private output suppressed') as failure:
        module.frozen_operation(current,request)
    assert 'PRIVATE-TOKEN' not in str(failure.value) and 'PRIVATE-ROW' not in str(failure.value)
    with pytest.raises(ValueError,match='Invalid frozen'):
        module.frozen_operation(old+';echo injected',request)
    assert git('worktree','list','--porcelain').count('worktree ')==1


def test_repeated_failed_pair_is_not_retried_per_comment_and_no_success_receipts():
    requests=ledger([[comment(i) for i in range(1,10)]])
    archive=store(); calls=[]
    def failing(*args):
        calls.append(1)
        raise RuntimeError('private failure')
    report=drain_requests(archive,requests,'a'*40,execute=failing,qa=lambda *args:None)
    assert len(calls)==1
    assert report['requests_verified']==0 and report['requests_pending']==9
    assert report['diagnostic_failures']==9
    assert not any(key.endswith('/completed.json') for key in archive.client.objects)


def test_review_uses_exact_verified_pairs_in_explicit_order_and_actual_source_revision():
    requests=ledger([[comment(1,list(PAIRS)[1]),comment(2)]])
    archive=store(); retained=[]
    def execute(revision,request,saved=None):
        return saved or {'parse_run_id':request['capture_id'],'record_count':3}
    def retain(store,inputs,revision):
        retained.append((inputs,revision))
        return {'private_readback_verified':True,'candidate_rows':6}
    result=drain_requests(archive,requests,'a'*40,execute=execute,qa=lambda *args:None,retain=retain)
    assert result['review_dossiers_verified']==1
    assert [r['capture_id'] for r in retained[0][0]]==[pair[0] for pair in PAIRS.values()]
    assert all(r['source_revision']=='a'*40 for r in retained[0][0])
    result=drain_requests(archive,requests,'b'*40,execute=execute,qa=lambda *args:None,retain=retain)
    assert retained[-1][1]=='b'*40
    assert all(r['source_revision']=='a'*40 for r in retained[-1][0])
    assert result['requests_pending']==0


def test_failed_review_remains_visible_and_retries_without_rewriting_completed_requests():
    requests=ledger([[comment()]])
    archive=store()
    def execute(revision,request,saved=None):
        return saved or {'parse_run_id':request['capture_id'],'record_count':1}
    def failed(*args):raise RuntimeError('PRIVATE-ROW-DETAILS')
    first=drain_requests(archive,requests,'a'*40,execute=execute,qa=lambda *args:None,retain=failed)
    assert first['diagnostic_failures']==1 and first['review_dossiers_verified']==0
    assert first['requests_verified']==1 and first['bounded_remaining']==0
    assert 'PRIVATE-ROW-DETAILS' not in str(first)
    before=dict(archive.client.objects)
    resumed=drain_requests(archive,requests,'b'*40,execute=execute,qa=lambda *args:None,
        retain=lambda *args:{'private_readback_verified':True})
    assert resumed['diagnostic_failures']==0 and resumed['review_dossiers_verified']==1
    assert archive.client.objects==before


def test_queue_review_accepts_bounded_field_aggregates_and_rejects_private_keys(monkeypatch):
    import os
    from contextlib import nullcontext
    from white_list_archive.acquisition import auto_transform
    from white_list_archive.normalisation import cosenza_review, source_queue

    class SyntheticConn:
        def rollback(self): pass

    monkeypatch.setenv('EVIDENCE_DATABASE_URL', 'synthetic-test-only')
    monkeypatch.setattr(auto_transform, 'private_connection',
                        lambda dsn: nullcontext(SyntheticConn()))
    summary = dict(
        contract='cosenza-private-review-v1', dossier_sha256='a'*64,
        receipt_sha256='b'*64, immutable=True, versions_expected=2,
        versions_verified=2, records_verified=2, comparison_verified=True,
        identical_occurrences=1, before_only_occurrences=1,
        after_only_occurrences=1, changed_document_mentions=1,
        changed_field_counts={'outcome_raw': 1, 'observed_listing_date': 1},
        administrative_reference_dates_unknown=2, database_writes=0,
        edition_approvals=0, semantic_ready=False, publication_ready=False)
    monkeypatch.setattr(cosenza_review, 'retain_review',
                        lambda *args, **kwargs: {'safe_summary':summary})
    output = source_queue.retain_queue_review(store(), [], 'a'*40)
    assert output['changed_field_counts'] == summary['changed_field_counts']
    assert output['edition_approvals'] == 0

    for invalid in (
        {'private_name': 1},
        {'outcome_raw': 'PRIVATE-SOURCE-VALUE'},
        {'outcome_raw': 2},
        {'outcome_raw': True},
    ):
        summary['changed_field_counts'] = invalid
        with pytest.raises(ValueError, match='bounded aggregate'):
            source_queue.retain_queue_review(store(), [], 'a'*40)

    summary['comparison_verified'] = False
    summary['changed_field_counts'] = None
    summary['changed_document_mentions'] = None
    assert source_queue.retain_queue_review(store(), [], 'a'*40)['comparison_verified'] is False
    summary['changed_field_counts'] = {}
    with pytest.raises(ValueError, match='Missing comparison'):
        source_queue.retain_queue_review(store(), [], 'a'*40)
