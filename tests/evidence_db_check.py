"""Real SQL/constraints, synthetic object transport. Rolled back; no durability claim."""
import hashlib
import io
import os
from unittest.mock import Mock

import psycopg
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig

payload = b'CI synthetic source evidence; not a Prefecture document'
manifest = {'sha256': hashlib.sha256(payload).hexdigest(), 'byte_size': len(payload), 'content_type': 'application/pdf'}
client = Mock()
client.get_object.side_effect = lambda **kw: {'Body': io.BytesIO(payload)}
store = EvidenceStore(client, StoreConfig('ci-evidence', 'https://ci.invalid', 'eu-west-1', 'synthetic policy'))
with psycopg.connect(os.environ['TEST_DSN']) as conn:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO source.content_object(sha256,mime_type,file_size,storage_uri) VALUES (%s,%s,%s,'artifact:fixture') RETURNING content_object_id", (manifest['sha256'],manifest['content_type'],manifest['byte_size']))
        identity = cur.fetchone()[0]
    store.promote(conn, manifest)
    store.promote(conn, manifest)
    with conn.cursor() as cur:
        cur.execute('SELECT content_object_id, storage_status_code, storage_uri FROM source.content_object WHERE sha256=%s', (manifest['sha256'],))
        row = cur.fetchone()
        assert row[0] == identity and row[1] == 'durable' and row[2].startswith('https://ci.invalid/ci-evidence/sha256/')
    conn.rollback()
print('PostgreSQL evidence promotion/idempotence passed with synthetic transport; transaction rolled back.')
