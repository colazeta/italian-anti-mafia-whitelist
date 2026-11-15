from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import os
import sys

import pytest

from white_list_archive.publishing import publication_handoff as handoff
from white_list_archive.publishing.public_snapshot import FILES, REPOSITORY
from test_public_history import fixture_registry, reconcile


def _complete(data):
    for report in data['meta']['sources']:
        row = next(r for r in data['records'] if r['source_key'] == report['source_key'])
        report.update({k: row[k] for k in ('authority_key', 'register_key', 'population_scope')})
        report['parser'] = row['parser_name']
    return data


def _manifest(data, tag):
    body = json.dumps(data, ensure_ascii=False).encode()
    files = {name: (body if name == 'registry.json' else name.encode()) for name in FILES}
    manifest = {'schema_version': 1, 'repository': REPOSITORY, 'release_tag': tag,
                'files': {name: {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                          for name, raw in files.items()}}
    return manifest, files


def fixture():
    other = deepcopy(fixture_registry()['records'])
    for row in other:
        row.update(source_key='other-combined', authority_key='other', register_key='other-register',
                   record_locator='other:' + row['record_locator'])
    before = _complete(reconcile(fixture_registry()['records'] + other))
    after = _complete(reconcile(fixture_registry('2026-07-01', 'b'*64, ('listed', 'listed', 'pending'))['records'] + other))
    selected_manifest, selected_files = _manifest(before, 'public-data-old')
    candidate_manifest, candidate_files = _manifest(after, 'public-data-new')
    config = {'sources': [{**s} for s in after['meta']['sources']]}
    monitoring = {'prefectures': [{'authority_key': a} for a in ('fixture', 'other', 'unpublished')]}
    rows = [r for r in after['records'] if r['source_key'] == 'fixture-combined']
    intent = {'schema_version': 1, 'baseline_manifest_sha256': handoff._digest(selected_manifest),
              'source_config_sha256': handoff._digest(config), 'review_document': 'docs/sources/fixture-review.md',
              'changes': {'fixture-combined': {'count': 3, 'statuses': {'listed': 2, 'pending': 1},
                  'reference_date': '2026-07-01', 'sha256': 'b'*64, 'parser': 'fixture_parser',
                  'records_sha256': handoff.records_digest(rows)}}}
    return dict(selected_manifest=selected_manifest, candidate_manifest=candidate_manifest,
                selected_bytes=selected_files['registry.json'], candidate_bytes=candidate_files['registry.json'],
                config=config, monitoring=monitoring, intent=intent)


def test_reviewed_candidate_prepares_exact_two_file_surface_without_approval_or_deploy():
    args = fixture()
    original = deepcopy(args)
    receipt, files = handoff.prepare_proposal(**args)
    assert args == original
    assert set(files) == {handoff.SELECTOR, handoff.MONITORING}
    assert receipt['state'] == 'selector_proposal_ready'
    assert receipt['publications'] == 0 and receipt['approval_granted'] is False
    state = json.loads(files[handoff.MONITORING])
    assert state['selected_publication']['release_tag'] == 'public-data-new'
    assert state['selected_publication']['source_presences'] == 5
    assert state['selected_publication']['live_deployment_verified'] is None
    assert state['prefectures'][2]['latest_selected_public_reference_date'] is None


def test_unchanged_observations_with_new_check_times_do_not_create_duplicate_releases():
    args = fixture()
    same = json.loads(args['selected_bytes'])
    for report in same['meta']['sources']:
        report['document_checked_at'] = '2026-11-15T12:00:00Z'
    manifest, files = _manifest(same, 'public-data-rechecked')
    args.update(candidate_manifest=manifest, candidate_bytes=files['registry.json'], intent=None)
    result, proposal = handoff.prepare_proposal(**args)
    assert result['state'] == 'no_release_delta' and proposal == {}


def test_new_source_without_review_intent_remains_unapproved_and_has_no_selector():
    args = fixture()
    args['intent'] = None
    result, files = handoff.prepare_proposal(**args)
    assert result['state'] == 'review_intent_required' and files == {}


@pytest.mark.parametrize('defect', ['baseline', 'config', 'scope', 'rows', 'statuses', 'digest', 'date', 'populations', 'report', 'source_time', 'outside_rows'])
def test_stale_unreviewed_or_outside_scope_inputs_fail_closed(defect):
    args = fixture()
    intent = args['intent']
    if defect == 'baseline': intent['baseline_manifest_sha256'] = '0'*64
    if defect == 'config': intent['source_config_sha256'] = '0'*64
    if defect == 'scope': intent['changes']['other-combined'] = deepcopy(intent['changes']['fixture-combined'])
    if defect == 'rows': intent['changes']['fixture-combined']['count'] = 4
    if defect == 'statuses': intent['changes']['fixture-combined']['statuses'] = {'listed': 3}
    if defect == 'digest': intent['changes']['fixture-combined']['records_sha256'] = '0'*64
    if defect in {'date', 'report', 'outside_rows', 'source_time'}:
        candidate = json.loads(args['candidate_bytes'])
        if defect == 'date': intent['changes']['fixture-combined']['reference_date'] = '2026-05-01'
        if defect == 'report': candidate['meta']['sources'][1]['document_checked_at'] = '2026-11-15T12:00:00Z'
        if defect == 'source_time': candidate['meta']['sources'][0]['document_checked_at'] = ''
        if defect == 'outside_rows': candidate['records'][-1]['name'] = 'Unreviewed change'
        manifest, files = _manifest(candidate, 'public-data-new')
        args.update(candidate_manifest=manifest, candidate_bytes=files['registry.json'])
    if defect == 'populations':
        args['config']['sources'][0]['population_scope'] = 'listed'
        intent['source_config_sha256'] = handoff._digest(args['config'])
    with pytest.raises(ValueError): handoff.prepare_proposal(**args)


def test_changed_wrapper_tag_reuses_one_proposal_identity_for_the_same_reviewed_data():
    args = fixture()
    first, _ = handoff.prepare_proposal(**args)
    args['candidate_manifest']['release_tag'] = 'public-data-another-attempt'
    second, _ = handoff.prepare_proposal(**args)
    assert first['branch'] == second['branch']
    assert first['proposal_identity'] == second['proposal_identity']


@pytest.mark.parametrize('name', sorted(FILES))
def test_every_candidate_asset_is_rehashed_before_a_proposal(tmp_path, name):
    data = _complete(fixture_registry())
    manifest, files = _manifest(data, 'public-data-new')
    for key, body in files.items(): (tmp_path / key).write_bytes(body)
    assert handoff.verify_candidate_files(manifest, tmp_path) == files['registry.json']
    (tmp_path / name).write_bytes(files[name] + b'corrupt')
    with pytest.raises(ValueError, match='integrity'):
        handoff.verify_candidate_files(manifest, tmp_path)


def test_preserver_retry_selects_one_existing_build_artifact_and_rejects_ambiguity():
    rows = [{'name': 'public-portal-review-attempt-1', 'expired': False},
            {'name': 'public-portal-review-attempt-2', 'expired': True},
            {'name': 'unrelated-private-output', 'expired': False}]
    assert handoff.choose_build_artifact(rows) == 'public-portal-review-attempt-1'
    with pytest.raises(ValueError): handoff.choose_build_artifact(rows + [rows[0]])
    with pytest.raises(ValueError): handoff.choose_build_artifact([])


def _git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL).decode().strip()


