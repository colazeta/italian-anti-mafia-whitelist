"""Real PostgreSQL check for immutable parser snapshots on an ephemeral CI database."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
import threading
import time

import psycopg

from white_list_archive.persistence.parse_snapshot import persist_parse_snapshot, snapshot_sha256


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


dsn = os.environ["TEST_DSN"]
started = datetime(2026, 9, 23, 5, 10, tzinfo=timezone.utc)
completed = datetime(2026, 9, 23, 5, 11, tzinfo=timezone.utc)
records = [
    {
        "operator_name": "Synthetic Operator A",
        "source_status": "listed",
        "source_fields": {"physical_locator": "row:1", "sections": ["I"]},
    },
    {
        "operator_name": "Synthetic Operator B",
        "source_status": "applicant",
        "source_fields": {"physical_locator": "row:2", "sections": ["II"]},
    },
]
diagnostics = {"source_rows": 2, "public_records": 2, "warnings": []}

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO source.source_series(series_code, series_name, series_type_code)
            VALUES ('ci-parse-snapshot','CI parse snapshot synthetic series','list')
            RETURNING series_id
            """
        )
        series_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO source.source_resource(canonical_locator, web_url, resource_type_code)
            VALUES ('https://official.example.test/snapshot.pdf',
                    'https://official.example.test/snapshot.pdf','pdf')
            RETURNING resource_id
            """
        )
        resource_id = cur.fetchone()[0]
        content_bytes = b"synthetic immutable source bytes"
        content_sha = _sha(content_bytes)
        cur.execute(
            """
            INSERT INTO source.content_object(
                sha256,mime_type,file_size,storage_uri,storage_status_code
            ) VALUES (%s,'application/pdf',%s,'https://ci.invalid/evidence/sha256/synthetic','durable')
            RETURNING content_object_id
            """,
            (content_sha, len(content_bytes)),
        )
        content_id = cur.fetchone()[0]
        capture_ids = [
            "10000000-0000-4000-8000-000000000001",
            "10000000-0000-4000-8000-000000000002",
        ]
        for offset, capture_id in enumerate(capture_ids):
            cur.execute(
                """
                INSERT INTO source.source_capture(
                    capture_id, series_id, resource_id, content_object_id,
                    captured_at, http_status, origin_type_code, authority_rank_code,
                    resolved_url
                ) VALUES (%s,%s,%s,%s,%s,200,'official_current','primary_official',
                          'https://official.example.test/snapshot.pdf')
                """,
                (
                    capture_id,
                    series_id,
                    resource_id,
                    content_id,
                    datetime(2026, 9, 23, 5, offset, tzinfo=timezone.utc),
                ),
            )

    common = dict(
        parser_name="synthetic_snapshot_parser",
        parser_revision="1",
        code_revision="a" * 40,
        configuration_hash="b" * 64,
        started_at=started,
        completed_at=completed,
        records=records,
        diagnostics=diagnostics,
    )
    first = persist_parse_snapshot(conn, capture_id=capture_ids[0], **common)
    repeated = persist_parse_snapshot(conn, capture_id=capture_ids[0], **common)

    retry_common = dict(common)
    retry_common["started_at"] = datetime(2026, 9, 23, 5, 14, tzinfo=timezone.utc)
    retry_common["completed_at"] = datetime(2026, 9, 23, 5, 15, tzinfo=timezone.utc)
    retried_later = persist_parse_snapshot(conn, capture_id=capture_ids[0], **retry_common)

    second_capture = persist_parse_snapshot(conn, capture_id=capture_ids[1], **common)

    assert (
        first["parse_run_id"]
        == repeated["parse_run_id"]
        == retried_later["parse_run_id"]
        == second_capture["parse_run_id"]
    )
    assert first["snapshot_sha256"] == snapshot_sha256(records, diagnostics)
    assert not first["parse_run_reused"] and not first["snapshot_reused"]
    assert repeated["parse_run_reused"] and repeated["snapshot_reused"] and repeated["capture_link_reused"]
    assert retried_later["parse_run_reused"] and retried_later["snapshot_reused"]
    assert retried_later["capture_link_reused"]
    assert second_capture["parse_run_reused"] and second_capture["snapshot_reused"]
    assert not second_capture["capture_link_reused"]
    assert first["capture_inputs"][0]["label"] == "primary"

    # A replay retry at a later wall-clock time reuses the same interpretation
    # identity and preserves the processing activity recorded by the first
    # successful materialisation.
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT pa.started_at, pa.completed_at
            FROM source.parse_run pr
            JOIN provenance.processing_activity pa
              ON pa.processing_activity_id=pr.processing_activity_id
            WHERE pr.parse_run_id=%s
            """,
            (first["parse_run_id"],),
        )
        assert cur.fetchone() == (started, completed)

    # The same immutable interpretation identity producing different output is
    # still an integrity error; later retry timestamps do not create a loophole.
    conflicting = dict(retry_common)
    conflicting["records"] = [dict(records[0], retry_conflict=True), records[1]]
    try:
        with conn.transaction():
            persist_parse_snapshot(conn, capture_id=capture_ids[0], **conflicting)
    except ValueError as exc:
        assert "immutable interpretation output" in str(exc)
    else:
        raise AssertionError("Conflicting output for one parse identity was accepted")

    revised = dict(common)
    revised["parser_revision"] = "2"
    revised["started_at"] = datetime(2026, 9, 23, 5, 12, tzinfo=timezone.utc)
    revised["completed_at"] = datetime(2026, 9, 23, 5, 13, tzinfo=timezone.utc)
    revised_records = [dict(row, parser_revision_note="revision-2") for row in records]
    revised["records"] = revised_records
    revised["diagnostics"] = {**diagnostics, "parser_revision": "2"}
    later = persist_parse_snapshot(conn, capture_id=capture_ids[0], **revised)
    assert later["parse_run_id"] != first["parse_run_id"]
    assert later["snapshot_sha256"] != first["snapshot_sha256"]

    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM source.content_object WHERE content_object_id=%s",
            (content_id,),
        )
        assert cur.fetchone()[0] == 1
        cur.execute(
            "SELECT count(*) FROM source.source_capture WHERE series_id=%s",
            (series_id,),
        )
        assert cur.fetchone()[0] == 2
        cur.execute(
            "SELECT count(*) FROM source.parse_run WHERE content_object_id=%s",
            (content_id,),
        )
        assert cur.fetchone()[0] == 2
        cur.execute(
            """
            SELECT count(*)
            FROM provenance.processing_activity
            WHERE activity_type_code='parse' AND software_name='synthetic_snapshot_parser'
            """
        )
        assert cur.fetchone()[0] == 2
        cur.execute(
            """
            SELECT count(*), sum(record_count)
            FROM source.parse_snapshot
            WHERE parse_run_id IN (%s,%s)
            """,
            (first["parse_run_id"], later["parse_run_id"]),
        )
        assert cur.fetchone() == (2, 4)
        cur.execute(
            """
            SELECT count(*) FROM source.capture_parse_run
            WHERE capture_id IN (%s,%s)
            """,
            (capture_ids[0], capture_ids[1]),
        )
        assert cur.fetchone()[0] == 3
        cur.execute(
            """
            SELECT records_json, diagnostics_json
            FROM source.parse_snapshot WHERE parse_run_id=%s
            """,
            (first["parse_run_id"],),
        )
        persisted_records, persisted_diagnostics = cur.fetchone()
        assert persisted_records == records
        assert persisted_diagnostics == diagnostics
        cur.execute(
            "SELECT count(*) FROM source.source_edition WHERE series_id=%s",
            (series_id,),
        )
        assert cur.fetchone()[0] == 0

    # Snapshot rows are append-only. A failed mutation is isolated in a savepoint.
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE source.parse_snapshot SET record_count=99 WHERE parse_run_id=%s",
                    (first["parse_run_id"],),
                )
    except psycopg.DatabaseError as exc:
        assert "parse_snapshot rows are immutable" in str(exc)
    else:
        raise AssertionError("Mutable parse snapshot was accepted")

    # A second durable ContentObject/capture is used both for a negative scalar
    # association and as a legitimate second member of a bundle parser input set.
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO source.source_resource(canonical_locator, web_url, resource_type_code)
            VALUES ('https://official.example.test/applicants.pdf',
                    'https://official.example.test/applicants.pdf','pdf')
            RETURNING resource_id
            """
        )
        other_resource_id = cur.fetchone()[0]
        other_bytes = b"different synthetic immutable bytes"
        other_sha = _sha(other_bytes)
        cur.execute(
            """
            INSERT INTO source.content_object(
                sha256,mime_type,file_size,storage_uri,storage_status_code
            ) VALUES (%s,'application/pdf',%s,'https://ci.invalid/evidence/sha256/other','durable')
            RETURNING content_object_id
            """,
            (other_sha, len(other_bytes)),
        )
        other_content_id = cur.fetchone()[0]
        other_capture_id = "20000000-0000-4000-8000-000000000001"
        cur.execute(
            """
            INSERT INTO source.source_capture(
                capture_id, series_id, resource_id, content_object_id,
                captured_at, http_status, origin_type_code, authority_rank_code,
                resolved_url
            ) VALUES (%s,%s,%s,%s,
                      '2026-09-23T05:20:00+00:00',200,'official_current','primary_official',
                      'https://official.example.test/applicants.pdf')
            """,
            (other_capture_id, series_id, other_resource_id, other_content_id),
        )
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO source.capture_parse_run(capture_id, parse_run_id, input_label)
                    VALUES (%s,%s,'primary')
                    """,
                    (other_capture_id, first["parse_run_id"]),
                )
    except psycopg.DatabaseError as exc:
        assert "different ContentObjects" in str(exc)
    else:
        raise AssertionError("Cross-content capture/parse association was accepted")

    bundle_records = [
        {
            "operator_name": "Synthetic Bundle Operator",
            "source_status": "listed",
            "source_fields": {"listed_locator": "row:1", "applicant_locator": "row:9"},
        }
    ]
    bundle_diagnostics = {"source_rows": 1, "public_records": 1, "bundle_members": 2}
    bundle_common = dict(
        parser_name="synthetic_bundle_parser",
        parser_revision="1",
        code_revision="c" * 40,
        configuration_hash="d" * 64,
        started_at=datetime(2026, 9, 23, 5, 21, tzinfo=timezone.utc),
        completed_at=datetime(2026, 9, 23, 5, 22, tzinfo=timezone.utc),
        records=bundle_records,
        diagnostics=bundle_diagnostics,
    )
    bundle_inputs = [
        {"label": "listed", "capture_id": capture_ids[0]},
        {"label": "applicants", "capture_id": other_capture_id},
    ]
    bundle = persist_parse_snapshot(conn, capture_inputs=bundle_inputs, **bundle_common)
    bundle_repeat = persist_parse_snapshot(conn, capture_inputs=list(reversed(bundle_inputs)), **bundle_common)
    assert bundle["parse_run_id"] == bundle_repeat["parse_run_id"]
    assert not bundle["parse_run_reused"]
    assert bundle_repeat["parse_run_reused"] and bundle_repeat["snapshot_reused"]
    assert [row["label"] for row in bundle["capture_inputs"]] == ["applicants", "listed"]

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT input_label, content_object_id
            FROM source.parse_run_input
            WHERE parse_run_id=%s ORDER BY input_label
            """,
            (bundle["parse_run_id"],),
        )
        assert cur.fetchall() == [
            ("applicants", other_content_id),
            ("listed", content_id),
        ]
        cur.execute(
            """
            SELECT capture_id::text, input_label
            FROM source.capture_parse_run
            WHERE parse_run_id=%s ORDER BY input_label
            """,
            (bundle["parse_run_id"],),
        )
        assert cur.fetchall() == [
            (other_capture_id, "applicants"),
            (capture_ids[0], "listed"),
        ]
        cur.execute(
            "SELECT count(*) FROM source.source_edition WHERE series_id=%s",
            (series_id,),
        )
        assert cur.fetchone()[0] == 0

    # Input provenance is immutable too.
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE source.parse_run_input SET input_label='changed'
                    WHERE parse_run_id=%s AND input_label='listed'
                    """,
                    (bundle["parse_run_id"],),
                )
    except psycopg.DatabaseError as exc:
        assert "parse_run_input rows are immutable" in str(exc)
    else:
        raise AssertionError("Mutable parser input provenance was accepted")

    conn.rollback()

