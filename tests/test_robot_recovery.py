from copy import deepcopy
from datetime import datetime, timezone
import json
import subprocess

import pytest

from test_archive_first_replay import store
from white_list_archive.acquisition.archive_first import archive_payload
from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.robot_recovery import (
    collect_robot_capture_references, read_robot_history, rehydrate_robot_captures,
)

URL = 'https://prefettura.example/elenco.pdf'
CID = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'
AUTHORITIES = {'alpha-listed': 'alpha'}


def state(cid=CID, digest='a' * 64, source='alpha-listed'):
    return {'schema_version': 1, 'robots': {'alpha': {
        'authority_key': 'alpha', 'resources': {URL: {
            'source_keys': [source], 'capture_ids': [cid], 'archived_sha256': digest,
        }},
    }}}


def test_all_retained_revisions_keep_overwritten_ids_and_deduplicate_unchanged_ids():
    first, second = state(), state(OTHER, 'b' * 64)
    refs, metrics = collect_robot_capture_references(
        [('1' * 40, first), ('2' * 40, second), ('3' * 40, second)], AUTHORITIES,
    )
    assert [r['capture_id'] for r in refs] == [CID, OTHER]
    assert len(refs[1]['evidence_refs']) == 2
    assert metrics['reviewed_robot_capture_references'] == 2
    assert metrics['reviewed_robot_source_series'] == 1
    assert 'captured_at' not in refs[0]['expected']


def test_new_history_and_legacy_snapshot_agree_without_inventing_time():
    first = state()
    second = deepcopy(first)
    second['robots']['alpha']['resources'][URL]['capture_history'] = [{
        'capture_id': CID, 'source_key': 'alpha-listed', 'sha256': 'a' * 64,
        'captured_at': None,
    }, {'capture_id': OTHER, 'source_key': 'alpha-listed', 'sha256': 'b' * 64,
        'captured_at': '2026-09-29T03:00:00+00:00'}]
    refs, _ = collect_robot_capture_references([('1' * 40, first), ('2' * 40, second)], AUTHORITIES)
    assert 'captured_at' not in refs[0]['expected']
    assert refs[1]['expected']['captured_at'] == '2026-09-29T03:00:00+00:00'


def test_discovery_and_unbound_ids_do_not_become_reviewed_source_series():
    ambiguous = state()
    ambiguous['robots']['alpha']['resources'][URL]['source_keys'] = ['alpha-listed', 'another']
    refs, metrics = collect_robot_capture_references([
        ('1' * 40, state(source='alpha-robot-discovery')),
        ('2' * 40, ambiguous),
    ], AUTHORITIES)
    assert refs == []
    assert metrics['discovery_capture_references_excluded'] == 1
    assert metrics['unbound_capture_references_excluded'] == 1


def test_conflicting_ownership_or_capture_metadata_fails_closed():
    with pytest.raises(ValueError, match='ownership'):
        collect_robot_capture_references([('1' * 40, state())], {'alpha-listed': 'beta'})
    with pytest.raises(ValueError, match='conflicting historical metadata'):
        collect_robot_capture_references([('1' * 40, state()), ('2' * 40, state(digest='b' * 64))], AUTHORITIES)


def test_catalogue_rehydration_is_read_only_and_preserves_evidenced_capture_time(tmp_path):
    evidence = store()
    archived = archive_payload(data=b'exact source bytes', source_key='alpha-listed',
        resource_url=URL, reference_date=None, content_type='application/pdf',
        store=evidence, work_dir=tmp_path, capture_id=CID,
        captured_at=datetime(2026, 9, 27, 1, 2, tzinfo=timezone.utc))
    refs, _ = collect_robot_capture_references([('1' * 40, state(digest=archived.sha256))], AUTHORITIES)
    before = deepcopy(evidence.client.objects)
    rows = rehydrate_robot_captures(refs, CaptureCatalogue(evidence))
    assert evidence.client.objects == before
    assert rows[0]['capture'] == archived.manifest
    assert rows[0]['capture']['captured_at'] == '2026-09-27T01:02:00+00:00'
    assert rows[0]['capture']['reference_date'] is None
    assert rows[0]['durable_absence_confirmed'] is False
    assert rows[0]['operator_evidence_refs'] == refs[0]['evidence_refs']
    refs[0]['expected']['sha256'] = 'f' * 64
    with pytest.raises(ValueError, match='Robot capture not verified'):
        rehydrate_robot_captures(refs, CaptureCatalogue(evidence))


def test_provider_failure_is_not_missing_and_does_not_leak_coordinates(monkeypatch):
    evidence = store()
    def broken(**kwargs):
        raise RuntimeError('https://private-provider.example/secret-namespace')
    monkeypatch.setattr(evidence.client, 'get_object', broken)
    refs, _ = collect_robot_capture_references([('1' * 40, state())], AUTHORITIES)
    with pytest.raises(ValueError) as failure:
        rehydrate_robot_captures(refs, CaptureCatalogue(evidence))
    assert str(failure.value) == 'Robot capture not verified: alpha-listed/' + CID


def test_git_history_pins_head_and_rejects_incomplete_history(tmp_path):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(tmp_path), *args], text=True).strip()
    git('init', '-q')
    heads = []
    for cid in [CID, OTHER]:
        (tmp_path / 'state.json').write_text(json.dumps(state(cid)))
        git('add', 'state.json')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test', 'commit', '-qm', 'state')
        heads.append(git('rev-parse', 'HEAD'))
    snapshots, metrics = read_robot_history(tmp_path, heads[0])
    assert metrics == {'robot_state_sha': heads[0], 'robot_state_revisions': 1}
    assert len(snapshots) == 1
    (tmp_path / '.git/shallow').write_text(heads[0] + '\n')
    with pytest.raises(ValueError, match='shallow'):
        read_robot_history(tmp_path, heads[1])
