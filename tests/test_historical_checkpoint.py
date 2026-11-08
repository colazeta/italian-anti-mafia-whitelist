from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from white_list_archive.acquisition.historical_checkpoint import (
    ACTIVE_KEY, PREFIX, campaign_summary, choose_shard, commit_attempt,
    digest, initialise, load_active, validate_state,
)


class ConditionalError(Exception):
    def __init__(self, code):
        self.response = {'Error': {'Code': code}}


class Client:
    def __init__(self):
        self.objects = {}
        self.reject_cas = False
        self.corrupt_read = False
    def put_object(self, **kw):
        key = kw['Key']
        if 'IfNoneMatch' in kw:
            assert kw['IfNoneMatch'] == '*'
            if key in self.objects:
                raise ConditionalError('PreconditionFailed')
        else:
            assert 'IfMatch' in kw and key == ACTIVE_KEY
            if self.reject_cas or key not in self.objects or kw['IfMatch'] != self.etag(key):
                raise ConditionalError('PreconditionFailed')
        self.objects[key] = kw['Body']
    def etag(self, key):
        return '"' + hashlib.sha256(self.objects[key]).hexdigest() + '"'
    def get_object(self, **kw):
        if kw['Key'] not in self.objects:
            raise ConditionalError('NoSuchKey')
        raw = self.objects[kw['Key']]
        return {'Body': BytesIO(raw+b'!' if self.corrupt_read else raw), 'ETag': self.etag(kw['Key'])}


def fixture(counts=(2, 1, 1, 1), review=0):
    plans = []
    for shard, count in enumerate(counts):
        plans.append([{'interpretation_key': digest({'shard': shard, 'job': job}),
            'source_key': f'source-{shard}', 'configuration_sha256': 'c'*64,
            'first_history_revision': 'd'*40,
            'inputs': {'primary': {'capture_id': f'capture-{shard}-{job}', 'sha256': 'a'*64}}}
            for job in range(count)])
    context = {'schema_version': 1, 'cycle_id': '11111111-1111-4111-8111-111111111111',
        'code_revision': 'a'*40, 'robot_state_sha': 'b'*40, 'config_sha256': 'c'*64,
        'selection': [{'shard': i, 'selection_sha256': digest(plan),
                       'interpretations': len(plan), 'review_items': review if i == 0 else 0}
                      for i, plan in enumerate(plans)],
        'created_at': '2026-11-08T10:00:00Z', 'previous_cycle_id': None}
    store = SimpleNamespace(client=Client(), config=SimpleNamespace(bucket='private'))
    state, etag = initialise(store, context)
    return store, state, etag, plans


def report(state, plans, *, count=1, quarantined=False):
    shard = choose_shard(state)
    cursor = state['cursors'][shard]
    entries = plans[shard][cursor:cursor+count]
    return {'cycle_id': state['context']['cycle_id'], 'shard': shard, 'cursor': cursor,
        'code_revision': state['context']['code_revision'],
        'robot_state_sha': state['context']['robot_state_sha'],
        'config_sha256': state['context']['config_sha256'],
        'planned_interpretations': plans[shard], 'publications': 0,
        'outcomes': [{'interpretation_key': row['interpretation_key'], 'capture_inputs': row['inputs'],
            'status': 'quarantined' if quarantined else 'reused_private_interpretation',
            'database_readback': 'verified', 'database_tls_verified': True,
            'publication_approved': False, 'stage': 'parser_compatibility',
            'reason': 'edition_bound_parser_requires_review', 'error_type': 'EditionReviewRequired'}
            for row in entries]}


def test_durable_fair_cursor_resumes_all_four_shards_and_retains_exact_attempt_receipts():
    store, state, etag, plans = fixture()
    seen = []
    while choose_shard(state) is not None:
        seen.append(choose_shard(state))
        state, etag = commit_attempt(store, state, etag, report=report(state, plans))
        readback, observed_etag = load_active(store)
        assert readback == state and observed_etag == etag
        receipt = json.loads(store.client.objects[state['last_attempt']['key']])
        assert digest(receipt) == state['last_attempt']['sha256']
        assert receipt['checkpoint_after']['cursors'] == state['cursors']
    assert seen == [0, 1, 2, 3, 0]
    summary = campaign_summary(state)
    assert summary['status'] == 'complete'
    assert summary['denominator_interpretations'] == summary['validated_interpretations'] == 5
    assert summary['pending_interpretations'] == summary['unresolved_interpretations'] == 0
    assert len([key for key in store.client.objects if '/attempts/' in key]) == 5


