from copy import deepcopy
import gzip
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from white_list_archive.storage.inventory_cycle import (
    SHARDS, denominator_sha, expected_for_shard, merge_inventory_shards,
    robot_shard, row_identity, shard_key, validate_context, validate_inventory_rows,
)
from white_list_archive.storage.inventory_report import (
    persist_private_inventory_document, read_private_inventory_document,
)


def fixture():
    expected = {}
    for i in range(12):
        row = {'identity_kind': 'capture', 'authority_key': 'alpha',
               'source_key': 'alpha-listed', 'capture_id': f'capture-{i}',
               'sha256': f'{i:064x}', 'byte_size': 10,
               'scope': 'shared' if i == 0 else robot_shard(
                   {'source_key': 'alpha-listed', 'capture_id': f'capture-{i}'})}
        expected[row_identity(row)] = row
    row = {'identity_kind': 'known_version', 'authority_key': 'beta', 'source_key': None,
           'evidence_version_key': 'legacy', 'sha256': 'a'*64, 'byte_size': None,
           'scope': 'shared'}
    expected[row_identity(row)] = row
    context = {'schema_version': 1, 'code_revision': 'a'*40, 'robot_state_sha': 'b'*40,
               'generated_at': '2026-11-08T04:00:00Z', 'run_key': '123-1', 'shards': SHARDS,
               'denominator_items': len(expected), 'denominator_sha256': denominator_sha(expected)}
    documents = []
    for shard in range(SHARDS):
        rows = []
        for target in expected_for_shard(expected, shard).values():
            row = {k: v for k, v in target.items() if k != 'scope'}
            capture = row['identity_kind'] == 'capture'
            row.update(status='verified' if capture else 'not_verified',
                       durable_original_verified=True,
                       capture_provenance_verified=capture,
                       evidence_refs=['positive-evidence'])
            rows.append(row)
        inventory = {'schema_version': 1, 'generated_at': context['generated_at'],
                     'recovery_search_complete': False, 'items': rows,
                     'published_release_scopes': [],
                     'metrics': {'denominator_items': len(rows)}}
        documents.append({'schema_version': 1, 'report_kind': 'national_recovery_inventory_shard',
                          'context': deepcopy(context), 'shard': shard, 'inventory': inventory,
                          'complete_denominator': False, 'shard_complete': True})
    return expected, context, documents


def test_deterministic_sharding_covers_exact_full_denominator_and_deduplicates_shared_controls():
    expected, context, documents = fixture()
    assert {robot_shard({'source_key': 'alpha-listed', 'capture_id': f'capture-{i}'})
            for i in range(12)} == set(range(SHARDS))
    result = merge_inventory_shards(list(reversed(documents)), context, expected)
    assert result['metrics']['denominator_items'] == len(expected)
    assert result['metrics']['captures_expected'] == 12
    assert result['metrics']['known_versions_without_capture_identity'] == 1
    assert result['metrics']['verified'] == 12
    assert result['metrics']['not_verified'] == 1
    assert len({row_identity(row) for row in result['items']}) == len(expected)
    assert result['recovery_search_complete'] is False
    assert result == merge_inventory_shards(documents, context, expected)


@pytest.mark.parametrize('mutation', ['missing_shard', 'duplicate_shard', 'missing_row', 'extra_row',
                                     'duplicate_row', 'unverified_capture', 'wrong_hash',
                                     'stale_run', 'wrong_code', 'wrong_robot', 'wrong_time',
                                     'wrong_denominator', 'false_completion', 'shared_disagreement'])
