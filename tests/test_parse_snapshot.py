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
    diagnostics = {"public_records": 2, "warnings": []}

    assert canonical_snapshot_bytes(left, diagnostics) == canonical_snapshot_bytes(
        same, {"warnings": [], "public_records": 2}
    )
    assert snapshot_sha256(left, diagnostics) == snapshot_sha256(same, diagnostics)
    assert snapshot_sha256(left, diagnostics) != snapshot_sha256(reversed_rows, diagnostics)
    assert snapshot_sha256(left, diagnostics) != snapshot_sha256(
        left, {"public_records": 2, "warnings": ["changed"]}
    )


def test_snapshot_requires_records_and_diagnostics_json_shapes() -> None:
    with pytest.raises(ValueError, match="array of objects"):
        canonical_snapshot_bytes(
            [{"ok": True}, "not-a-record"], {}  # type: ignore[list-item]
        )

    with pytest.raises(ValueError, match="diagnostics must be a JSON object"):
        canonical_snapshot_bytes([{"ok": True}], [])  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        canonical_snapshot_bytes([{"not_finite": float("nan")}], {})


def test_parse_run_identity_changes_only_with_interpretation_inputs() -> None:
    base = dict(
        content_inputs=[("primary", "a" * 64)],
        parser_name="example_parser",
        parser_revision="1",
        code_revision="b" * 40,
        configuration_hash="c" * 64,
    )
    first = _parse_run_code(**base)
    assert first == _parse_run_code(**base)

    for key, value in (
        ("content_inputs", [("primary", "d" * 64)]),
        ("parser_revision", "2"),
        ("code_revision", "e" * 40),
        ("configuration_hash", "f" * 64),
    ):
        changed = dict(base)
        changed[key] = value
        assert _parse_run_code(**changed) != first

    bundle = dict(base)
    bundle["content_inputs"] = [("applicants", "d" * 64), ("listed", "a" * 64)]
    bundle_id = _parse_run_code(**bundle)
    assert bundle_id != first
    assert bundle_id == _parse_run_code(**bundle)


def test_snapshot_envelope_is_closed_for_scalar_and_bundle_inputs(tmp_path) -> None:
    payload = {
        "capture_id": "11111111-2222-4333-8444-555555555555",
        "parser_name": "example_parser",
        "parser_revision": "1",
        "code_revision": "a" * 40,
        "configuration_hash": "b" * 64,
        "started_at": "2026-09-23T05:00:00+00:00",
        "completed_at": "2026-09-23T05:00:01+00:00",
        "records": [{"source_fields": {"physical_locator": "row:1"}}],
        "diagnostics": {"public_records": 1},
    }
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert _load_snapshot_envelope(path) == payload

    bundle = dict(payload)
    bundle.pop("capture_id")
    bundle["capture_inputs"] = [
        {"label": "listed", "capture_id": "11111111-2222-4333-8444-555555555555"},
        {"label": "applicants", "capture_id": "66666666-7777-4888-8999-000000000000"},
    ]
    path.write_text(json.dumps(bundle), encoding="utf-8")
    assert _load_snapshot_envelope(path) == bundle

    bundle["publication_date"] = "2026-09-23"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one of capture_id or capture_inputs"):
        _load_snapshot_envelope(path)