def test_quarantines_and_scope_review_are_not_silently_skipped_or_claimed_complete():
    store, state, etag, plans = fixture(counts=(1, 0, 0, 0))
    state, _ = commit_attempt(store, state, etag, report=report(state, plans, quarantined=True))
    summary = campaign_summary(state)
    assert summary['pending_interpretations'] == 0
    assert summary['unresolved_interpretations'] == 1
    assert summary['validated_interpretations'] == 0
    assert summary['status'] == 'blocked_review'
    assert choose_shard(state) is None
    _, state, _, _ = fixture(counts=(0, 0, 0, 0), review=1)
    assert campaign_summary(state)['status'] == 'blocked_review'


def test_rejected_cursor_cas_retains_receipt_but_never_claims_progress():
    store, state, etag, plans = fixture()
    old = store.client.objects[ACTIVE_KEY]
    store.client.reject_cas = True
    with pytest.raises(RuntimeError, match='conditional persistence/readback failed'):
        commit_attempt(store, state, etag, report=report(state, plans))
    assert store.client.objects[ACTIVE_KEY] == old
    assert load_active(store)[0] == state
    assert len([key for key in store.client.objects if '/attempts/' in key]) == 1
    store.client.reject_cas = False
    # Interpretations committed before an interruption/CAS failure are retried at
    # the exact same cursor and inputs; ordinary transform reuse makes this safe.
    repeated = report(state, plans)
    updated, _ = commit_attempt(store, state, etag, report=repeated)
    assert updated['cursors'] == [1, 0, 0, 0]
    assert campaign_summary(updated)['validated_interpretations'] == 1
    assert len([key for key in store.client.objects if '/attempts/' in key]) == 2


def test_interruption_after_database_commit_before_checkpoint_replays_exact_same_input():
    store, state, etag, plans = fixture(counts=(1, 0, 0, 0))
    persisted = set()
    def idempotent_transform(entry):
        fresh = entry['interpretation_key'] not in persisted
        persisted.add(entry['interpretation_key'])
        return 'parsed_private_review_required' if fresh else 'reused_private_interpretation'
    entry = plans[0][0]
    assert idempotent_transform(entry) == 'parsed_private_review_required'
    # Simulated process death: no checkpoint or cursor update took place.
    resumed, same_etag = load_active(store)
    assert resumed['cursors'] == [0, 0, 0, 0]
    attempt = report(resumed, plans)
    attempt['outcomes'][0]['status'] = idempotent_transform(entry)
    updated, _ = commit_attempt(store, resumed, same_etag, report=attempt)
    assert len(persisted) == 1
    assert updated['cursors'] == [1, 0, 0, 0]
    assert campaign_summary(updated)['status'] == 'complete'


@pytest.mark.parametrize('field', ['code_revision', 'robot_state_sha', 'config_sha256',
                                   'planned_interpretations', 'capture_inputs', 'database_readback', 'publications'])
def test_frozen_divergence_and_unverified_success_cannot_advance(field):
    store, state, etag, plans = fixture()
    attempt = report(state, plans)
    if field in ('code_revision', 'robot_state_sha', 'config_sha256'):
        attempt[field] = 'f'*len(attempt[field])
    elif field == 'planned_interpretations':
        attempt[field] = attempt[field][:-1]
    elif field == 'capture_inputs':
        attempt['outcomes'][0][field] = {}
    elif field == 'database_readback':
        attempt['outcomes'][0][field] = 'not_verified'
    else:
        attempt['publications'] = 1
    before = deepcopy(store.client.objects)
    with pytest.raises(ValueError):
        commit_attempt(store, state, etag, report=attempt)
    assert store.client.objects == before


def test_pointer_and_frozen_context_tampering_fail_independent_readback():
    store, state, etag, plans = fixture()
    updated, _ = commit_attempt(store, state, etag, report=report(state, plans))
    corrupted = deepcopy(updated)
    next(iter(corrupted['validated'].values()))['status'] = 'forged'
    from white_list_archive.acquisition.historical_checkpoint import canonical
    store.client.objects[ACTIVE_KEY] = canonical(corrupted)
    with pytest.raises(RuntimeError, match='cursor evidence readback failed'):
        load_active(store)


def test_explicit_restart_preserves_old_context_attempt_and_closing_pointer():
    store, state, etag, plans = fixture()
    state, etag = commit_attempt(store, state, etag, report=report(state, plans))
    prior_objects = deepcopy(store.client.objects)
    context = deepcopy(state['context'])
    context.update(cycle_id='22222222-2222-4222-8222-222222222222', code_revision='d'*40,
                   previous_cycle_id=state['context']['cycle_id'])
    new, _ = initialise(store, context, previous=state, previous_etag=etag)
    assert new['cursors'] == [0, 0, 0, 0]
    for key, value in prior_objects.items():
        if key != ACTIVE_KEY:
            assert store.client.objects[key] == value
    assert len([key for key in store.client.objects if '/closures/' in key]) == 1
    assert load_active(store)[0] == new


