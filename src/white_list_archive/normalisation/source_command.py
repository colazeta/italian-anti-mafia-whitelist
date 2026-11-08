"""Authorise exact owner-only source commands before protected credentials exist."""
from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import UUID

REPOSITORY = 'colazeta/italian-anti-mafia-whitelist'
PAIRS = {
    '/cosenza-source-only 2026-06-28': (
        '9e769f09-3d3c-5d2a-b0f7-1b53ee5895c0', 'd0e644d0-ec85-4a7e-87e7-e5aa3dc48c23'),
    '/cosenza-source-only 2026-08-03': (
        '32f713a4-2106-5c58-8256-6f3c02c133c3', 'd03076ee-9e3d-4abc-bb4e-e1407ca50d42'),
}


def authorise(event_name, event, *, repository, actor, ref):
    if repository != REPOSITORY or ref != 'refs/heads/main':
        raise ValueError('Only the designated main repository may execute this operation')
    if event_name == 'issue_comment':
        issue, comment = event.get('issue', {}), event.get('comment', {})
        owner = REPOSITORY.split('/')[0]
        if (event.get('action') != 'created'
            or event.get('repository', {}).get('full_name') != REPOSITORY
            or actor != owner or comment.get('user', {}).get('login') != owner
            or comment.get('user', {}).get('type') != 'User'
            or issue.get('number') != 225 or 'pull_request' in issue
            or comment.get('body') not in PAIRS):
            raise ValueError('An exact owner command on issue225 is required')
        capture, run = PAIRS[comment['body']]
        mode = 'persist-source-only'
    elif event_name == 'workflow_run':
        run = event.get('workflow_run', {})
        if (run.get('name') != 'Prefecture robots' or run.get('conclusion') != 'success'
            or run.get('head_branch') != 'main'
            or run.get('head_repository', {}).get('full_name') != REPOSITORY
            or run.get('event') not in ('schedule', 'workflow_dispatch')):
            raise ValueError('Only the trusted ordinary robots run may wake the queue')
        capture, run = PAIRS['/cosenza-source-only 2026-06-28']
        mode = 'drain-owner-queue'
    elif event_name == 'push':
        capture, run = PAIRS['/cosenza-source-only 2026-06-28']
        mode = 'preflight'
    elif event_name == 'workflow_dispatch':
        inputs = event.get('inputs', {})
        mode = inputs.get('mode') or 'preflight'
        capture, run = inputs.get('capture_id'), inputs.get('parse_run_id')
        if mode not in ('preflight', 'persist-source-only'):
            raise ValueError('Unsupported explicit operation mode')
        capture, run = str(UUID(capture)), str(UUID(run))
        if actor != REPOSITORY.split('/')[0] or (capture, run) not in PAIRS.values():
            raise ValueError('Owner and exact reviewed capture/snapshot pair required')
    else:
        raise ValueError('Unsupported trigger')
    return {'mode': mode, 'capture_id': capture, 'parse_run_id': run}


def main():
    request = authorise(os.environ['GITHUB_EVENT_NAME'],
        json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text()),
        repository=os.environ['GITHUB_REPOSITORY'], actor=os.environ['GITHUB_ACTOR'],
        ref=os.environ['GITHUB_REF'])
    with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:
        for key, value in request.items():
            output.write(f'{key}={value}\n')


if __name__ == '__main__':
    main()