# Prove actual concurrent retries are idempotent rather than relying only on the
# unique parse_run_code index. The first transaction creates the interpretation
# but deliberately withholds commit while a second connection attempts the same
# stable identity. After the first commit, the second must re-read and reuse it;
# a bare SELECT-then-INSERT implementation instead raises a unique violation.
concurrent_records = [
    {
        "operator_name": "Synthetic Concurrent Operator",
        "source_status": "listed",
        "source_fields": {"physical_locator": "row:1"},
    }
]
concurrent_diagnostics = {"source_rows": 1, "public_records": 1, "warnings": []}
concurrent_capture_id = "30000000-0000-4000-8000-000000000001"
concurrent_common = dict(
    parser_name="synthetic_snapshot_concurrent_parser",
    parser_revision="1",
    code_revision="e" * 40,
    configuration_hash="f" * 64,
    started_at=datetime(2026, 9, 23, 6, 0, tzinfo=timezone.utc),
    completed_at=datetime(2026, 9, 23, 6, 1, tzinfo=timezone.utc),
    records=concurrent_records,
    diagnostics=concurrent_diagnostics,
)
with psycopg.connect(dsn) as setup_conn:
    with setup_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO source.source_series(series_code, series_name, series_type_code)
            VALUES ('ci-parse-snapshot-concurrent','CI concurrent parse snapshot series','list')
            RETURNING series_id
            """
        )
        concurrent_series_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO source.source_resource(canonical_locator, web_url, resource_type_code)
            VALUES ('https://official.example.test/concurrent.pdf',
                    'https://official.example.test/concurrent.pdf','pdf')
            RETURNING resource_id
            """
        )
        concurrent_resource_id = cur.fetchone()[0]
        concurrent_bytes = b"synthetic concurrent immutable source bytes"
        concurrent_sha = _sha(concurrent_bytes)
        cur.execute(
            """
            INSERT INTO source.content_object(
                sha256,mime_type,file_size,storage_uri,storage_status_code
            ) VALUES (%s,'application/pdf',%s,'https://ci.invalid/evidence/sha256/concurrent','durable')
            RETURNING content_object_id
            """,
            (concurrent_sha, len(concurrent_bytes)),
        )
        concurrent_content_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO source.source_capture(
                capture_id, series_id, resource_id, content_object_id,
                captured_at, http_status, origin_type_code, authority_rank_code,
                resolved_url
            ) VALUES (%s,%s,%s,%s,
                      '2026-09-23T06:00:00+00:00',200,'official_current','primary_official',
                      'https://official.example.test/concurrent.pdf')
            """,
            (
                concurrent_capture_id,
                concurrent_series_id,
                concurrent_resource_id,
                concurrent_content_id,
            ),
        )
    setup_conn.commit()

first_conn = psycopg.connect(dsn)
try:
    concurrent_first = persist_parse_snapshot(
        first_conn, capture_id=concurrent_capture_id, **concurrent_common
    )
    second_started = threading.Event()
    second_result: dict[str, object] = {}
    second_error: list[BaseException] = []

    def _run_concurrent_retry() -> None:
        try:
            with psycopg.connect(dsn) as second_conn:
                later_common = dict(concurrent_common)
                later_common["started_at"] = datetime(2026, 9, 23, 6, 2, tzinfo=timezone.utc)
                later_common["completed_at"] = datetime(2026, 9, 23, 6, 3, tzinfo=timezone.utc)
                second_started.set()
                second_result.update(
                    persist_parse_snapshot(
                        second_conn,
                        capture_id=concurrent_capture_id,
                        **later_common,
                    )
                )
                second_conn.commit()
        except BaseException as exc:  # surfaced in the main test thread below
            second_error.append(exc)

    retry_thread = threading.Thread(target=_run_concurrent_retry, daemon=True)
    retry_thread.start()
    assert second_started.wait(timeout=5), "Concurrent retry thread did not start"
    time.sleep(0.2)
    assert retry_thread.is_alive(), "Concurrent retry did not wait for the first transaction"

    first_conn.commit()
    retry_thread.join(timeout=5)
    assert not retry_thread.is_alive(), "Concurrent retry did not finish after first commit"
    assert not second_error, f"Concurrent retry failed instead of reusing the parse run: {second_error!r}"
    assert second_result["parse_run_id"] == concurrent_first["parse_run_id"]
    assert second_result["parse_run_reused"] is True
    assert second_result["snapshot_reused"] is True
    assert second_result["capture_link_reused"] is True
finally:
    if not first_conn.closed:
        first_conn.close()

with psycopg.connect(dsn) as verify_conn:
    with verify_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM source.parse_run WHERE content_object_id=%s",
            (concurrent_content_id,),
        )
        assert cur.fetchone()[0] == 1
        cur.execute(
            """
            SELECT count(*)
            FROM provenance.processing_activity
            WHERE activity_type_code='parse'
              AND software_name='synthetic_snapshot_concurrent_parser'
            """
        )
        assert cur.fetchone()[0] == 1

print(
    "Immutable parse snapshots passed against PostgreSQL: repeated unchanged captures, later wall-clock retries, "
    "and concurrent retries reuse one interpretation while preserving first processing provenance; divergent "
    "output fails closed; parser revisions remain separate; labelled multi-ContentObject bundles preserve every "
    "input/capture; full records/diagnostics are retrievable; no SourceEdition is invented."
)