def test_owner_command_and_daily_robot_wakeup_are_guarded_without_new_schedule_or_grants():
    workflow = Path('.github/workflows/transform-historical-captures.yml').read_text()
    assert 'workflow_run:' in workflow and "workflows: ['Prefecture robots']" in workflow
    assert 'schedule:' not in workflow
    assert 'actions: write' not in workflow and 'contents: write' not in workflow
    assert "github.event.comment.body == '/whitelist-history-resume'" in workflow
    assert 'github.event.issue.number == 225' in workflow
    assert '!github.event.issue.pull_request' in workflow
    assert 'github.actor == github.repository_owner' in workflow
    assert 'github.event.comment.user.login == github.repository_owner' in workflow
    assert "format('ignored-historical-{0}', github.run_id)" in workflow
    assert 'ref: ${{ needs.prepare-resume.outputs.code_revision }}' in workflow
    assert 'historical_checkpoint inspect' in workflow
    assert 'upload-artifact@' not in workflow


def test_only_exact_owner_command_and_trusted_daily_completion_authorise_prepare():
    from white_list_archive.acquisition.historical_checkpoint import authorised_wakeup
    common = dict(actor='owner', owner='owner', repository='owner/archive', ref='refs/heads/main')
    event = {'repository': {'full_name': 'owner/archive'}, 'action': 'created',
             'issue': {'number': 225},
             'comment': {'user': {'login': 'owner', 'type': 'User'}, 'body': '/whitelist-history-resume',
                         'created_at': '2026-11-08T10:00:00Z', 'updated_at': '2026-11-08T10:00:00Z'}}
    assert authorised_wakeup('issue_comment', event, **common)
    for mutation in ('actor', 'author', 'number', 'body', 'action', 'pr', 'repository', 'ref', 'bot', 'edited', 'missing_timestamp'):
        candidate, args = deepcopy(event), dict(common)
        if mutation == 'actor': args['actor'] = 'someone'
        elif mutation == 'author': candidate['comment']['user']['login'] = 'someone'
        elif mutation == 'number': candidate['issue']['number'] = 224
        elif mutation == 'body': candidate['comment']['body'] += ' --max-jobs 999'
        elif mutation == 'action': candidate['action'] = 'edited'
        elif mutation == 'pr': candidate['issue']['pull_request'] = {}
        elif mutation == 'repository': candidate['repository']['full_name'] = 'foreign/archive'
        elif mutation == 'bot': candidate['comment']['user']['type'] = 'Bot'
        elif mutation == 'edited': candidate['comment']['updated_at'] = '2026-11-08T10:01:00Z'
        elif mutation == 'missing_timestamp': candidate['comment'].pop('created_at')
        else: args['ref'] = 'refs/pull/1/merge'
        assert not authorised_wakeup('issue_comment', candidate, **args)
    robot = {'repository': {'full_name': 'owner/archive'}, 'action': 'completed',
        'workflow_run': {'name': 'Prefecture robots', 'conclusion': 'success',
            'head_branch': 'main', 'head_repository': {'full_name': 'owner/archive'}, 'event': 'schedule'}}
    assert authorised_wakeup('workflow_run', robot, **common)
    robot['workflow_run']['event'] = 'pull_request'
    assert not authorised_wakeup('workflow_run', robot, **common)
    assert not authorised_wakeup('unrelated_event', event, **common)


def test_workflow_job_and_input_sections_have_their_intended_top_level_shape():
    import re
    text = Path('.github/workflows/transform-historical-captures.yml').read_text()
    prefix, jobs = text.split('\njobs:\n', 1)
    assert set(re.findall(r'^  ([a-z][a-z-]+):', jobs, re.M)) == {
        'prepare-resume', 'resume-frozen-batch', 'historical-transform'}
    assert '  prepare-resume:' not in prefix
    assert '      max_jobs:\n        description:' in prefix
    assert '      selection_sha256:\n        description:' in prefix
    assert 'ref: ${{ needs.prepare-resume.outputs.code_revision }}' in jobs


def test_irrelevant_workflow_results_do_not_enter_shared_transform_concurrency():
    text = Path('.github/workflows/transform-historical-captures.yml').read_text()
    group = text.split('  group: >-\n', 1)[1].split('  cancel-in-progress:', 1)[0]
    assert "github.event.workflow_run.conclusion == 'success'" in group
    assert "github.event.workflow_run.name == 'Prefecture robots'" in group
    assert 'github.event.workflow_run.head_repository.full_name == github.repository' in group
    assert "github.event.comment.user.type == 'User'" in group
    assert 'github.event.comment.created_at == github.event.comment.updated_at' in group
    assert "format('ignored-historical-{0}', github.run_id)" in group
