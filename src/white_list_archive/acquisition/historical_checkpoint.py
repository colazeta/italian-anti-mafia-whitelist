"""Private CAS cursor and immutable receipts for a frozen historical campaign.

The active pointer is operational state. Source originals and historical evidence
are never overwritten. Checkpoint failure leaves committed interpretations safe to
replay through the common idempotent transformer.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from uuid import uuid4

from .historical_transform import (
    digest, execute_batch, select_historical_jobs, selection_manifest, select_batch,
)
from white_list_archive.storage.robot_recovery import read_robot_history

ACTIVE_KEY = 'operations/v1/historical-backlog/active.json'
PREFIX = 'operations/v1/historical-backlog/cycles/'
MAX_BYTES = 2_000_000
SHA40 = re.compile(r'[0-9a-f]{40}')
SHA64 = re.compile(r'[0-9a-f]{64}')
SUCCESS = {'parsed_private_review_required', 'reused_private_interpretation'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def now():
    return datetime.now(timezone.utc).isoformat()


def _read(store, key):
    response = store.client.get_object(Bucket=store.config.bucket, Key=key)
    stream = response['Body']
    try:
        raw = stream.read(MAX_BYTES + 1)
    finally:
        stream.close()
    if len(raw) > MAX_BYTES:
        raise ValueError('Historical checkpoint exceeds its bound')
    document = json.loads(raw)
    if not isinstance(document, dict) or canonical(document) != raw:
        raise ValueError('Historical checkpoint is not canonical JSON')
    return document, response.get('ETag')


def _put_verified(store, key, document, *, etag=None):
    body = canonical(document)
    if len(body) > MAX_BYTES:
        raise ValueError('Historical checkpoint exceeds its bound')
    condition = {'IfMatch': etag} if etag is not None else {'IfNoneMatch': '*'}
    try:
        store.client.put_object(Bucket=store.config.bucket, Key=key, Body=body,
                                ContentType='application/json', **condition)
        actual, actual_etag = _read(store, key)
    except Exception:
        raise RuntimeError('Historical checkpoint conditional persistence/readback failed') from None
    if canonical(actual) != body:
        raise RuntimeError('Historical checkpoint failed exact readback')
    return hashlib.sha256(body).hexdigest(), actual_etag


def validate_state(state):
    if set(state) != {'schema_version', 'context', 'cursors', 'next_shard', 'validated',
                      'unresolved', 'last_attempt', 'updated_at'} or state['schema_version'] != 1:
        raise ValueError('Invalid historical active-state schema')
    context = state['context']
    if set(context) != {'schema_version', 'cycle_id', 'code_revision', 'config_sha256',
                        'robot_state_sha', 'selection', 'created_at', 'previous_cycle_id'}:
        raise ValueError('Invalid frozen historical context')
    if context['schema_version'] != 1 or not re.fullmatch(r'[0-9a-f-]{36}', context['cycle_id']):
        raise ValueError('Invalid frozen historical identity')
    if any(not isinstance(context[key], str) or not SHA40.fullmatch(context[key])
           for key in ('code_revision', 'robot_state_sha')):
        raise ValueError('Historical campaign requires exact code and robot revisions')
    if not isinstance(context['config_sha256'], str) or not SHA64.fullmatch(context['config_sha256']):
        raise ValueError('Historical campaign requires exact configuration identity')
    selection = context['selection']
    if not isinstance(selection, list) or len(selection) != 4:
        raise ValueError('Historical campaign must cover four authority shards')
    for shard, row in enumerate(selection):
        if (set(row) != {'shard', 'selection_sha256', 'interpretations', 'review_items'}
            or row['shard'] != shard or not SHA64.fullmatch(row['selection_sha256'])
            or any(type(row[name]) is not int or row[name] < 0 for name in ('interpretations', 'review_items'))):
            raise ValueError('Invalid historical selection denominator')
    cursors = state['cursors']
    if (not isinstance(cursors, list) or len(cursors) != 4 or
        any(type(cursor) is not int or not 0 <= cursor <= selection[i]['interpretations']
            for i, cursor in enumerate(cursors))):
        raise ValueError('Historical cursor exceeds its frozen denominator')
    if type(state['next_shard']) is not int or not 0 <= state['next_shard'] < 4:
        raise ValueError('Invalid fair historical shard cursor')
    for name in ('validated', 'unresolved'):
        if not isinstance(state[name], dict) or any(not SHA64.fullmatch(key) for key in state[name]):
            raise ValueError('Invalid historical result ledger')
    if set(state['validated']) & set(state['unresolved']):
        raise ValueError('A historical interpretation cannot be validated and unresolved')
    if len(state['validated']) + len(state['unresolved']) != sum(cursors):
        raise ValueError('Historical attempt ledger does not cover its cursor exactly')
    return state


def load_active(store):
    try:
        state, etag = _read(store, ACTIVE_KEY)
    except Exception as exc:
        code = getattr(exc, 'response', {}).get('Error', {}).get('Code')
        if code in ('NoSuchKey', 'NotFound', '404'):
            return None, None
        raise RuntimeError('Private historical active-state readback failed') from None
    validate_state(state)
    try:
        context, _ = _read(store, PREFIX + state['context']['cycle_id'] + '/context.json')
        if context != state['context']:
            raise ValueError('Active context differs from immutable campaign evidence')
        if sum(state['cursors']):
            last = state['last_attempt']
            if not isinstance(last, dict) or set(last) != {'key', 'sha256'}:
                raise ValueError('Historical cursor lacks an attempt receipt')
            if not last['key'].startswith(PREFIX + context['cycle_id'] + '/attempts/'):
                raise ValueError('Historical receipt belongs to another campaign')
            receipt, _ = _read(store, last['key'])
            if digest(receipt) != last['sha256'] or receipt.get('context') != context:
                raise ValueError('Historical cursor receipt integrity failed')
            if receipt.get('checkpoint_after') != {k: v for k, v in state.items() if k != 'last_attempt'}:
                raise ValueError('Historical cursor diverges from its immutable attempt receipt')
        elif state['last_attempt'] is not None:
            raise ValueError('Empty historical cursor has an unexpected attempt receipt')
    except Exception:
        raise RuntimeError('Private historical cursor evidence readback failed') from None
    if not isinstance(etag, str) or not etag:
        raise ValueError('Historical active-state CAS requires a provider ETag')
    return state, etag


def initialise(store, context, *, previous=None, previous_etag=None):
    state = {'schema_version': 1, 'context': context, 'cursors': [0, 0, 0, 0],
             'next_shard': 0, 'validated': {}, 'unresolved': {},
             'last_attempt': None, 'updated_at': now()}
    validate_state(state)
    if previous is None and (previous_etag is not None or context['previous_cycle_id'] is not None):
        raise ValueError('Initial campaign cannot replace unrecorded operational state')
    if previous is not None:
        validate_state(previous)
        if previous_etag is None or context['previous_cycle_id'] != previous['context']['cycle_id']:
            raise ValueError('Replacing a campaign requires its exact previous pointer')
        _put_verified(store, PREFIX + previous['context']['cycle_id'] + '/closures/' + str(uuid4()) + '.json', previous)
    _put_verified(store, PREFIX + context['cycle_id'] + '/context.json', context)
    _, etag = _put_verified(store, ACTIVE_KEY, state, etag=previous_etag)
    if not etag:
        raise ValueError('Historical active-state CAS requires a provider ETag')
    return state, etag


def campaign_summary(state):
    validate_state(state)
    total = sum(row['interpretations'] for row in state['context']['selection'])
    pending = total - sum(state['cursors'])
    review = sum(row['review_items'] for row in state['context']['selection'])
    unresolved = len(state['unresolved'])
    status = 'pending' if pending else ('blocked_review' if unresolved or review else 'complete')
    return {'cycle_id': state['context']['cycle_id'], 'denominator_interpretations': total,
            'attempted_interpretations': sum(state['cursors']), 'pending_interpretations': pending,
            'validated_interpretations': len(state['validated']),
            'unresolved_interpretations': unresolved, 'selection_review_items': review,
            'status': status, 'publications': 0}


def choose_shard(state):
    validate_state(state)
    for offset in range(4):
        shard = (state['next_shard'] + offset) % 4
        if state['cursors'][shard] < state['context']['selection'][shard]['interpretations']:
            return shard
    return None


def commit_attempt(store, state, etag, *, report):
    """Persist complete attempt evidence before advancing the mutable CAS cursor."""
    validate_state(state)
    shard = choose_shard(state)
    if shard is None or report.get('cycle_id') != state['context']['cycle_id'] or report.get('shard') != shard:
        raise ValueError('Attempt does not match the active fair campaign')
    context = state['context']
    for key in ('code_revision', 'robot_state_sha', 'config_sha256'):
        if report.get(key) != context[key]:
            raise ValueError('Historical attempt diverges from frozen context')
    plan = report.get('planned_interpretations')
    expected = context['selection'][shard]
    if not isinstance(plan, list) or len(plan) != expected['interpretations'] or digest(plan) != expected['selection_sha256']:
        raise ValueError('Historical attempt selection differs from its frozen denominator')
    cursor = state['cursors'][shard]
    if report.get('publications') != 0:
        raise ValueError('Private historical campaign must never promote public observations')
    outcomes = report.get('outcomes')
    if (report.get('cursor') != cursor or not isinstance(outcomes, list) or not 1 <= len(outcomes) <= 10
        or cursor + len(outcomes) > len(plan)):
        raise ValueError('Historical attempt cursor or size is invalid')
    updated = deepcopy(state)
    for entry, result in zip(plan[cursor:cursor+len(outcomes)], outcomes):
        key = entry['interpretation_key']
        if result.get('interpretation_key') != key or result.get('capture_inputs') != entry['inputs']:
            raise ValueError('Historical attempt result input lineage differs from its planned job')
        if result.get('status') in SUCCESS:
            if (result.get('database_readback') != 'verified' or result.get('database_tls_verified') is not True
                or result.get('publication_approved') is not False):
                raise ValueError('Historical validation requires actual database/TLS readback and no public approval')
            updated['validated'][key] = {'status': result['status']}
        elif result.get('status') == 'quarantined':
            updated['unresolved'][key] = {name: result.get(name) for name in ('stage', 'reason', 'error_type')}
        else:
            raise ValueError('Unknown historical attempt result')
    updated['cursors'][shard] += len(outcomes)
    updated['next_shard'] = (shard + 1) % 4
    updated['updated_at'] = now()
    receipt_key = PREFIX + context['cycle_id'] + '/attempts/' + str(uuid4()) + '.json'
    receipt = {'schema_version': 1, 'report_kind': 'resumable_historical_attempt',
               'context': context, 'report': report,
               'cursor_before': state['cursors'], 'cursor_after': updated['cursors'],
               'checkpoint_before_sha256': digest(state),
               'checkpoint_after': {k: v for k, v in updated.items() if k != 'last_attempt'}}
    receipt_sha, _ = _put_verified(store, receipt_key, receipt)
    updated['last_attempt'] = {'key': receipt_key, 'sha256': receipt_sha}
    validate_state(updated)
    _, new_etag = _put_verified(store, ACTIVE_KEY, updated, etag=etag)
    if not new_etag:
        raise ValueError('Historical cursor update lacks its CAS readback ETag')
    return updated, new_etag


def build_context(root, robot_head, config_path, *, previous_cycle_id=None):
    snapshots, metrics = read_robot_history(root, robot_head)
    configuration = json.loads(config_path.read_text())
    selection = []
    for shard in range(4):
        jobs, issues = select_historical_jobs(snapshots, configuration, shard=shard, shards=4)
        selection.append({'shard': shard, 'selection_sha256': digest(selection_manifest(jobs)),
                          'interpretations': len(jobs), 'review_items': len(issues)})
    return {'schema_version': 1, 'cycle_id': str(uuid4()),
            'code_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            'config_sha256': hashlib.sha256(config_path.read_bytes()).hexdigest(),
            'robot_state_sha': metrics['robot_state_sha'], 'selection': selection,
            'created_at': now(), 'previous_cycle_id': previous_cycle_id}


def authorised_wakeup(event_name, event, *, actor, owner, repository, ref):
    """Defence in depth for the secret-bearing prepare job's closed event contract."""
    if ref != 'refs/heads/main' or event.get('repository', {}).get('full_name') != repository:
        return False
    if event_name in {'push', 'workflow_dispatch'}:
        return True
    if event_name == 'issue_comment':
        issue, comment = event.get('issue', {}), event.get('comment', {})
        return (event.get('action') == 'created' and issue.get('number') == 225
                and 'pull_request' not in issue and actor == owner
                and comment.get('user', {}).get('login') == owner
                and comment.get('user', {}).get('type') == 'User'
                and isinstance(comment.get('created_at'), str) and bool(comment['created_at'])
                and comment.get('created_at') == comment.get('updated_at')
                and comment.get('body') == '/whitelist-history-resume')
    if event_name == 'workflow_run':
        run = event.get('workflow_run', {})
        return (event.get('action') == 'completed' and run.get('name') == 'Prefecture robots'
                and run.get('conclusion') == 'success' and run.get('head_branch') == 'main'
                and run.get('head_repository', {}).get('full_name') == repository
                and run.get('event') in {'schedule', 'workflow_dispatch'})
    return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'resume', 'inspect'))
    parser.add_argument('--robot-head', default='refs/remotes/origin/robot-state')
    parser.add_argument('--source-config', type=Path, default=Path('data/publication/multi_prefecture_pilot.json'))
    parser.add_argument('--max-jobs', type=int, default=10)
    parser.add_argument('--expected-cycle-id')
    parser.add_argument('--restart-cycle', action='store_true')
    args = parser.parse_args(argv)
    if not 1 <= args.max_jobs <= 10:
        raise ValueError('Historical invocation must contain at most ten jobs')
    if args.mode == 'prepare' and os.environ.get('GITHUB_ACTIONS') == 'true':
        event_name = os.environ['GITHUB_EVENT_NAME']
        event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        if not authorised_wakeup(event_name, event, actor=os.environ['GITHUB_ACTOR'],
            owner=os.environ['GITHUB_REPOSITORY_OWNER'], repository=os.environ['GITHUB_REPOSITORY'],
            ref=os.environ['GITHUB_REF']):
            raise ValueError('Historical wake-up is not authorised')
        if args.restart_cycle and event_name != 'workflow_dispatch':
            raise ValueError('Campaign replacement requires an explicit manual dispatch')
    if args.restart_cycle and args.mode != 'prepare':
        raise ValueError('Campaign replacement is an explicit preparation action')
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    config = StoreConfig.from_env()
    store = EvidenceStore(client_for(config), config)
    root = Path('.').resolve()
    state, etag = load_active(store)
    if args.mode == 'prepare' and (state is None or args.restart_cycle):
        context = build_context(root, args.robot_head, args.source_config,
            previous_cycle_id=state['context']['cycle_id'] if state else None)
        state, etag = initialise(store, context, previous=state, previous_etag=etag)
    if state is None:
        raise ValueError('No frozen historical campaign has been prepared')
    if args.mode == 'prepare':
        print('code_revision=' + state['context']['code_revision'])
        print('robot_state_sha=' + state['context']['robot_state_sha'])
        print('cycle_id=' + state['context']['cycle_id'])
        print('has_work=' + ('true' if choose_shard(state) is not None else 'false'))
        return 0
    if args.mode == 'inspect':
        print(json.dumps({**campaign_summary(state), 'private_checkpoint_readback_verified': True}, sort_keys=True))
        return 0
    if args.expected_cycle_id != state['context']['cycle_id']:
        raise ValueError('Prepared historical campaign changed before worker execution')
    context = state['context']
    code = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    config_sha = hashlib.sha256(args.source_config.read_bytes()).hexdigest()
    if code != context['code_revision'] or config_sha != context['config_sha256']:
        raise ValueError('Worker code/configuration differs from frozen campaign')
    shard = choose_shard(state)
    if shard is None:
        print(json.dumps(campaign_summary(state), sort_keys=True))
        return 0
    snapshots, _ = read_robot_history(root, context['robot_state_sha'])
    jobs, issues = select_historical_jobs(snapshots, json.loads(args.source_config.read_text()), shard=shard, shards=4)
    plan = selection_manifest(jobs)
    frozen = context['selection'][shard]
    if digest(plan) != frozen['selection_sha256'] or len(jobs) != frozen['interpretations'] or len(issues) != frozen['review_items']:
        raise ValueError('Historical campaign selection diverged')
    batch, coverage = select_batch(jobs, cursor=state['cursors'][shard], max_jobs=args.max_jobs)
    dsn = os.environ.get('EVIDENCE_DATABASE_URL')
    if not dsn:
        raise ValueError('Historical campaign requires the designated database writer')
    outcomes = execute_batch(batch, store=store, dsn=dsn, code_revision=code,
        authority_registry=root/'data/source_registry/territorial_authorities.csv',
        series_registry=root/'data/source_registry/source_series_inventory.csv')
    report = {'cycle_id': context['cycle_id'], 'shard': shard, 'shards': 4,
              'code_revision': code, 'robot_state_sha': context['robot_state_sha'],
              'config_sha256': config_sha, 'run_at': now(), **coverage,
              'planned_interpretations': plan, 'selection_review_items': issues,
              'outcomes': outcomes, 'publications': 0}
    updated, _ = commit_attempt(store, state, etag, report=report)
    print(json.dumps({**campaign_summary(updated), 'batch_shard': shard,
        'batch_cursor_before': state['cursors'][shard], 'batch_cursor_after': updated['cursors'][shard],
        'batch_attempted': len(outcomes), 'private_checkpoint_readback_verified': True}, sort_keys=True))
    return 1 if any(row['status'] == 'quarantined' or row.get('diagnostic_failure') for row in outcomes) else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        raise SystemExit('Historical campaign failed (' + type(exc).__name__ + ')') from None
