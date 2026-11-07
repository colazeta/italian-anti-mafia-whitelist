"""Private logical PostgreSQL backup and clean restore, without a public dump.

This is a same-provider recovery checkpoint, not independent disaster recovery.
The source is held in one exported read-only snapshot until pg_dump completes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from uuid import uuid4


class RecoveryFailure(RuntimeError):
    """Only a non-sensitive stage identifier may leave this private runner."""


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def run_client(program, dsn, *, arguments=(), output=None, input_path=None):
    """Use a pinned major client, passing connection material only in environment."""
    command = ["docker", "run", "--rm", "--network", "host", "--env", "PGDATABASE",
               "--env", "PGCONNECT_TIMEOUT"]
    env = dict(os.environ, PGDATABASE=dsn, PGCONNECT_TIMEOUT="30")
    if program == "pg_restore":
        from psycopg.conninfo import conninfo_to_dict
        target = conninfo_to_dict(dsn)
        # pg_restore requires --dbname to execute instead of emitting SQL. Its
        # fixed non-secret database name is safe in argv; all other parameters
        # remain in libpq environment variables.
        if target.get("dbname") != "clean_restore":
            raise RecoveryFailure("invalid_restore_database")
        for option, variable in (("host", "PGHOST"), ("port", "PGPORT"),
                                 ("user", "PGUSER"), ("password", "PGPASSWORD")):
            if option in target:
                env[variable] = target[option]
                command += ["--env", variable]
        env["PGDATABASE"] = "clean_restore"
        arguments = ("--dbname=clean_restore", *arguments)
    command += ["-i", "postgres:18-alpine", program, *arguments]
    with (open(input_path, "rb") if input_path else open(os.devnull, "rb")) as source:
        with (open(output, "xb") if output else open(os.devnull, "wb")) as destination:
            result = subprocess.run(command, env=env, stdin=source, stdout=destination,
                                    stderr=subprocess.DEVNULL, check=False, timeout=600)
    if result.returncode:
        raise RecoveryFailure(program + "_failed")


def inspect_database(conn):
    """Compare exact row multisets and structural catalogues, including empty tables.

    Sequence/large-object/foreign-table extensions fail closed: the currently
    deployed UUID-based project has no such objects. No partial backup is labelled
    complete when the database grows unsupported storage features.
    """
    from psycopg import sql

    with conn.cursor() as cur:
        cur.execute("SELECT current_setting('server_version_num')::int")
        if not 180000 <= cur.fetchone()[0] < 190000:
            raise RecoveryFailure("postgresql_18_required")
        cur.execute("""SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                       WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
                       AND c.relkind IN ('S','f')""")
        unsupported = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM pg_largeobject_metadata")
        if unsupported or cur.fetchone()[0]:
            raise RecoveryFailure("unsupported_storage_objects")
        cur.execute("""SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                       WHERE n.nspname !~ '^pg_' AND c.relrowsecurity""")
        if cur.fetchone()[0]:
            raise RecoveryFailure("row_security_requires_separate_recovery_review")
        cur.execute("""SELECT n.nspname,c.relname FROM pg_class c
                       JOIN pg_namespace n ON n.oid=c.relnamespace
                       WHERE c.relkind IN ('r','p','m') AND n.nspname !~ '^pg_'
                       AND n.nspname <> 'information_schema' ORDER BY 1,2""")
        tables = cur.fetchall()
        cur.execute("""SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                       WHERE c.relkind IN ('r','p','m') AND n.nspname !~ '^pg_'
                       AND n.nspname <> 'information_schema'
                       AND (NOT has_table_privilege(c.oid,'SELECT')
                            OR NOT has_schema_privilege(n.oid,'USAGE'))""")
        unreadable = cur.fetchone()[0]
        if unreadable:
            raise RecoveryFailure("unreadable_table_count=" + str(unreadable))
    rows = {}
    for schema, table in tables:
        row_hash = hashlib.sha256()
        count = 0
        with conn.cursor(name="recovery_" + uuid4().hex) as cur:
            cur.execute(sql.SQL("SELECT to_jsonb(t)::text FROM {}.{} t ORDER BY to_jsonb(t)::text COLLATE \"C\"")
                        .format(sql.Identifier(schema), sql.Identifier(table)))
            for (row,) in cur:
                payload = row.encode("utf-8")
                row_hash.update(len(payload).to_bytes(8, "big"))
                row_hash.update(payload)
                count += 1
        rows[schema + "." + table] = {"count": count, "sha256": row_hash.hexdigest()}
    catalogues = {
        "columns": """SELECT n.nspname,c.relname,a.attname,a.attnum,
            format_type(a.atttypid,a.atttypmod),a.attnotnull,a.attidentity,a.attgenerated,
            pg_get_expr(d.adbin,d.adrelid)
            FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
            WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
            AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2,4""",
        "constraints": """SELECT n.nspname,c.relname,k.conname,k.contype,k.convalidated,
            pg_get_constraintdef(k.oid) FROM pg_constraint k
            JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname !~ '^pg_' ORDER BY 1,2,3""",
        "indexes": """SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes
            WHERE schemaname !~ '^pg_' ORDER BY 1,2,3""",
        "functions": """SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),
            pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
            AND p.prokind IN ('f','p') ORDER BY 1,2,3""",
        "views": """SELECT schemaname,viewname,definition FROM pg_views
            WHERE schemaname !~ '^pg_' AND schemaname <> 'information_schema' ORDER BY 1,2""",
        "triggers": """SELECT n.nspname,c.relname,t.tgname,pg_get_triggerdef(t.oid)
            FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE NOT t.tgisinternal AND n.nspname !~ '^pg_' ORDER BY 1,2,3""",
        "extensions": "SELECT extname,extversion FROM pg_extension ORDER BY 1",
    }
    structures = {}
    with conn.cursor() as cur:
        for name, query in catalogues.items():
            cur.execute(query)
            structures[name] = digest(cur.fetchall())
    return {"tables": rows, "structure_sha256": structures}


def private_write_readback(store, key, body, content_type):
    store.client.put_object(Bucket=store.config.bucket, Key=key, Body=body,
                            ContentType=content_type, IfNoneMatch="*")
    response = store.client.get_object(Bucket=store.config.bucket, Key=key)
    stream = response["Body"]
    try:
        actual = stream.read(len(body) + 1)
    finally:
        stream.close()
    if actual != body:
        raise RecoveryFailure("private_backup_readback_mismatch")
    return actual


def backup_and_clean_restore(source_dsn, restore_dsn, store, code_revision):
    import psycopg
    from psycopg.conninfo import conninfo_to_dict

    if source_dsn == restore_dsn:
        raise RecoveryFailure("restore_target_matches_source")
    target = conninfo_to_dict(restore_dsn)
    if target.get("host") not in ("localhost", "127.0.0.1", "::1") or target.get("dbname") != "clean_restore":
        raise RecoveryFailure("restore_target_must_be_ephemeral_loopback_database")
    run_id = str(uuid4())
    with tempfile.TemporaryDirectory(prefix="wl-private-db-recovery-") as work:
        os.chmod(work, 0o700)
        dump_path = Path(work) / "database.dump"
        with psycopg.connect(source_dsn, connect_timeout=30) as conn:
            if not conn.pgconn.ssl_in_use:
                raise RecoveryFailure("source_tls_required")
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            snapshot = conn.execute("SELECT pg_export_snapshot()").fetchone()[0]
            original = inspect_database(conn)
            run_client("pg_dump", source_dsn, arguments=("--format=custom", "--no-owner",
                       "--no-acl", "--snapshot=" + snapshot), output=dump_path)
        body = dump_path.read_bytes()
        dump_sha = hashlib.sha256(body).hexdigest()
        # Per-attempt key avoids overwriting any evidence; content identity is explicit.
        prefix = f"operations/v1/postgres-recovery/{run_id}"
        restored_dump = private_write_readback(store, prefix + "/" + dump_sha + ".dump",
                                              body, "application/octet-stream")
        restore_input = Path(work) / "provider-readback.dump"
        restore_input.write_bytes(restored_dump)
        with psycopg.connect(restore_dsn, connect_timeout=30) as conn:
            # The workflow supplies a new database; refuse any user-defined objects.
            count = conn.execute("""SELECT count(*) FROM pg_class c JOIN pg_namespace n
                ON n.oid=c.relnamespace WHERE n.nspname !~ '^pg_'
                AND n.nspname <> 'information_schema'""").fetchone()[0]
            if count:
                raise RecoveryFailure("restore_target_not_empty")
        run_client("pg_restore", restore_dsn, arguments=("--exit-on-error", "--no-owner",
                   "--no-acl"), input_path=restore_input)
        with psycopg.connect(restore_dsn, connect_timeout=30) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            restored = inspect_database(conn)
        if restored != original:
            raise RecoveryFailure("restored_database_differs")
        report = {"schema_version": 1, "run_id": run_id, "code_revision": code_revision,
                  "verified_at": datetime.now(timezone.utc).isoformat(),
                  "dump_sha256": dump_sha, "dump_bytes": len(body),
                  "inventory": original, "inventory_sha256": digest(original),
                  "all_tables_and_structures_restored": True,
                  "independent_backup": False, "role_acls_restored": False}
        private_write_readback(store, prefix + "/verification.json", canonical_bytes(report),
                               "application/json")
        return {key: report[key] for key in ("schema_version", "run_id", "code_revision",
                "verified_at", "dump_sha256", "dump_bytes", "inventory_sha256",
                "all_tables_and_structures_restored", "independent_backup", "role_acls_restored")} | {
                    "tables_verified": len(original["tables"]),
                    "rows_verified": sum(v["count"] for v in original["tables"].values())}


def main():
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    try:
        config = StoreConfig.from_env()
        report = backup_and_clean_restore(os.environ["EVIDENCE_DATABASE_URL"],
            os.environ["RESTORE_DATABASE_URL"], EvidenceStore(client_for(config), config),
            os.environ["GITHUB_SHA"])
        print(json.dumps(report, sort_keys=True))
    except Exception as exc:
        # Provider/libpq/tool messages can contain connection strings or source rows.
        stage = str(exc) if isinstance(exc, RecoveryFailure) else "private_recovery_failed"
        print(json.dumps({"status": "failed", "stage": stage}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
