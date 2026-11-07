from io import BytesIO
from types import SimpleNamespace

import pytest

from white_list_archive.acquisition.auto_transform import (
    persist_operational_report, private_connection, read_snapshot_verified,
)
from white_list_archive.persistence.parse_snapshot import snapshot_sha256


def test_client_tls_is_required_even_if_database_connects(monkeypatch):
    import psycopg

    class Connection:
        info = SimpleNamespace(ssl_in_use=False)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr(psycopg, "connect", lambda *a, **kw: Connection())
    with pytest.raises(RuntimeError, match="requires a TLS"):
        with private_connection("not-disclosed"):
            pytest.fail("Unencrypted connection must not reach ingestion")


def test_tls_checks_negotiated_client_protocol_and_cipher(monkeypatch):
    import psycopg

    class Connection:
        info = SimpleNamespace(ssl_in_use=True)
        pgconn = SimpleNamespace(ssl_attribute=lambda key: {
            b"protocol": b"TLSv1.3", b"cipher": b"TLS_AES_256_GCM_SHA384",
        }[key])
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr(psycopg, "connect", lambda *a, **kw: Connection())
    with private_connection("not-disclosed") as conn:
        assert conn.info.ssl_in_use
    Connection.pgconn = SimpleNamespace(ssl_attribute=lambda key: None)
    with pytest.raises(RuntimeError, match="unverified"):
        with private_connection("not-disclosed"):
            pytest.fail("Missing client TLS evidence must fail closed")


def test_reuse_rehashes_committed_rows_rather_than_trusting_count():
    records = [{"source_status": "listed", "name": "Synthetic"}]
    diagnostics = {"dropped_date_rows": 0}

    class Cursor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, *args):
            pass
        def fetchone(self):
            return self.row

    cursor = Cursor()
    conn = SimpleNamespace(cursor=lambda: cursor)
    cursor.row = (snapshot_sha256(records, diagnostics), 1, records, diagnostics)
    assert read_snapshot_verified(conn, "run") == (records, diagnostics)
    cursor.row = ("0" * 64, 1, records, diagnostics)
    with pytest.raises(RuntimeError, match="integrity"):
        read_snapshot_verified(conn, "run")
    cursor.row = None
    with pytest.raises(RuntimeError, match="missing"):
        read_snapshot_verified(conn, "run")


def test_private_diagnostic_attempts_are_append_only_and_verified():
    class Client:
        objects = {}
        corrupt = False
        def put_object(self, **kwargs):
            assert kwargs["IfNoneMatch"] == "*"
            assert kwargs["Key"] not in self.objects
            self.objects[kwargs["Key"]] = kwargs["Body"]
        def get_object(self, **kwargs):
            body = self.objects[kwargs["Key"]]
            return {"Body": BytesIO(body + b"!" if self.corrupt else body)}

    client = Client()
    store = SimpleNamespace(client=client, config=SimpleNamespace(bucket="private"))
    report = {"outcomes": [{"stage": "parser_compatibility", "reason": "review"}]}
    persist_operational_report(store, report)
    persist_operational_report(store, report)
    assert len(client.objects) == 2
    client.corrupt = True
    with pytest.raises(RuntimeError, match="readback"):
        persist_operational_report(store, report)
    assert len(client.objects) == 3  # A failed readback never deletes prior evidence.
