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
