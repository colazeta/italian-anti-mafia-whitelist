"""Real SQL/constraints, synthetic object transport. Rolled back; no durability claim."""
from datetime import datetime, timezone
import hashlib
import io
import os
from pathlib import Path
import tempfile
from unittest.mock import Mock

import psycopg

from white_list_archive.acquisition.archive_first import archive_payload
from white_list_archive.persistence.archived_capture import persist_archived_capture
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, object_key


# Preserve the existing ContentObject promotion regression.
payload = b'CI synthetic source evidence; not a Prefecture document'
manifest = {
    'sha256': hashlib.sha256(payload).hexdigest(),
    'byte_size': len(payload),
    'content_type': 'application/pdf',
}
client = Mock()
client.get_object.side_effect = lambda **kw: {'Body': io.BytesIO(payload)}
store = EvidenceStore(
    client,
    StoreConfig('ci-evidence', 'https://ci.invalid', 'eu-west-1', 'synthetic policy'),
)
with psycopg.connect(os.environ['TEST_DSN']) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO source.content_object(sha256,mime_type,file_size,storage_uri) "
            "VALUES (%s,%s,%s,'artifact:fixture') RETURNING content_object_id",
            (manifest['sha256'], manifest['content_type'], manifest['byte_size']),
        )
        identity = cur.fetchone()[0]
    store.promote(conn, manifest)
    store.promote(conn, manifest)
    with conn.cursor() as cur:
        cur.execute(
            'SELECT content_object_id, storage_status_code, storage_uri '
            'FROM source.content_object WHERE sha256=%s',
            (manifest['sha256'],),
        )
        row = cur.fetchone()
        assert row[0] == identity and row[1] == 'durable'
        assert row[2].startswith('https://ci.invalid/ci-evidence/sha256/')
    conn.rollback()
print('PostgreSQL evidence promotion/idempotence passed with synthetic transport; transaction rolled back.')


class ExistingObject(Exception):
    def __init__(self):
        self.response = {'Error': {'Code': 'PreconditionFailed'}}


class MemoryClient:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        assert Bucket == 'ci-evidence'
        if Key in self.objects:
            raise ExistingObject()
        self.objects[Key] = bytes(Body)
        return {}

    def get_object(self, *, Bucket, Key):
        assert Bucket == 'ci-evidence'
        if Key not in self.objects:
            raise KeyError(Key)
        return {'Body': io.BytesIO(self.objects[Key])}


# Exercise the complete archive-first -> private readback -> relational provenance path
# with real PostgreSQL constraints. The object transport is deliberately synthetic;
# this does not replace the separately required real-provider gate.
archive_client = MemoryClient()
archive_store = EvidenceStore(
    archive_client,
    StoreConfig('ci-evidence', 'https://ci.invalid', 'eu-west-1', 'synthetic policy'),
)
with tempfile.TemporaryDirectory() as tmp, psycopg.connect(os.environ['TEST_DSN']) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO source.source_series(series_code, series_name, series_type_code)
            VALUES ('ci-archive-first','CI archive-first synthetic series','list')
            RETURNING series_id
            """
        )
        series_id = cur.fetchone()[0]

    archived = archive_payload(
        data=b'archive-first bytes persisted only in synthetic CI transport',
        source_key='ci-archive-first',
        resource_url='https://official.example.test/current.pdf',
        reference_date=None,
        content_type='application/pdf',
        store=archive_store,
        work_dir=Path(tmp),
        captured_at=datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc),
        capture_id='11111111-2222-4333-8444-555555555555',
        http_status=200,
        origin_type='official_current',
        authority_rank_code='primary_official',
        resource_type_code='pdf',
    )
    first = persist_archived_capture(conn, archived, archive_store)
    second = persist_archived_capture(conn, archived, archive_store)
    assert first == second

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.capture_id, c.series_id, c.declared_reference_date,
                   c.origin_type_code, c.authority_rank_code,
                   o.storage_status_code, o.storage_uri, o.sha256
            FROM source.source_capture c
            JOIN source.content_object o ON o.content_object_id=c.content_object_id
            WHERE c.capture_id=%s
            """,
            (archived.manifest['capture_id'],),
        )
        row = cur.fetchone()
        assert str(row[0]) == archived.manifest['capture_id']
        assert row[1] == series_id
        assert row[2] is None
        assert row[3:5] == ('official_current', 'primary_official')
        assert row[5] == 'durable'
        assert row[6] == archived.content_receipt['storage_uri']
        assert row[7] == archived.sha256

    corrupted = archive_payload(
        data=b'second independent synthetic capture',
        source_key='ci-archive-first',
        resource_url='https://official.example.test/current.pdf',
        reference_date='2026-09-22',
        content_type='application/pdf',
        store=archive_store,
        work_dir=Path(tmp),
        captured_at=datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc),
        capture_id='66666666-7777-4888-8999-aaaaaaaaaaaa',
        http_status=200,
        origin_type='official_current',
        authority_rank_code='primary_official',
        resource_type_code='pdf',
    )
    archive_client.objects[object_key(corrupted.manifest)] = b'corrupt after archive receipt'
    try:
        persist_archived_capture(conn, corrupted, archive_store)
    except ValueError as exc:
        assert 'Stored evidence failed independent size/SHA-256 verification' in str(exc)
    else:
        raise AssertionError('Corrupted archived bytes were accepted for relational persistence')
    with conn.cursor() as cur:
        cur.execute(
            'SELECT count(*) FROM source.source_capture WHERE capture_id=%s',
            (corrupted.manifest['capture_id'],),
        )
        assert cur.fetchone()[0] == 0

    conn.rollback()
print('Archive-first capture persistence/idempotence/corruption rejection passed against PostgreSQL; transaction rolled back.')
