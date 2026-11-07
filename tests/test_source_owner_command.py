from copy import deepcopy

import pytest

from white_list_archive.normalisation.source_command import PAIRS, REPOSITORY, authorise


def event(command='/cosenza-source-only 2026-06-28'):
    return {'action': 'created', 'repository': {'full_name': REPOSITORY},
            'issue': {'number': 225},
            'comment': {'body': command, 'user': {'login': 'colazeta', 'type': 'User'}}}


def call(payload, **kwargs):
    return authorise('issue_comment', payload, repository=REPOSITORY,
                     actor=kwargs.get('actor', 'colazeta'), ref=kwargs.get('ref', 'refs/heads/main'))


@pytest.mark.parametrize('command', PAIRS)
def test_only_exact_owner_commands_map_to_previously_pinned_input_pairs(command):
    result = call(event(command))
    assert (result['capture_id'], result['parse_run_id']) == PAIRS[command]
    assert result['mode'] == 'persist-source-only'


@pytest.mark.parametrize('change', [
    {'action': 'edited'}, {'repository': {'full_name': 'outsider/fork'}},
    {'issue': {'number': 224}}, {'issue': {'number': 225, 'pull_request': {}}},
    {'comment': {'body': '/cosenza-source-only 2026-06-28',
                 'user': {'login': 'outsider', 'type': 'User'}}},
    {'comment': {'body': '/cosenza-source-only 2026-06-28',
                 'user': {'login': 'colazeta', 'type': 'Bot'}}},
])
def test_untrusted_payloads_are_rejected_before_protected_execution(change):
    payload = event()
    payload.update(deepcopy(change))
    with pytest.raises(ValueError):
        call(payload)


@pytest.mark.parametrize('command', [
    'Please /cosenza-source-only 2026-06-28',
    '/cosenza-source-only 2026-06-28\nmode=publish',
    '/cosenza-source-only 2026-06-28 ', '/cosenza-source-only 2026-09-01',
])
def test_extra_text_cannot_inject_outputs_or_select_other_inputs(command):
    with pytest.raises(ValueError):
        call(event(command))


def test_spoofed_author_and_nonmain_context_are_rejected():
    for kwargs in ({'actor': 'outsider'}, {'ref': 'refs/pull/1/merge'}):
        with pytest.raises(ValueError):
            call(event(), **kwargs)


def test_push_is_read_only_even_if_payload_contains_persistence_inputs():
    result = authorise('push', {'inputs': {'mode': 'persist-source-only'}},
                       repository=REPOSITORY, actor='colazeta', ref='refs/heads/main')
    assert result['mode'] == 'preflight'


def test_manual_dispatch_requires_owner_and_an_exact_reviewed_pair():
    capture, run = next(iter(PAIRS.values()))
    payload = {'inputs': {'mode': 'persist-source-only', 'capture_id': capture, 'parse_run_id': run}}
    assert authorise('workflow_dispatch', payload, repository=REPOSITORY,
                     actor='colazeta', ref='refs/heads/main')['mode'] == 'persist-source-only'
    with pytest.raises(ValueError):
        authorise('workflow_dispatch', payload, repository=REPOSITORY,
                  actor='outsider', ref='refs/heads/main')
    payload['inputs']['parse_run_id'] = '00000000-0000-0000-0000-000000000000'
    with pytest.raises(ValueError):
        authorise('workflow_dispatch', payload, repository=REPOSITORY,
                  actor='colazeta', ref='refs/heads/main')


def test_protected_job_depends_on_secret_free_authorisation_and_frozen_code():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] /
            '.github/workflows/cosenza-rich-preflight.yml').read_text()
    initial, protected = text.split('  preflight:', 1)
    assert 'environment: evidence-archive' not in initial
    assert 'secrets.' not in initial
    assert 'needs: authorise' in protected
    assert 'ref: ${{ needs.authorise.outputs.code_revision }}' in protected
    assert 'github.event.comment.user.login == github.repository_owner' in initial
    assert '!github.event.issue.pull_request' in initial
