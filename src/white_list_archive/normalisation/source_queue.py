"""Bounded private owner-request ledger, using existing issue225 and R2 only."""
from __future__ import annotations

import hashlib
import json
import re
from urllib.request import Request, urlopen

from .source_command import PAIRS, REPOSITORY, authorise

MAX_PAGES = 100
MAX_REQUESTS = 1000
MAX_RECEIPT_BYTES = 16_384
PREFIX = 'operations/v1/cosenza-owner-requests/'


def github_json(path, token):
    """Use fixed GitHub API origin; neither credentials nor errors are printed."""
    if not path.startswith(f'/repos/{REPOSITORY}/issues/'):
        raise ValueError('Unexpected queue API path')
    request = Request('https://api.github.com' + path, headers={
        'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'})
    with urlopen(request, timeout=30) as response:
        body = response.read(5_000_001)
    if len(body) > 5_000_000:
        raise ValueError('Queue API response exceeds bound')
    return json.loads(body)


def ledger_requests(fetch):
    """Snapshot every unedited original owner command; never infer edited intent."""
    issue = fetch(f'/repos/{REPOSITORY}/issues/225')
    if issue.get('number') != 225 or 'pull_request' in issue:
        raise ValueError('Queue ledger is not the designated issue')
    requests = []
    for page in range(1, MAX_PAGES + 1):
        comments = fetch(f'/repos/{REPOSITORY}/issues/225/comments?per_page=100&page={page}')
        if not isinstance(comments, list) or len(comments) > 100:
            raise ValueError('Invalid queue page')
        for comment in comments:
            if comment.get('body') not in PAIRS:
                continue
            payload = {'action': 'created', 'repository': {'full_name': REPOSITORY},
                       'issue': issue, 'comment': comment}
            try:
                authorised = authorise('issue_comment', payload, repository=REPOSITORY,
                    actor=comment.get('user', {}).get('login'), ref='refs/heads/main')
            except ValueError:
                continue
            if (type(comment.get('id')) is not int or comment['id'] <= 0
                    or not isinstance(comment.get('created_at'), str)
                    or comment.get('updated_at') != comment['created_at']):
                raise ValueError('Owner command lacks an unedited original creation snapshot')
            requests.append({**authorised, 'comment_id': comment['id'],
                'created_at': comment['created_at'],
                'body_sha256': hashlib.sha256(comment['body'].encode()).hexdigest()})
            if len(requests) > MAX_REQUESTS:
                raise ValueError('Owner request ledger exceeds bound')
        if len(comments) < 100:
            return sorted(requests, key=lambda row: row['comment_id'])
    raise ValueError('Owner request pagination limit reached; ledger is incomplete')


def read_receipt(store, key):
    from botocore.exceptions import ClientError
    try:
        stream = store.client.get_object(Bucket=store.config.bucket, Key=key)['Body']
    except ClientError as exc:
        if exc.response.get('Error', {}).get('Code') in ('NoSuchKey', '404'):
            return None
        raise
    try:
        raw = stream.read(MAX_RECEIPT_BYTES + 1)
    finally:
        stream.close()
    if len(raw) > MAX_RECEIPT_BYTES:
        raise ValueError('Queue receipt exceeds bound')
    return json.loads(raw)


def append_receipt(store, key, value):
    """Append conditionally, then verify exact immutable content independently."""
    from botocore.exceptions import ClientError
    body = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(body) > MAX_RECEIPT_BYTES:
        raise ValueError('Queue receipt exceeds bound')
    try:
        store.client.put_object(Bucket=store.config.bucket, Key=key, Body=body,
                                ContentType='application/json', IfNoneMatch='*')
    except ClientError as exc:
        if not (exc.response.get('Error', {}).get('Code') == 'PreconditionFailed'
                or exc.response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 412):
            raise
    saved = read_receipt(store, key)
    if saved != value:
        raise ValueError('Immutable queue receipt differs from the accepted request')
    return saved


