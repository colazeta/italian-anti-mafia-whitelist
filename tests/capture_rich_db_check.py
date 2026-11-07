"""Real ephemeral PostgreSQL acceptance for capture-only rich source persistence."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import os
from uuid import uuid4

import psycopg

from test_capture_rich_cosenza import synthetic_record
from white_list_archive.persistence.capture_rich_cosenza import persist_capture_records, verify_rich_readback

DSN = os.environ['TEST_DSN']
capture_id = str(uuid4())
raw_bytes = b'CI synthetic capture-only rich source bytes'
source_sha = hashlib.sha256(raw_bytes).hexdigest()
now = datetime.now(timezone.utc)
records = [synthetic_record()]
common = dict(capture_id=capture_id,source_sha256=source_sha,records=records,
              code_revision='1'*40,started_at=now,completed_at=now,expected_count=1)
protected = ('source.source_edition','source.capture_edition','semantic.projection_run',
             'semantic.entity_observation','core.legal_entity','whitelist.white_list_relationship')


def protected_counts(conn):
    with conn.cursor() as cur:
        result = {}
        for table in protected:
            cur.execute('SELECT count(*) FROM ' + table)
            result[table] = cur.fetchone()[0]
        return result


def run_counts(conn, run_id):
    with conn.cursor() as cur:
        cur.execute('''SELECT
            (SELECT count(*) FROM source.parsed_record WHERE parse_run_id=%s),
            (SELECT count(*) FROM source.source_field_value v JOIN source.parsed_record r USING(parsed_record_id)
             WHERE r.parse_run_id=%s),
            (SELECT count(*) FROM source.entity_mention m JOIN source.parsed_record r USING(parsed_record_id)
             WHERE r.parse_run_id=%s)''',(run_id,run_id,run_id))
        return cur.fetchone()


with psycopg.connect(DSN) as conn:
    baseline = protected_counts(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT series_id FROM source.source_series WHERE series_code='cosenza-combined'")
        row = cur.fetchone()
        if row:
            series_id = row[0]
        else:
            cur.execute("INSERT INTO source.source_series(series_code,series_name,series_type_code) "
                        "VALUES ('cosenza-combined','CI Cosenza series','list') RETURNING series_id")
            series_id = cur.fetchone()[0]
        cur.execute("INSERT INTO source.source_resource(canonical_locator,resource_type_code) "
                    "VALUES (%s,'pdf') RETURNING resource_id",('https://ci.invalid/'+capture_id,))
        resource_id = cur.fetchone()[0]
        cur.execute("INSERT INTO source.content_object(sha256,mime_type,file_size,storage_uri,storage_status_code) "
                    "VALUES (%s,'application/pdf',%s,'https://ci.invalid/immutable','durable') "
                    "RETURNING content_object_id",(source_sha,len(raw_bytes)))
        content_id = cur.fetchone()[0]
        cur.execute("INSERT INTO source.source_capture(capture_id,series_id,resource_id,content_object_id," 
                    "captured_at,http_status,origin_type_code,authority_rank_code,resolved_url) "
                    "VALUES (%s,%s,%s,%s,%s,200,'official_current','primary_official','https://ci.invalid/final')",
                    (capture_id,series_id,resource_id,content_id,now-timedelta(days=10)))
        cur.execute('SELECT row_to_json(c) FROM source.source_capture c WHERE capture_id=%s',(capture_id,))
        original_capture = cur.fetchone()[0]
    with conn.cursor() as cur:
        cur.execute('''SELECT first_observed_at,last_observed_at FROM source.source_schema_version v
            JOIN source.source_schema s ON s.source_schema_id=v.source_schema_id
            WHERE s.series_id=%s AND v.structural_fingerprint=%s''',
            (series_id,'fbb124c5a43d26bef93316844b3021096060f7ed9d2cc0f8f6081f6df935dc97'))
        previous_schema_times = cur.fetchone()
    result = persist_capture_records(conn,**common)
    repeat = persist_capture_records(conn,**dict(common,started_at=now+timedelta(seconds=3),
                                                completed_at=now+timedelta(seconds=3)))
    assert result['parse_run_id'] == repeat['parse_run_id']
    assert not result['parse_run_reused'] and repeat['parse_run_reused']
    assert repeat['snapshot_reused'] and repeat['capture_link_reused']
    assert run_counts(conn,result['parse_run_id']) == (1,7,1)
    assert protected_counts(conn) == baseline
    with conn.cursor() as cur:
        cur.execute('SELECT row_to_json(c) FROM source.source_capture c WHERE capture_id=%s',(capture_id,))
        assert cur.fetchone()[0] == original_capture
        cur.execute('''SELECT first_observed_at,last_observed_at FROM source.source_schema_version v
            JOIN source.source_schema s ON s.source_schema_id=v.source_schema_id
            WHERE s.series_id=%s AND v.structural_fingerprint=%s''',
            (series_id,'fbb124c5a43d26bef93316844b3021096060f7ed9d2cc0f8f6081f6df935dc97'))
        observed = cur.fetchone()
        assert observed == (previous_schema_times or (now,None))
    conn.commit()

pins = dict(capture_id=capture_id,parse_run_id=result['parse_run_id'],source_sha256=source_sha,
            expected_count=1,expected_snapshot_sha256=result['snapshot_sha256'],code_revision='1'*40)
with psycopg.connect(DSN) as conn:
    independently_verified = verify_rich_readback(conn,**pins)
    assert independently_verified['rich_readback_verified']
    assert run_counts(conn,result['parse_run_id']) == (1,7,1)
    # Same run identity cannot accept altered output even when its new raw hash is valid.
    changed = deepcopy(records)
    changed[0]['registered_office_raw'] = 'Altered synthetic field'
    try:
        with conn.transaction():
            persist_capture_records(conn,**dict(common,records=changed))
    except ValueError as exc:
        assert 'immutable interpretation output' in str(exc)
    else:
        raise AssertionError('One interpretation identity accepted conflicting source rows')
    # Full field readback catches an unexpected extra physical field location.
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute('''INSERT INTO source.source_field_value(parsed_record_id,field_definition_id,
                    schema_version_id,raw_value,parsed_value_json,structural_locator)
                    SELECT v.parsed_record_id,v.field_definition_id,v.schema_version_id,
                           v.raw_value,v.parsed_value_json,'ci-extra-field'
                    FROM source.source_field_value v JOIN source.parsed_record r USING(parsed_record_id)
                    WHERE r.parse_run_id=%s LIMIT 1''',(result['parse_run_id'],))
            verify_rich_readback(conn,**pins)
    except ValueError as exc:
        assert 'field values/definitions' in str(exc)
    else:
        raise AssertionError('Unexpected source field was hidden during readback')
    verify_rich_readback(conn,**pins)
    assert run_counts(conn,result['parse_run_id']) == (1,7,1)
    assert protected_counts(conn) == baseline
    with conn.cursor() as cur:
        cur.execute('SELECT row_to_json(c) FROM source.source_capture c WHERE capture_id=%s',(capture_id,))
        assert cur.fetchone()[0] == original_capture
print('Capture-only rich persistence: repeated input, independent full readback and protected boundaries verified')