def test_incomplete_foreign_or_inconsistent_shards_never_produce_full_inventory(mutation):
    expected, context, docs = fixture()
    if mutation == 'missing_shard':
        docs.pop()
    elif mutation == 'duplicate_shard':
        docs[-1] = deepcopy(docs[0])
    elif mutation == 'missing_row':
        docs[0]['inventory']['items'].pop()
        docs[0]['inventory']['metrics']['denominator_items'] -= 1
    elif mutation in ('extra_row', 'duplicate_row'):
        row = deepcopy(docs[0]['inventory']['items'][0])
        if mutation == 'extra_row':
            row['capture_id'] = 'unexpected'
        docs[0]['inventory']['items'].append(row)
        docs[0]['inventory']['metrics']['denominator_items'] += 1
    elif mutation == 'unverified_capture':
        docs[0]['inventory']['items'][0]['capture_provenance_verified'] = False
    elif mutation == 'wrong_hash':
        docs[0]['inventory']['items'][0]['sha256'] = 'f'*64
    elif mutation == 'stale_run':
        docs[0]['context']['run_key'] = '122-1'
    elif mutation == 'wrong_code':
        docs[0]['context']['code_revision'] = 'c'*40
    elif mutation == 'wrong_robot':
        docs[0]['context']['robot_state_sha'] = 'c'*40
    elif mutation == 'wrong_time':
        docs[0]['inventory']['generated_at'] = '2026-11-07T04:00:00Z'
    elif mutation == 'wrong_denominator':
        context['denominator_sha256'] = 'e'*64
    elif mutation == 'false_completion':
        docs[0]['complete_denominator'] = True
    elif mutation == 'shared_disagreement':
        docs[0]['inventory']['items'][0]['evidence_refs'] = ['different-review-evidence']
    with pytest.raises((ValueError, KeyError)):
        merge_inventory_shards(docs, context, expected)


def test_complete_denominator_hash_binds_authority_and_original_byte_expectations():
    expected, context, _ = fixture()
    validate_context(context, expected)
    changed = deepcopy(expected)
    next(iter(changed.values()))['authority_key'] = 'another'
    with pytest.raises(ValueError, match='complete frozen denominator'):
        validate_context(context, changed)
    with pytest.raises(ValueError, match='Invalid inventory shard'):
        expected_for_shard(expected, 4)


class Client:
    def __init__(self):
        self.objects = {}
    def put_object(self, **kw):
        assert kw['IfNoneMatch'] == '*'
        if kw['Key'] in self.objects:
            raise RuntimeError('already exists')
        self.objects[kw['Key']] = kw['Body']
    def get_object(self, **kw):
        return {'Body': BytesIO(self.objects[kw['Key']])}


def test_private_checkpoints_are_create_only_bounded_read_back_and_attempt_scoped():
    expected, context, documents = fixture()
    client = Client()
    store = SimpleNamespace(client=client, config=SimpleNamespace(bucket='private'))
    for doc in documents:
        key = shard_key(context, doc['shard'])
        persist_private_inventory_document(store, doc, key=key)
        assert read_private_inventory_document(store, key=key) == doc
        with pytest.raises(RuntimeError, match='persistence/readback failed'):
            persist_private_inventory_document(store, doc, key=key)
    assert merge_inventory_shards([read_private_inventory_document(store, key=shard_key(context, i))
                                   for i in range(4)], context, expected)['metrics']['denominator_items'] == 13
    new_attempt = {**context, 'run_key': '123-2'}
    with pytest.raises(RuntimeError, match='could not be verified'):
        read_private_inventory_document(store, key=shard_key(new_attempt, 0))
    key = shard_key(context, 0)
    client.objects[key] = b'corrupt-gzip'
    with pytest.raises(RuntimeError, match='could not be verified'):
        read_private_inventory_document(store, key=key)
    with pytest.raises(ValueError, match='Invalid private inventory shard key'):
        read_private_inventory_document(store, key='foreign/key')


def test_workflow_freezes_scope_and_requires_all_bounded_private_shards_before_reduction():
    text = Path('.github/workflows/lane-a-recovery-inventory-proof.yml').read_text()
    assert 'max-parallel: 2' in text
    assert 'shard: [0, 1, 2, 3]' in text
    assert 'needs: [freeze-denominator, verify-recovery-shard]' in text
    assert 'denominator_sha256: ${{ steps.freeze.outputs.denominator_sha256 }}' in text
    assert 'ROBOT_HEAD: ${{ needs.freeze-denominator.outputs.robot_state_sha }}' in text
    assert 'cancel-in-progress: false' in text
    assert 'upload-artifact@' not in text
    assert 'environment: evidence-archive' in text


