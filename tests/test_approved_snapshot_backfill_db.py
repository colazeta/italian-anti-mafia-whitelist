"""Exercise lookup SQL against the applied CI PostgreSQL schema."""
import os

import pytest

from white_list_archive.acquisition.approved_snapshot_backfill import existing_snapshot


@pytest.mark.skipif(not os.environ.get('BACKFILL_TEST_DSN'), reason='Requires applied CI PostgreSQL schema')
def test_lookup_on_real_schema_disambiguates_both_content_object_columns():
    import psycopg
    job = {'config': {'parser': 'nonexistent-regression-parser', 'source_key': 'regression-only'},
           'captures': {'primary': {'state': {'sha256': '0'*64}}}}
    with psycopg.connect(os.environ['BACKFILL_TEST_DSN']) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        assert existing_snapshot(conn, job) is False


@pytest.mark.skipif(not os.environ.get('BACKFILL_TEST_DSN'), reason='Requires CI PostgreSQL')
def test_snapshot_counter_hash_survives_actual_postgresql_jsonb_roundtrip():
    import json
    import psycopg
    from white_list_archive.persistence.parse_snapshot import snapshot_sha256
    records = [{'source_status': 'listed'}]
    diagnostics = {'parser': 'grosseto_listed', 'section_counts': {n: n+2 for n in range(1, 11)}}
    with psycopg.connect(os.environ['BACKFILL_TEST_DSN']) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        stored = conn.execute('SELECT %s::jsonb', (json.dumps({'records': records, 'diagnostics': diagnostics}),)).fetchone()[0]
    assert snapshot_sha256(records, diagnostics) == snapshot_sha256(stored['records'], stored['diagnostics'])
