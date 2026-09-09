from copy import deepcopy
import hashlib
import io
from pathlib import Path
from unittest.mock import Mock

import pytest

from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, object_key

CONFIG = StoreConfig('private-evidence', 'https://storage.example.invalid', 'eu-west-1', 'reviewed-policy-fixture')
DATA = b'%PDF-synthetic-evidence-test'
MANIFEST = {'sha256': hashlib.sha256(DATA).hexdigest(), 'byte_size': len(DATA),
            'content_type': 'application/pdf', 'resource_url': 'https://official.example.invalid/source.pdf',
            'captured_at': '2026-09-06T12:00:00Z', 'reference_date': '2026-08-03'}


class Conflict(Exception):
    response = {'Error': {'Code': 'PreconditionFailed'}}


class LockedConflict(Exception):
    response = {'Error': {'Code': 'ObjectLockedByBucketPolicy'}}


class MemoryS3:
    """Protocol double; never evidence of production storage readiness."""
    def __init__(self):
        self.objects, self.writes = {}, 0
        self.corrupt_read = False

    def put_object(self, **kwargs):
        assert kwargs['IfNoneMatch'] == '*'
        k = kwargs['Key']
        if k in self.objects:
            raise Conflict()
        self.objects[k] = kwargs['Body']
        self.writes += 1

    def get_object(self, **kwargs):
        value = self.objects[kwargs['Key']]
        return {'Body': io.BytesIO(b'corrupt' if self.corrupt_read else value)}


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'evidence.pdf'
    path.write_bytes(DATA)
    return path


def test_idempotent_upload_retrieval_and_unchanged_manifest(source):
    client = MemoryS3()
    store = EvidenceStore(client, CONFIG)
    manifest = deepcopy(MANIFEST)
    first, second = store.archive(source, manifest), store.archive(source, manifest)
    assert first['created'] and not second['created']
    assert client.writes == 1
    assert store.read_verified(manifest) == DATA
    assert first['storage_uri'].startswith(CONFIG.endpoint + '/' + CONFIG.bucket + '/sha256/')
    assert first['database_promoted'] is False
    assert manifest == MANIFEST


def test_r2_bucket_lock_existing_object_signal_requires_full_verification(source):
    client = MemoryS3(); store = EvidenceStore(client, CONFIG)
    first = store.archive(source, MANIFEST)
    assert first['created'] and client.writes == 1
    client.put_object = Mock(side_effect=LockedConflict())
    second = store.archive(source, MANIFEST)
    assert not second['created']
    key = object_key(MANIFEST)
    client.objects[key] = b'wrong'
    with pytest.raises(ValueError, match='Stored evidence'):
        store.archive(source, MANIFEST)


def test_changed_bytes_get_new_identity_without_replacing_history(source):
    client = MemoryS3(); store = EvidenceStore(client, CONFIG)
    store.archive(source, MANIFEST)
    data = DATA + b'new edition'
    source.write_bytes(data)
    updated = {**MANIFEST, 'sha256': hashlib.sha256(data).hexdigest(), 'byte_size': len(data)}
    store.archive(source, updated)
    assert len(client.objects) == 2
    assert store.read_verified(MANIFEST) == DATA


def test_local_hash_mismatch_never_uploads(source):
    client = MemoryS3()
    source.write_bytes(b'wrong')
    with pytest.raises(ValueError, match='Local evidence'):
        EvidenceStore(client, CONFIG).archive(source, MANIFEST)
    assert not client.objects


def test_conflicting_existing_object_is_not_overwritten(source):
    client = MemoryS3(); key = object_key(MANIFEST)
    client.objects[key] = b'wrong'
    with pytest.raises(ValueError, match='Stored evidence'):
        EvidenceStore(client, CONFIG).archive(source, MANIFEST)
    assert client.objects[key] == b'wrong' and client.writes == 0


def test_upload_errors_missing_objects_and_corrupt_retrieval_fail(source):
    client = MemoryS3(); store = EvidenceStore(client, CONFIG)
    with pytest.raises(KeyError):
        store.read_verified(MANIFEST)
    client.put_object = Mock(side_effect=PermissionError('denied'))
    with pytest.raises(PermissionError):
        store.archive(source, MANIFEST)
    client = MemoryS3(); client.corrupt_read = True
    with pytest.raises(ValueError, match='Stored evidence'):
        EvidenceStore(client, CONFIG).archive(source, MANIFEST)


def test_promotion_rechecks_bytes_and_rejects_missing_or_conflicting_db_objects(source):
    client = MemoryS3(); store = EvidenceStore(client, CONFIG)
    receipt = store.archive(source, MANIFEST)
    cur = Mock(); conn = Mock(); conn.cursor.return_value.__enter__ = Mock(return_value=cur)
    conn.cursor.return_value.__exit__ = Mock(return_value=False)
    good = ('id', len(DATA), 'application/pdf', 'artifact:old', 'ephemeral')
    for row in [None, ('id', 0, 'application/pdf', '', 'ephemeral'), ('id', len(DATA), 'application/pdf', 'https://another', 'durable')]:
        cur.fetchone.return_value = row
        with pytest.raises(ValueError):
            store.promote(conn, MANIFEST)
    cur.fetchone.return_value = good
    client.corrupt_read = True
    before = cur.execute.call_count
    with pytest.raises(ValueError):
        store.promote(conn, MANIFEST)
    assert cur.execute.call_count == before + 1  # SELECT only; no UPDATE.
    client.corrupt_read = False
    store.promote(conn, MANIFEST)
    assert cur.execute.call_args.args[1] == (receipt['storage_uri'], 'id')


@pytest.mark.parametrize('endpoint', ['http://storage.invalid', 'https://user:secret@storage.invalid', 'https://storage.invalid/?token=x'])
def test_insecure_or_credential_bearing_endpoint_rejected(endpoint):
    with pytest.raises(ValueError):
        StoreConfig('private-evidence', endpoint, 'region', 'policy')


def test_boto3_adapter_uses_conditional_put_and_full_get(source):
    import boto3
    from botocore.stub import Stubber
    client = boto3.client('s3', region_name='eu-west-1', aws_access_key_id='fixture', aws_secret_access_key='fixture')
    with Stubber(client) as stub:
        stub.add_response('put_object', {}, {'Bucket': CONFIG.bucket, 'Key': object_key(MANIFEST),
            'Body': DATA, 'ContentType': 'application/pdf', 'IfNoneMatch': '*', 'Metadata': {'sha256': MANIFEST['sha256']}})
        stub.add_response('get_object', {'Body': io.BytesIO(DATA)}, {'Bucket': CONFIG.bucket, 'Key': object_key(MANIFEST)})
        EvidenceStore(client, CONFIG).archive(source, MANIFEST)
        stub.assert_no_pending_responses()
