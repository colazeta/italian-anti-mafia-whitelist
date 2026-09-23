"""Persist full private parser observations without inventing source publications.

A parse snapshot is an interpretation of one or more immutable ContentObjects. The
same parse run may be linked to multiple captures of unchanged bytes, while a new
input set, parser/configuration/code revision creates a new interpretation. Source
capture time and declared source dates remain on ``source.source_capture``;
processing time remains on ``provenance.processing_activity``.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any

try:
    import psycopg
except ImportError as exc:  # pragma: no cover - only when database extra is absent
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-blank string")
    return value.strip()


def _parse_time(value: Any, field: str) -> datetime:
    text = _required_text(value, field)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include an explicit timezone")
    return parsed


def canonical_snapshot_bytes(
    records: list[dict[str, Any]], diagnostics: dict[str, Any]
) -> bytes:
    """Return deterministic UTF-8 JSON for one complete parser output."""
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError("records must be a JSON array of objects")
    if not isinstance(diagnostics, dict):
        raise ValueError("diagnostics must be a JSON object")
    return json.dumps(
        {"records": records, "diagnostics": diagnostics},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def snapshot_sha256(
    records: list[dict[str, Any]], diagnostics: dict[str, Any]
) -> str:
    return hashlib.sha256(canonical_snapshot_bytes(records, diagnostics)).hexdigest()


def _parse_run_code(
    *,
    content_inputs: list[tuple[str, str]],
    parser_name: str,
    parser_revision: str,
    code_revision: str,
    configuration_hash: str,
) -> str:
    """Return a stable interpretation key while preserving scalar compatibility."""
    if content_inputs == [("primary", content_inputs[0][1])]:
        # Preserve the established scalar identity introduced by #175.
        input_material = content_inputs[0][1]
        parts = [
            input_material,
            parser_name,
            parser_revision,
            code_revision,
            configuration_hash,
        ]
    else:
        canonical_inputs = json.dumps(
            [{"label": label, "sha256": digest} for label, digest in content_inputs],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        parts = [
            "multi-input-v1",
            canonical_inputs,
            parser_name,
            parser_revision,
            code_revision,
            configuration_hash,
        ]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _capture_content(cur, capture_id: str):
    cur.execute(
        """
        SELECT c.content_object_id, o.sha256, o.storage_status_code
        FROM source.source_capture c
        LEFT JOIN source.content_object o ON o.content_object_id=c.content_object_id
        WHERE c.capture_id=%s
        """,
        (capture_id,),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Unknown source capture: {capture_id}")
    content_object_id, content_sha256, storage_status = row
    if content_object_id is None or content_sha256 is None:
        raise ValueError("Parse snapshot requires a capture bound to immutable source bytes")
    if storage_status != "durable":
        raise ValueError("Parse snapshot requires a durably persisted ContentObject")
    if not _SHA256_RE.fullmatch(content_sha256):
        raise ValueError("Persisted ContentObject has an invalid SHA-256 identity")
    return content_object_id, content_sha256


def _resolve_capture_inputs(
    cur,
    *,
    capture_id: str | None,
    capture_inputs: list[dict[str, str]] | None,
) -> list[dict[str, Any]]:
    """Resolve an explicit labelled capture set without collapsing equal bytes."""
    if capture_id is not None and capture_inputs is not None:
        raise ValueError("Provide either capture_id or capture_inputs, not both")
    if capture_inputs is None:
        capture_inputs = [{"label": "primary", "capture_id": _required_text(capture_id, "capture_id")}]
    if not isinstance(capture_inputs, list) or not capture_inputs:
        raise ValueError("capture_inputs must be a non-empty list")

    labels: set[str] = set()
    capture_ids: set[str] = set()
    resolved: list[dict[str, Any]] = []
    for index, item in enumerate(capture_inputs):
        if not isinstance(item, dict) or set(item) != {"label", "capture_id"}:
            raise ValueError("Each capture_inputs row must contain exactly label and capture_id")
        label = _required_text(item["label"], f"capture_inputs[{index}].label")
        current_capture_id = _required_text(
            item["capture_id"], f"capture_inputs[{index}].capture_id"
        )
        if label in labels:
            raise ValueError(f"Duplicate parse input label: {label}")
        if current_capture_id in capture_ids:
            raise ValueError("One capture/check cannot satisfy multiple parser input labels")
        labels.add(label)
        capture_ids.add(current_capture_id)
        content_object_id, content_sha256 = _capture_content(cur, current_capture_id)
        resolved.append(
            {
                "label": label,
                "capture_id": current_capture_id,
                "content_object_id": content_object_id,
                "content_sha256": content_sha256,
            }
        )
    resolved.sort(key=lambda row: row["label"])
    return resolved


def _ensure_parse_inputs(cur, parse_run_id, inputs: list[dict[str, Any]]) -> None:
    cur.execute(
        """
        SELECT input_label, content_object_id
        FROM source.parse_run_input
        WHERE parse_run_id=%s
        ORDER BY input_label
        """,
        (parse_run_id,),
    )
    existing = list(cur.fetchall())
    expected = [(item["label"], item["content_object_id"]) for item in inputs]
    if not existing:
        # Compatibility for an established scalar parse_run created before the
        # parse_run_input migration was applied to the live database.
        if len(inputs) != 1 or inputs[0]["label"] != "primary":
            raise ValueError("Existing parse run lacks immutable multi-input provenance")
        cur.execute(
            """
            INSERT INTO source.parse_run_input(parse_run_id,input_label,content_object_id)
            VALUES (%s,'primary',%s)
            """,
            (parse_run_id, inputs[0]["content_object_id"]),
        )
        existing = expected
    if existing != expected:
        raise ValueError("Existing parse run conflicts with immutable parser input provenance")


def _ensure_parse_run(
    cur,
    *,
    inputs: list[dict[str, Any]],
    parser_name: str,
    parser_revision: str,
    code_revision: str,
    configuration_hash: str,
    started_at: datetime,
    completed_at: datetime,
):
    content_inputs = [(row["label"], row["content_sha256"]) for row in inputs]
    parse_run_code = _parse_run_code(
        content_inputs=content_inputs,
        parser_name=parser_name,
        parser_revision=parser_revision,
        code_revision=code_revision,
        configuration_hash=configuration_hash,
    )
    software_version = f"{parser_revision}+git.{code_revision}"
    primary_content_object_id = inputs[0]["content_object_id"]
    cur.execute(
        """
        SELECT pr.parse_run_id, pr.content_object_id, pr.status_code,
               pa.software_name, pa.software_version, pa.configuration_hash,
               pa.started_at, pa.completed_at
        FROM source.parse_run pr
        JOIN provenance.processing_activity pa
          ON pa.processing_activity_id=pr.processing_activity_id
        WHERE pr.parse_run_code=%s
        """,
        (parse_run_code,),
    )
    row = cur.fetchone()
    if row:
        # ``parse_run_code`` identifies the interpretation, not a retry attempt.
        # The processing timestamps are retained from the first successful
        # materialisation and are never rewritten merely because an exact frozen
        # replay is retried at a later wall-clock time.
        expected_identity = (
            primary_content_object_id,
            "succeeded",
            parser_name,
            software_version,
            configuration_hash,
        )
        if tuple(row[1:6]) != expected_identity:
            raise ValueError("Existing parse_run_code conflicts with immutable interpretation provenance")
        _ensure_parse_inputs(cur, row[0], inputs)
        return row[0], parse_run_code, True

    cur.execute(
        """
        INSERT INTO provenance.processing_activity(
            activity_type_code, software_name, software_version,
            configuration_hash, started_at, completed_at
        ) VALUES ('parse',%s,%s,%s,%s,%s)
        RETURNING processing_activity_id
        """,
        (
            parser_name,
            software_version,
            configuration_hash,
            started_at,
            completed_at,
        ),
    )
    processing_activity_id = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO source.parse_run(
            content_object_id, processing_activity_id, status_code, parse_run_code
        ) VALUES (%s,%s,'succeeded',%s)
        RETURNING parse_run_id
        """,
        (primary_content_object_id, processing_activity_id, parse_run_code),
    )
    parse_run_id = cur.fetchone()[0]
    for item in inputs:
        cur.execute(
            """
            INSERT INTO source.parse_run_input(parse_run_id,input_label,content_object_id)
            VALUES (%s,%s,%s)
            """,
            (parse_run_id, item["label"], item["content_object_id"]),
        )
    return parse_run_id, parse_run_code, False


