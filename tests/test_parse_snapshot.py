from __future__ import annotations

import json

import pytest

from white_list_archive.persistence.parse_snapshot import (
    _load_snapshot_envelope,
    _parse_run_code,
    canonical_snapshot_bytes,
    snapshot_sha256,
)


def test_snapshot_hash_is_canonical_but_preserves_record_order() -> None:
    left = [{"b": 2, "a": 1}, {"row": "second"}]
    same = [{"a": 1, "b": 2}, {"row": "second"}]
    reversed_rows = list(reversed(same))

    assert canonical_snapshot_bytes(left) == canonical_snapshot_bytes(same)
    assert snapshot_sha256(left) == snapshot_sha256(same)
    assert snapshot_sha256(left) != snapshot_sha256(reversed_rows)


def test_snapshot_requires_an_array_of_record_objects() -> None:
    with pytest.raises(ValueError, match="array of objects"):
        canonical_snapshot_bytes([{"ok": True}, "not-a-record"])  # type: ignore[list-item]

    with pytest.raises(ValueError):
        canonical_snapshot_bytes([{"not_finite": float("nan")}])


def test_parse_run_identity_changes_only_with_interpretation_inputs() -> None:
    base = dict(
        content_sha256="a" * 64,
        parser_name="example_parser",
        parser_revision="1",
        code_revision="b" * 40,
        configuration_hash="c" * 64,
    )
    first = _parse_run_code(**base)
    assert first == _parse_run_code(**base)

    for key, value in (
        ("content_sha256", "d" * 64),
        ("parser_revision", "2"),
        ("code_revision", "e" * 40),
        ("configuration_hash", "f" * 64),
    ):
        changed = dict(base)
        changed[key] = value
        assert _parse_run_code(**changed) != first


def test_snapshot_envelope_is_closed(tmp_path) -> None:
    payload = {
        "capture_id": "11111111-2222-4333-8444-555555555555",
        "parser_name": "example_parser",
        "parser_revision": "1",
        "code_revision": "a" * 40,
        "configuration_hash": "b" * 64,
        "started_at": "2026-09-23T05:00:00+00:00",
        "completed_at": "2026-09-23T05:00:01+00:00",
        "records": [{"source_fields": {"physical_locator": "row:1"}}],
    }
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert _load_snapshot_envelope(path) == payload

    payload["publication_date"] = "2026-09-23"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="fields must be exactly"):
        _load_snapshot_envelope(path)
