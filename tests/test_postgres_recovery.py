import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from white_list_archive.storage.postgres_recovery import (
    RecoveryFailure, backup_and_clean_restore, canonical_bytes, digest,
    private_write_readback, run_client,
)


def test_private_readback_mismatch_fails_and_closes_stream():
    stream = io.BytesIO(b"different")
    client = SimpleNamespace(put_object=lambda **kw: None,
        get_object=lambda **kw: {"Body": stream})
    store = SimpleNamespace(client=client, config=SimpleNamespace(bucket="private"))
    with pytest.raises(RecoveryFailure, match="readback_mismatch"):
        private_write_readback(store, "new-attempt", b"expected", "application/json")
    assert stream.closed


def test_private_write_is_conditional_and_exact():
    writes = []
    client = SimpleNamespace(put_object=lambda **kw: writes.append(kw),
        get_object=lambda **kw: {"Body": io.BytesIO(b"exact")})
    store = SimpleNamespace(client=client, config=SimpleNamespace(bucket="private"))
    assert private_write_readback(store, "new", b"exact", "application/json") == b"exact"
    assert writes[0]["IfNoneMatch"] == "*"


def test_client_secret_never_in_argv_and_stderr_is_discarded(monkeypatch, tmp_path):
    seen = {}
    def fake_run(command, **kwargs):
        seen.update(command=command, **kwargs)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr("subprocess.run", fake_run)
    secret = "postgresql://private:never-print-me@provider/database"
    run_client("pg_dump", secret, arguments=("--format=custom",), output=tmp_path / "private.dump")
    assert secret not in repr(seen["command"])
    assert seen["env"]["PGDATABASE"] == secret
    import subprocess
    assert seen["stderr"] == subprocess.DEVNULL


def test_restore_executes_database_without_secret_arguments(monkeypatch, tmp_path):
    pytest.importorskip("psycopg")
    seen = {}
    def fake_run(command, **kwargs):
        seen.update(command=command, **kwargs)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr("subprocess.run", fake_run)
    source = tmp_path / "private.dump"
    source.write_bytes(b"dump")
    secret = "postgresql://u:never-print-me@localhost:5432/clean_restore"
    run_client("pg_restore", secret, input_path=source)
    assert "--dbname=clean_restore" in seen["command"]
    assert "never-print-me" not in repr(seen["command"])
    assert seen["env"]["PGPASSWORD"] == "never-print-me"


def test_restore_refuses_remote_target_before_connection():
    pytest.importorskip("psycopg")
    with pytest.raises(RecoveryFailure, match="ephemeral_loopback"):
        backup_and_clean_restore("postgresql://source/db", "postgresql://other/clean_restore", None, "a" * 40)


def test_canonical_inventory_hash_is_order_independent():
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})
    assert digest({"a": 1}) != digest({"a": 2})


@pytest.mark.skipif(not __import__("os").environ.get("RECOVERY_TEST_DSN"),
                    reason="requires an isolated PostgreSQL 18 test database")
def test_inventory_detects_data_and_constraint_changes():
    import os
    import psycopg
    from white_list_archive.storage.postgres_recovery import inspect_database
    with psycopg.connect(os.environ["RECOVERY_TEST_DSN"]) as conn:
        conn.execute("CREATE SCHEMA recovery_test")
        conn.execute("CREATE TABLE recovery_test.rows (id integer PRIMARY KEY, value text)")
        conn.execute("INSERT INTO recovery_test.rows VALUES (1,'before')")
        first = inspect_database(conn)
        conn.execute("UPDATE recovery_test.rows SET value='after'")
        second = inspect_database(conn)
        assert first["tables"] != second["tables"]
        assert first["structure_sha256"] == second["structure_sha256"]
        conn.execute("ALTER TABLE recovery_test.rows ADD CHECK (id>0)")
        third = inspect_database(conn)
        assert second["structure_sha256"] != third["structure_sha256"]
        conn.rollback()


@pytest.mark.skipif(not __import__("os").environ.get("RECOVERY_ROUNDTRIP_DSN"),
                    reason="requires isolated PostgreSQL 18 source/restore services and Docker")
def test_real_pg_dump_restore_uses_same_snapshot(tmp_path):
    import os
    import psycopg
    from white_list_archive.storage.postgres_recovery import inspect_database
    source_dsn = os.environ["RECOVERY_TEST_DSN"]
    restore_dsn = os.environ["RECOVERY_ROUNDTRIP_DSN"]
    with psycopg.connect(source_dsn, autocommit=True) as conn:
        conn.execute("CREATE DATABASE clean_restore")
        conn.execute("CREATE EXTENSION pgcrypto")
        conn.execute("CREATE EXTENSION btree_gist")
        conn.execute("CREATE SCHEMA recovery_fixture")
        conn.execute("CREATE TABLE recovery_fixture.parent (id uuid PRIMARY KEY, value jsonb NOT NULL)")
        conn.execute("CREATE TABLE recovery_fixture.child (id integer PRIMARY KEY, parent uuid REFERENCES recovery_fixture.parent)")
        conn.execute("INSERT INTO recovery_fixture.parent VALUES ('11111111-1111-1111-1111-111111111111','{\"v\":1}')")
        conn.execute("INSERT INTO recovery_fixture.child VALUES (1,'11111111-1111-1111-1111-111111111111')")
        conn.execute("CREATE VIEW recovery_fixture.view_rows AS SELECT value FROM recovery_fixture.parent")
    with psycopg.connect(source_dsn) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        snapshot = conn.execute("SELECT pg_export_snapshot()").fetchone()[0]
        expected = inspect_database(conn)
        with psycopg.connect(source_dsn) as writer:
            writer.execute("INSERT INTO recovery_fixture.child VALUES (2,'11111111-1111-1111-1111-111111111111')")
        dump = tmp_path / "synthetic.dump"
        run_client("pg_dump", source_dsn, arguments=("--format=custom", "--no-owner", "--no-acl", "--snapshot=" + snapshot), output=dump)
    run_client("pg_restore", restore_dsn, arguments=("--exit-on-error", "--no-owner", "--no-acl"), input_path=dump)
    with psycopg.connect(restore_dsn) as restored:
        assert inspect_database(restored) == expected
        assert restored.execute("SELECT count(*) FROM recovery_fixture.child").fetchone()[0] == 1
