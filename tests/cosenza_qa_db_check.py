"""Run after capture_rich_db_check.py against the disposable CI PostgreSQL database."""
import os
import psycopg
from white_list_archive.normalisation.cosenza_qa import assess

with psycopg.connect(os.environ['TEST_DSN']) as conn:
    with conn.cursor() as cur:
        cur.execute('''SELECT c.capture_id,p.parse_run_id,s.record_count FROM source.parse_run p
            JOIN provenance.processing_activity a USING(processing_activity_id)
            JOIN source.capture_parse_run c USING(parse_run_id)
            JOIN source.parse_snapshot s USING(parse_run_id)
            WHERE a.software_version=%s AND a.software_name='white_list_archive.parsers.cosenza_combined_v2'
            ORDER BY s.created_at DESC LIMIT 1''',('2+git.'+'1'*40,))
        capture_id,run_id,count = cur.fetchone()
    conn.rollback()
    report = assess(conn,capture_id=str(capture_id),parse_run_id=str(run_id),
                    code_revision='1'*40,expected_count=count)
    assert report['gates']['structural_parser_lineage']['status'] == 'ready'
    assert report['gates']['edition_attribution_review']['status'] == 'blocked'
    assert not report['semantic_ready'] and not report['publication_ready']
    with conn.cursor() as cur:
        cur.execute('SHOW transaction_read_only')
        assert cur.fetchone()[0] == 'on'
    conn.rollback()
    try:
        assess(conn,capture_id=str(capture_id),parse_run_id=str(run_id),
               code_revision='1'*40,expected_count=count+1)
    except ValueError:
        pass
    else:
        raise AssertionError('QA accepted incorrect source denominator')
    conn.rollback()
print('Read-only QA verifies exact source facts and blocks unattributed semantics')
