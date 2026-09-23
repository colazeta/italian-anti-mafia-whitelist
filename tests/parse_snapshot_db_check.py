"""Real PostgreSQL check for immutable parser snapshots; transaction rolled back."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os

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
    second_capture = persist_parse_snapshot(conn, capture_id=capture_ids[1], **common)

    assert first["parse_run_id"] == repeated["parse_run_id"] == second_capture["parse_run_id"]
    assert first["snapshot_sha256"] == snapshot_sha256(records, diagnostics)
    assert not first["parse_run_reused"] and not first["snapshot_reused"]
    assert repeated["parse_run_reused"] and repeated["snapshot_reused"] and repeated["capture_link_reused"]
    assert second_capture["parse_run_reused"] and second_capture["snapshot_reused"]
    assert not second_capture["capture_link_reused"]

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

    # A capture cannot be associated with an interpretation of different bytes.
    with conn.cursor() as cur:
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
        cur.execute(
            """
            INSERT INTO source.source_capture(
                capture_id, series_id, resource_id, content_object_id,
                captured_at, http_status, origin_type_code, authority_rank_code,
                resolved_url
            ) VALUES ('20000000-0000-4000-8000-000000000001',%s,%s,%s,
                      '2026-09-23T05:20:00+00:00',200,'official_current','primary_official',
                      'https://official.example.test/snapshot.pdf')
            """,
            (series_id, resource_id, other_content_id),
        )
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO source.capture_parse_run(capture_id, parse_run_id)
                    VALUES ('20000000-0000-4000-8000-000000000001',%s)
                    """,
                    (first["parse_run_id"],),
                )
    except psycopg.DatabaseError as exc:
        assert "different ContentObjects" in str(exc)
    else:
        raise AssertionError("Cross-content capture/parse association was accepted")

    conn.rollback()

print(
    "Immutable parse snapshots passed against PostgreSQL: repeated unchanged captures reuse one interpretation; "
    "a parser revision creates a new interpretation; full records/diagnostics are retrievable; no SourceEdition is invented."
)