def frozen_operation(revision, request, completion=None):
    """Execute actual trusted ancestor code in isolation; never relabel a revision."""
    import os
    from pathlib import Path
    import subprocess
    import sys
    import tempfile
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('Invalid frozen queue revision')
    root = Path(__file__).resolve().parents[3]
    def git(*args):
        return subprocess.run(['git', *args], cwd=root, capture_output=True, timeout=30, check=True)
    git('merge-base', '--is-ancestor', revision, 'HEAD')
    script = '''import json,sys
from white_list_archive.normalisation.cosenza_capture_rich import materialise
request=json.loads(sys.argv[1]); revision=sys.argv[2]; saved=json.loads(sys.argv[3])
if saved is None:
    result=materialise(capture_id=request['capture_id'],parse_run_id=request['parse_run_id'],code_revision=revision)
else:
    import os
    from white_list_archive.acquisition.auto_transform import private_connection
    from white_list_archive.persistence.capture_rich_cosenza import verify_rich_readback
    from white_list_archive.storage.capture_catalogue import CaptureCatalogue
    from white_list_archive.storage.catalogue_recovery import load_catalogued_capture
    from white_list_archive.storage.evidence import EvidenceStore,StoreConfig,client_for
    config=StoreConfig.from_env(); store=EvidenceStore(client_for(config),config)
    manifest,_=load_catalogued_capture(CaptureCatalogue(store),source_key='cosenza-combined',capture_id=request['capture_id'])
    store.read_verified(manifest)
    with private_connection(os.environ['EVIDENCE_DATABASE_URL']) as conn:
        verify_rich_readback(conn,capture_id=request['capture_id'],parse_run_id=saved['parse_run_id'],source_sha256=manifest['sha256'],expected_count=saved['record_count'],expected_snapshot_sha256=saved['snapshot_sha256'],code_revision=revision)
        conn.rollback()
    result=saved
print(json.dumps(result,sort_keys=True))
'''
    with tempfile.TemporaryDirectory(prefix='trusted-owner-source-') as directory:
        checkout = Path(directory) / 'code'
        git('worktree', 'add', '--detach', str(checkout), revision)
        try:
            actual = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=checkout,
                                    capture_output=True, timeout=30, check=True).stdout.decode().strip()
            if actual != revision:
                raise ValueError('Frozen queue checkout mismatch')
            env = dict(os.environ, PYTHONPATH=str(checkout / 'src'))
            with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
                result = subprocess.run([sys.executable, '-c', script, json.dumps(request), revision,
                                         json.dumps(completion)], cwd=checkout, env=env,
                                        stdout=output, stderr=errors, timeout=600)
                output.seek(0)
                body = output.read(MAX_RECEIPT_BYTES + 1)
            if result.returncode != 0 or len(body) > MAX_RECEIPT_BYTES:
                raise RuntimeError('Frozen source operation failed; private output suppressed')
            value = json.loads(body)
            allowed = {'parse_run_id','record_count','field_value_count','entity_mention_count',
                'snapshot_sha256','rich_readback_verified','editions_created','publications',
                'capture_id','prerequisite_parse_run_id','code_revision','parse_run_reused',
                'snapshot_reused','preflight_verified','committed_readback_verified','mode',
                'semantic_writes','canonical_writes','edition_approvals'}
            if (not isinstance(value, dict) or set(value) - allowed
                or value.get('rich_readback_verified') is not True
                or value.get('committed_readback_verified') is not True
                or value.get('capture_id') != request['capture_id']
                or value.get('prerequisite_parse_run_id') != request['parse_run_id']
                or value.get('code_revision') != revision
                or any(value.get(k) != 0 for k in ('editions_created','publications','semantic_writes','canonical_writes','edition_approvals'))):
                raise ValueError('Frozen source operation lacks complete source-only evidence')
            return value
        finally:
            git('worktree', 'remove', '--force', str(checkout))