def _ensure_snapshot(
    cur,
    parse_run_id,
    records: list[dict[str, Any]],
    diagnostics: dict[str, Any],
):
    digest = snapshot_sha256(records, diagnostics)
    record_count = len(records)
    cur.execute(
        """
        SELECT snapshot_sha256, record_count, records_json, diagnostics_json
        FROM source.parse_snapshot
        WHERE parse_run_id=%s
        """,
        (parse_run_id,),
    )
    row = cur.fetchone()
    if row:
        if (
            row[0] != digest
            or row[1] != record_count
            or row[2] != records
            or row[3] != diagnostics
        ):
            raise ValueError("Existing parse snapshot conflicts with immutable interpretation output")
        return digest, True

    cur.execute(
        """
        INSERT INTO source.parse_snapshot(
            parse_run_id, snapshot_sha256, record_count, records_json, diagnostics_json
        ) VALUES (%s,%s,%s,%s::jsonb,%s::jsonb)
        """,
        (
            parse_run_id,
            digest,
            record_count,
            json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            json.dumps(diagnostics, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        ),
    )
    return digest, False


def _ensure_capture_link(cur, capture_id: str, parse_run_id, input_label: str) -> bool:
    cur.execute(
        """
        INSERT INTO source.capture_parse_run(capture_id, parse_run_id, input_label)
        VALUES (%s,%s,%s)
        ON CONFLICT DO NOTHING
        RETURNING capture_id
        """,
        (capture_id, parse_run_id, input_label),
    )
    return cur.fetchone() is None


def persist_parse_snapshot(
    conn,
    *,
    capture_id: str | None = None,
    capture_inputs: list[dict[str, str]] | None = None,
    parser_name: str,
    parser_revision: str,
    code_revision: str,
    configuration_hash: str,
    started_at: datetime,
    completed_at: datetime,
    records: list[dict[str, Any]],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    """Persist one complete private interpretation snapshot for archived input captures.

    The caller owns the transaction. This function never acquires source bytes,
    creates a SourceEdition or publishes facts. Every selected capture must already
    be bound to a durably persisted ContentObject. Scalar callers may keep using
    ``capture_id``; bundle parsers use labelled ``capture_inputs``.
    """
    parser_name = _required_text(parser_name, "parser_name")
    parser_revision = _required_text(parser_revision, "parser_revision")
    code_revision = _required_text(code_revision, "code_revision")
    configuration_hash = _required_text(configuration_hash, "configuration_hash")
    if not _GIT_SHA_RE.fullmatch(code_revision):
        raise ValueError("code_revision must be an exact 40-character lowercase Git SHA")
    if completed_at < started_at:
        raise ValueError("completed_at must not precede started_at")
    # Validate and hash the complete parser output before any database write.
    canonical_snapshot_bytes(records, diagnostics)

    with conn.cursor() as cur:
        inputs = _resolve_capture_inputs(
            cur, capture_id=capture_id, capture_inputs=capture_inputs
        )
        parse_run_id, parse_run_code, parse_run_reused = _ensure_parse_run(
            cur,
            inputs=inputs,
            parser_name=parser_name,
            parser_revision=parser_revision,
            code_revision=code_revision,
            configuration_hash=configuration_hash,
            started_at=started_at,
            completed_at=completed_at,
        )
        digest, snapshot_reused = _ensure_snapshot(
            cur, parse_run_id, records, diagnostics
        )
        link_reuse = {
            item["label"]: _ensure_capture_link(
                cur, item["capture_id"], parse_run_id, item["label"]
            )
            for item in inputs
        }

    primary = inputs[0]
    return {
        # Established scalar compatibility fields remain the first labelled input.
        "capture_id": primary["capture_id"],
        "content_object_id": str(primary["content_object_id"]),
        "capture_inputs": [
            {
                "label": item["label"],
                "capture_id": item["capture_id"],
                "content_object_id": str(item["content_object_id"]),
                "sha256": item["content_sha256"],
            }
            for item in inputs
        ],
        "parse_run_id": str(parse_run_id),
        "parse_run_code": parse_run_code,
        "snapshot_sha256": digest,
        "record_count": len(records),
        "parse_run_reused": parse_run_reused,
        "snapshot_reused": snapshot_reused,
        "capture_link_reused": all(link_reuse.values()),
        "capture_links_reused": link_reuse,
    }


def _load_snapshot_envelope(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Snapshot input must be one JSON object")
    common = {
        "parser_name",
        "parser_revision",
        "code_revision",
        "configuration_hash",
        "started_at",
        "completed_at",
        "records",
        "diagnostics",
    }
    keys = set(payload)
    if keys == common | {"capture_id"}:
        return payload
    if keys == common | {"capture_inputs"}:
        return payload
    raise ValueError(
        "Snapshot input must contain the processing/output fields plus exactly one of capture_id or capture_inputs"
    )


def persist_from_path(dsn: str, snapshot_path: Path) -> dict[str, Any]:
    if psycopg is None:
        raise RuntimeError("psycopg is required; install the 'database' extra") from _IMPORT_ERROR
    payload = _load_snapshot_envelope(snapshot_path)
    started_at = _parse_time(payload["started_at"], "started_at")
    completed_at = _parse_time(payload["completed_at"], "completed_at")
    records = payload["records"]
    diagnostics = payload["diagnostics"]
    if not isinstance(records, list):
        raise ValueError("records must be a JSON array")
    if not isinstance(diagnostics, dict):
        raise ValueError("diagnostics must be a JSON object")
    with psycopg.connect(dsn) as conn:
        result = persist_parse_snapshot(
            conn,
            capture_id=payload.get("capture_id"),
            capture_inputs=payload.get("capture_inputs"),
            parser_name=payload["parser_name"],
            parser_revision=payload["parser_revision"],
            code_revision=payload["code_revision"],
            configuration_hash=payload["configuration_hash"],
            started_at=started_at,
            completed_at=completed_at,
            records=records,
            diagnostics=diagnostics,
        )
        conn.commit()
        return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Persist a complete immutable parser observation snapshot for archived capture inputs."
    )
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    result = persist_from_path(args.dsn, args.snapshot)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