def test_four_shards_rehydrate_real_catalogue_objects_and_reduce_real_materialiser_results(tmp_path, monkeypatch):
    import csv
    from datetime import datetime, timezone
    from test_archive_inventory import store
    from white_list_archive.acquisition.archive_first import archive_payload
    import white_list_archive.storage.inventory_cycle as module
    import white_list_archive.storage.recovery_materialize as materialise
    import white_list_archive.storage.recovery_migration as migration

    evidence = store()
    root = tmp_path / 'repository'
    registry = root / 'data/source_registry/source_series_inventory.csv'
    registry.parent.mkdir(parents=True)
    registry.write_text('source_series_key,authority_key\npotenza-combined,potenza\naosta-listed,aosta\ncosenza-combined,cosenza\n')
    archived = {}
    for i, (source, cid, authority) in enumerate(module.CONTROLS):
        archived[cid] = archive_payload(data=f'original-{i}'.encode(), source_key=source,
            resource_url=f'https://prefettura.example/{source}/{i}.pdf',
            reference_date=None, content_type='application/pdf', store=evidence,
            work_dir=tmp_path/f'capture-{i}', capture_id=cid,
            captured_at=datetime(2026, 11, 7, tzinfo=timezone.utc), http_status=200)
    known = []
    for path, (_, cid, _) in zip(module.LEGACY_PATHS, module.CONTROLS[2:]):
        original = archived[cid].manifest
        legacy = {**original, 'final_url': original['resolved_url']}
        destination = root/path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(legacy))
        known.append({'authority_key': 'cosenza', 'source_key': 'cosenza-combined',
            'evidence_version_key': 'legacy-manifest:'+path, 'sha256': original['sha256'],
            'byte_size': original['byte_size'], 'evidence_refs': [path], 'recovery_paths': [],
            'durable_absence_confirmed': False})
    known.append({'authority_key': 'missing-history', 'source_key': None,
        'evidence_version_key': 'positive-historical-hash', 'sha256': 'f'*64,
        'byte_size': None, 'evidence_refs': ['reviewed historical hash evidence'],
        'recovery_paths': [], 'durable_absence_confirmed': False})
    def expectations(**kwargs):
        return {'schema_version': 1, 'generated_at': kwargs['generated_at'],
                'recovery_search_complete': False, 'captures': [],
                'known_versions': deepcopy(known), 'published_release_scopes': []}
    for target in (module, materialise, migration):
        monkeypatch.setattr(target, 'build_repository_recovery_expectations', expectations)
    references = []
    for i in range(8):
        cid = f'{i:08d}-4444-4444-8444-444444444444'
        source = 'potenza-combined'
        result = archive_payload(data=f'robot-{i}'.encode(), source_key=source,
            resource_url=f'https://prefettura.example/robot-{i}.pdf',
            reference_date=None, content_type='application/pdf', store=evidence,
            work_dir=tmp_path/f'robot-{i}', capture_id=cid,
            captured_at=datetime(2026, 11, 7, tzinfo=timezone.utc), http_status=200)
        references.append({'source_key': source, 'capture_id': cid, 'authority_key': 'potenza',
            'resource_url': result.manifest['resource_url'],
            'expected': {key: result.manifest[key] for key in ('sha256', 'byte_size', 'captured_at')},
            'evidence_refs': ['git:robot-state:'+'b'*40+':state.json#potenza']})
    monkeypatch.setattr(module, 'read_robot_history', lambda *a: ([], {'robot_state_sha': 'b'*40}))
    monkeypatch.setattr(module, 'collect_robot_capture_references', lambda *a: (references, {}))
    expected = module.expected_denominator(root, references)
    context = {'schema_version': 1, 'code_revision': 'a'*40, 'robot_state_sha': 'b'*40,
               'generated_at': '2026-11-08T04:00:00Z', 'run_key': '123-1', 'shards': SHARDS,
               'denominator_items': len(expected), 'denominator_sha256': denominator_sha(expected)}
    for shard in range(4):
        document = module.run_shard(root, evidence, context, shard)
        assert document['complete_denominator'] is False
    documents = [read_private_inventory_document(evidence, key=shard_key(context, i)) for i in range(4)]
    complete = merge_inventory_shards(documents, context, expected)
    assert complete['metrics']['denominator_items'] == 13
    assert complete['metrics']['verified'] == 12  # 8 robot captures + 4 controls
    assert complete['metrics']['not_verified'] == 1
    assert complete['metrics']['missing'] == 0
