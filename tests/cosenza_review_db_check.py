"""Disposable PostgreSQL check, after capture_rich_db_check.py; never production.

Real QA, rich records, candidate planning, counts and pins use PostgreSQL.
Only the external archive/catalogue is a synthetic in-memory fixture.
"""
import hashlib
import os
from unittest.mock import patch

import psycopg

from test_cosenza_review import Client
from types import SimpleNamespace
from white_list_archive.normalisation import cosenza_review as review
from white_list_archive.parsers import cosenza_combined_v2 as parser

raw_bytes = b'CI synthetic capture-only rich source bytes'
source_sha = hashlib.sha256(raw_bytes).hexdigest()
source_revision = '1' * 40
protected = ('source.source_edition', 'source.capture_edition', 'semantic.projection_run',
             'semantic.entity_observation', 'core.legal_entity', 'whitelist.white_list_relationship',
             'source.parse_run','source.parse_snapshot','source.parsed_record',
             'source.source_field_value','source.entity_mention')


def counts(conn):
    with conn.cursor() as cur:
        values = {}
        for table in protected:
            cur.execute('SELECT count(*) FROM ' + table)
            values[table] = cur.fetchone()[0]
        return values


with psycopg.connect(os.environ['TEST_DSN']) as conn:
    conn.execute('SET TRANSACTION READ ONLY')
    with conn.cursor() as cur:
        cur.execute('''SELECT c.capture_id,p.parse_run_id,c.captured_at
            FROM source.source_capture c
            JOIN source.content_object o USING(content_object_id)
            JOIN source.capture_parse_run cr USING(capture_id)
            JOIN source.parse_run p USING(parse_run_id)
            JOIN provenance.processing_activity a ON a.processing_activity_id=p.processing_activity_id
            JOIN source.parse_snapshot s USING(parse_run_id)
            WHERE o.sha256=%s AND a.software_name=%s AND a.software_version=%s''',
            (source_sha,parser.PARSER_NAME,f'{parser.PARSER_VERSION}+git.{source_revision}'))
        rows=cur.fetchall()
    assert len(rows)==1, 'Run existing synthetic capture_rich_db_check before this check'
    capture_id,parse_run_id,captured_at=rows[0]
    pins=[dict(capture_id=str(capture_id),parse_run_id=str(parse_run_id),
               source_revision=source_revision,expected_count=1)]
    before=counts(conn)
    store=SimpleNamespace(client=Client(),config=SimpleNamespace(bucket='CI-private-only'),
                          read_verified=lambda manifest:raw_bytes)
    manifest=dict(capture_id=str(capture_id),source_key='cosenza-combined',sha256=source_sha,
                  byte_size=len(raw_bytes),captured_at=captured_at.isoformat())
    def synthetic_catalogue(catalogue, *, source_key,capture_id):
        assert source_key=='cosenza-combined' and capture_id==str(rows[0][0])
        return manifest,{'catalogue_record_sha256':'b'*64}
    with patch.object(review,'load_catalogued_capture',synthetic_catalogue):
        first=review.retain_review(conn,store,inputs=pins,dossier_code_revision='2'*40)
        repeat=review.retain_review(conn,store,inputs=pins,dossier_code_revision='2'*40)
    assert first==repeat and len(store.client.objects)==3
    dossier=review.load_retained_review(store,first['dossier_sha256'])
    assert dossier['versions'][0]['pins']['source_sha256']==source_sha
    assert dossier['versions'][0]['candidate_sha256']
    assert dossier['versions'][0]['qa']['gates']['structural_parser_lineage']['status']=='ready'
    assert first['safe_summary']['versions_verified']==1
    assert first['safe_summary']['administrative_reference_dates_unknown']==1
    assert first['safe_summary']['edition_approvals']==0
    assert first['safe_summary']['semantic_ready'] is False
    assert counts(conn)==before
    conn.rollback()
print('Private review: real PostgreSQL source/QA/candidate pins, deterministic archive receipts and zero database writes verified')
