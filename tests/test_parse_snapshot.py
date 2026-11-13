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

def test_integer_section_counter_hash_survives_json_roundtrip():
    records = [{'source_status': 'listed', 'source_fields': {'sections': ['I']}}]
    diagnostics = {'parser': 'grosseto_listed', 'section_counts': {n: n+2 for n in range(1, 11)}}
    payload = json.loads(json.dumps({'records': records, 'diagnostics': diagnostics}))
    assert snapshot_sha256(records, diagnostics) == snapshot_sha256(payload['records'], payload['diagnostics'])
    assert diagnostics['section_counts'][10] == 12  # No mutation of caller's counter.


def test_retained_legacy_counter_digest_requires_exact_full_original_bytes():
    import hashlib
    from copy import deepcopy
    from white_list_archive.persistence.parse_snapshot import snapshot_digest_matches
    records = [{'source_status': 'listed', 'source_fields': {'physical_locator': 'sheet:R1'}}]
    diagnostics = {'parser': 'grosseto_listed', 'section_counts': {n: n+2 for n in range(1, 11)}}
    old_digest = hashlib.sha256(json.dumps({'records': records, 'diagnostics': diagnostics},
        sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    stored = json.loads(json.dumps(diagnostics))
    assert old_digest != snapshot_sha256(records, stored)
    assert snapshot_digest_matches(records, stored, old_digest)
    changed = deepcopy(records)
    changed[0]['source_status'] = 'pending'
    assert not snapshot_digest_matches(changed, stored, old_digest)
    stored['section_counts']['10'] += 1
    assert not snapshot_digest_matches(records, stored, old_digest)
    stored['parser'] = 'unreviewed_parser'
    assert not snapshot_digest_matches(records, stored, old_digest)