def verify_queue_qa(store, request, result, source_revision, qa_revision):
    """Read-only QA uses its own current revision; its report remains private."""
    from white_list_archive.acquisition.auto_transform import private_connection, persist_operational_report
    from white_list_archive.normalisation.cosenza_qa import assess
    import os
    with private_connection(os.environ['EVIDENCE_DATABASE_URL']) as conn:
        report = assess(conn, capture_id=request['capture_id'], parse_run_id=result['parse_run_id'],
            code_revision=source_revision, expected_count=result['record_count'],
            qa_code_revision=qa_revision)
        conn.rollback()
    if (report.get('writes') != 0 or report.get('semantic_ready') is not False
        or report.get('publication_ready') is not False
        or report.get('gates', {}).get('structural_parser_lineage', {}).get('status') != 'ready'):
        raise ValueError('Queue QA did not verify the source-only boundary')
    persist_operational_report(store, report)


def drain_requests(store, requests, revision, *, execute=frozen_operation, qa=verify_queue_qa, limit=50):
    """At most fifty request receipts and two newly materialised pairs per wake-up."""
    verified = failures = processed = new_requests = new_completions = 0
    cache = {}
    verified_results = {}
    qa_verified = set()
    failed_pairs = set()
    for request in requests:
        key = PREFIX + str(request['comment_id'])
        cache_key = None
        try:
            receipt = read_receipt(store, key + '/accepted.json')
            pair = (request['capture_id'], request['parse_run_id'])
            if receipt is None:
                if new_requests >= limit:
                    continue
                new_requests += 1
                frozen = cache[pair][0] if pair in cache else revision
                receipt = append_receipt(store, key + '/accepted.json',
                    {'schema_version': 1, 'request': request, 'code_revision': frozen})
            if (set(receipt) != {'schema_version', 'request', 'code_revision'}
                    or receipt['schema_version'] != 1 or receipt['request'] != request):
                raise ValueError('Queue request binding mismatch')
            frozen = receipt['code_revision']
            completed = read_receipt(store, key + '/completed.json')
            cache_key = (pair, frozen)
            if cache_key in failed_pairs:
                raise ValueError('Equivalent queue operation already failed this wake-up')
            if completed is None:
                if new_completions >= limit:
                    continue
                new_completions += 1
            if completed is not None:
                if set(completed) != {'accepted', 'result'} or completed['accepted'] != receipt:
                    raise ValueError('Queue completion binding mismatch')
                if cache_key in verified_results:
                    if verified_results[cache_key] != completed['result']:
                        raise ValueError('Inconsistent immutable queue completion')
                    result = verified_results[cache_key]
                else:
                    if processed >= limit:
                        continue
                    processed += 1
                    result = execute(frozen, request, completed['result'])
            elif pair in cache and cache[pair][0] == frozen:
                # The earlier result was independently read back in this worker.
                result = cache[pair][1]
            else:
                if processed >= limit:
                    continue
                processed += 1
                result = execute(frozen, request)
            if cache_key not in qa_verified:
                qa(store, request, result, frozen, revision)
                qa_verified.add(cache_key)
            if completed is None:
                append_receipt(store, key + '/completed.json', {'accepted': receipt, 'result': result})
            cache[pair] = (frozen, result)
            verified_results[cache_key] = result
            verified += 1
        except Exception:
            if cache_key is not None:
                failed_pairs.add(cache_key)
            # No provider exceptions, source rows, request IDs or private keys escape.
            failures += 1
    return {'requests_expected': len(requests), 'requests_verified': verified,
            'requests_pending': len(requests) - verified, 'diagnostic_failures': failures,
            'bounded_remaining': len(requests) - verified - failures,
            'qa_reports_verified': len(qa_verified), 'semantic_ready': False, 'publication_ready': False,
            'publications': 0, 'edition_approvals': 0}


def main():
    import os
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    try:
        requests = ledger_requests(lambda path: github_json(path, os.environ['GITHUB_TOKEN']))
        config = StoreConfig.from_env()
        store = EvidenceStore(client_for(config), config)
        report = drain_requests(store, requests, os.environ['EXECUTING_REVISION'])
    except Exception:
        report = {'requests_expected': None, 'requests_verified': 0, 'requests_pending': None,
                  'diagnostic_failures': 1, 'publications': 0, 'edition_approvals': 0}
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(1 if report['diagnostic_failures'] or report['requests_pending'] else 0)


if __name__ == '__main__':
    main()
