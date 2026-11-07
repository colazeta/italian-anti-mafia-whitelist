from datetime import datetime, timezone

import pytest

from white_list_archive.acquisition.production_checkpoint import collect_checkpoint


class Cursor:
    def __init__(self):
        self.calls = []
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if "transaction_timestamp()" in sql:
            self.result = (datetime(2026, 11, 7, tzinfo=timezone.utc),)
        elif "has_schema_privilege" in sql:
            self.result = (params[0] != "semantic",)
        elif "sum(record_count)" in sql:
            self.result = (13473, 1)
        elif "storage_status_code" in sql:
            self.result = (14,)
        else:
            self.result = (38,)

    def fetchone(self):
        return self.result


class Connection:
    def __init__(self):
        self.cur = Cursor()

    def cursor(self):
        return self.cur


def test_unreadable_layer_is_unknown_and_never_queried_as_zero():
    conn = Connection()
    report = collect_checkpoint(conn, code_revision="a" * 40)
    assert report["metrics"]["semantic_observations"]["value"] is None
    assert report["metrics"]["semantic_observations"]["status"] == "not_verified"
    assert not any("FROM semantic.entity_observation" in q for q, _ in conn.cur.calls)
    assert conn.cur.calls[0][0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    assert report["metrics"]["snapshot_record_occurrences"]["distinct_business_count"] is False
    assert report["metrics"]["snapshot_count_mismatches"]["numerator"] == 1
    assert report["metrics"]["snapshot_count_mismatches"]["denominator"] == 38
    assert report["independent_backup_verified"] is None
    assert report["release_approval_verified"] is None


def test_bad_revision_stops_before_database_access():
    conn = Connection()
    with pytest.raises(ValueError):
        collect_checkpoint(conn, code_revision="main")
    assert conn.cur.calls == []