def _repo(tmp_path, monkeypatch):
    remote, root = tmp_path/'remote.git', tmp_path/'checkout'
    subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
    subprocess.run(['git', 'init', '-b', 'main', str(root)], check=True, capture_output=True)
    for key, value in [('user.name', 'Fixture'), ('user.email', 'fixture@example.test')]: _git(root, 'config', key, value)
    for path in handoff.PROPOSAL_PATHS:
        file = root/path; file.parent.mkdir(parents=True, exist_ok=True); file.write_text('old\n')
    _git(root, 'add', '.'); _git(root, 'commit', '-m', 'Base')
    _git(root, 'remote', 'add', 'origin', str(remote)); _git(root, 'push', 'origin', 'main')
    monkeypatch.chdir(root)
    return root, remote, _git(root, 'rev-parse', 'HEAD')


def test_real_git_proposal_is_idempotent_and_never_writes_main(tmp_path, monkeypatch):
    root, remote, base = _repo(tmp_path, monkeypatch)
    receipt, files = handoff.prepare_proposal(**fixture())
    commit, created = handoff.write_proposal_branch(files, receipt, base)
    assert created
    assert handoff.write_proposal_branch(files, receipt, base) == (commit, False)
    assert _git(root, 'rev-parse', 'HEAD') == base
    assert _git(remote, 'rev-parse', 'refs/heads/main') == base
    assert set(_git(root, 'diff', '--name-only', base, commit).splitlines()) == set(handoff.PROPOSAL_PATHS)
    # A conflicting branch is not force-pushed or silently adopted.
    with pytest.raises(ValueError):
        handoff.write_proposal_branch({**files, handoff.MONITORING: 'conflict\n'}, receipt, base)
    assert _git(remote, 'rev-parse', 'refs/heads/' + receipt['branch']) == commit


def test_real_git_blocks_stale_publication_code_but_allows_unrelated_docs(tmp_path, monkeypatch):
    root, _, base = _repo(tmp_path, monkeypatch)
    (root/'README.md').write_text('unrelated documentation')
    _git(root, 'add', '.'); _git(root, 'commit', '-m', 'Docs')
    handoff.assert_current_base(base, _git(root, 'rev-parse', 'HEAD'))
    path = root/'src/white_list_archive/publishing/new.py'; path.parent.mkdir(parents=True); path.write_text('changed')
    _git(root, 'add', '.'); _git(root, 'commit', '-m', 'Changed publication code')
    with pytest.raises(ValueError, match='approval inputs'):
        handoff.assert_current_base(base, _git(root, 'rev-parse', 'HEAD'))


def test_handoff_stays_in_existing_main_preserver_with_unchanged_permissions():
    root = Path(__file__).resolve().parents[1]
    workflow = (root/'.github/workflows/public-registry-review.yml').read_text()
    preserve = workflow.split('\n  preserve:', 1)[1].split('\n  catania-source-only:', 1)[0]
    assert "if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'" in preserve
    assert 'contents: write\n      actions: read' in preserve
    assert 'pull-requests: write' not in preserve
    assert '--write-branch' in preserve
    assert 'gh release upload' in preserve
    assert '--force' not in preserve and 'deploy-pages' not in workflow
    assert 'actions/deploy-pages@v4' in (root/'.github/workflows/public-pages.yml').read_text()


def test_metadata_preserver_does_not_require_a_parser_runtime():
    from white_list_archive.publishing.frozen_release import configuration_sha256
    value = {'unicode': 'à', 'sources': ['first', {'sha256': 'a'*64}]}
    assert handoff._digest(value) == configuration_sha256(value)
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, '-S', '-c', 'import white_list_archive.publishing.publication_handoff'],
                   cwd=root, env={**os.environ, 'PYTHONPATH': str(root/'src')}, check=True)
