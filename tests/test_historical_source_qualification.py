from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from white_list_archive.acquisition.historical_source_qualification import (
    _TARGETS, _qualify_one, inspect_lodi_qualifications,
)
from white_list_archive.acquisition.historical_object_audit import PINS


class FakeStore:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def read_digest_verified(self, digest):
        self.calls.append(digest)
        reply = self.responses[digest]
        if isinstance(reply, Exception):
            raise reply
        return reply


def fixture(spec, *, data=b"synthetic archival CSV"):
    chosen = dict(spec)
    chosen["sha256"] = hashlib.sha256(data).hexdigest()
    cfg = {
        "source_key": chosen["source_key"],
        "authority_key": "lodi",
        "population_scope": chosen["population_scope"],
        "reference_date": chosen["reference_date"],
        "sha256": chosen["sha256"],
        "parser": chosen["parser"],
    }
    return chosen, cfg


def fake_parser(spec, *, data):
    def parse(path: Path, cfg: dict):
        assert path.read_bytes() == data
        assert cfg["source_key"] == spec["source_key"]
        records = [
            {"source_status": status}
            for status, count in spec["statuses"].items()
            for _ in range(count)
        ]
        return SimpleNamespace(
            records=records, diagnostics={"status_counts": dict(spec["statuses"])}
        )
    return parse


def test_two_existing_historical_pins_match_reviewed_parser_contracts():
    assert tuple(spec["sha256"] for spec in _TARGETS) == (PINS[0][1], PINS[1][1])
    assert [spec["source_key"] for spec in _TARGETS] == ["lodi-listed", "lodi-applicants"]
    assert [spec["records"] for spec in _TARGETS] == [169, 6]
    assert sum(_TARGETS[0]["statuses"].values()) == 169
    assert sum(_TARGETS[1]["statuses"].values()) == 6


def test_byte_verified_strict_source_parser_reports_aggregate_only():
    for spec in _TARGETS:
        raw = ("synthetic-" + spec["source_key"]).encode()
        chosen, cfg = fixture(spec, data=raw)
        store = FakeStore({chosen["sha256"]: raw})
        result = _qualify_one(store, cfg, chosen, fake_parser(chosen, data=raw))
        assert result == {
            "scope": chosen["scope"],
            "status": "strict_parser_compatible_source_only",
            "primary_bytes_verified": True,
            "strict_parser_compatible": True,
            "document_occurrences": chosen["records"],
        }
        assert store.calls == [chosen["sha256"]]


def test_missing_or_unverified_bytes_do_not_start_parser_or_claim_loss():
    spec, cfg = fixture(_TARGETS[0])
    store = FakeStore({spec["sha256"]: ValueError("secret/private URL/row")})
    def forbidden_parser(*args):
        raise AssertionError("Must not parse unverified evidence")
    result = _qualify_one(store, cfg, spec, forbidden_parser)
    assert result["status"] == "primary_bytes_unknown"
    assert result["primary_bytes_verified"] is False
    assert result["strict_parser_compatible"] is False
    assert "secret" not in json.dumps(result)
    store.responses[spec["sha256"]] = b"wrong, private company source bytes"
    result = _qualify_one(store, cfg, spec, forbidden_parser)
    assert result["status"] == "primary_bytes_unknown"
    assert "private company" not in json.dumps(result)


def test_parser_error_is_redacted_and_keeps_original_byte_verdict():
    raw = b"private source data"
    spec, cfg = fixture(_TARGETS[1], data=raw)
    store = FakeStore({spec["sha256"]: raw})
    def reject(path, config):
        raise RuntimeError("unreviewed source row: confidential name/address")
    result = _qualify_one(store, cfg, spec, reject)
    assert result["status"] == "parser_review_required"
    assert result["primary_bytes_verified"] is True
    assert result["strict_parser_compatible"] is False
    assert result["document_occurrences"] is None
    assert "confidential" not in json.dumps(result)


def test_status_and_record_cardinality_drift_fail_closed():
    raw = b"synthetic"
    spec, cfg = fixture(_TARGETS[0], data=raw)
    store = FakeStore({spec["sha256"]: raw})
    def short_parser(path, config):
        return SimpleNamespace(
            records=[{"source_status": "listed"}] * 168,
            diagnostics={"status_counts": {"listed": 168}},
        )
    assert _qualify_one(store, cfg, spec, short_parser)["status"] == "parser_review_required"
    def wrong_status(path, config):
        return SimpleNamespace(
            records=[{"source_status": "listed"}] * 169,
            diagnostics={"status_counts": {"listed": 169}},
        )
    assert _qualify_one(store, cfg, spec, wrong_status)["strict_parser_compatible"] is False


def test_config_mismatch_and_duplicate_source_series_do_not_read_provider():
    raw = b"synthetic"
    spec, cfg = fixture(_TARGETS[1], data=raw)
    store = FakeStore({spec["sha256"]: raw})
    incorrect = {**cfg, "reference_date": "2026-11-13"}
    result = _qualify_one(store, incorrect, spec, fake_parser(spec, data=raw))
    assert result["status"] == "selection_unverified"
    assert not store.calls
    source_list = [{"source_key": "lodi-listed"}, {"source_key": "lodi-listed"}]
    safe = inspect_lodi_qualifications(store, {"sources": source_list})
    assert safe["checked_historical_sources"] == 2
    assert safe["strict_parser_compatible_source_only"] == 0
    assert safe["relational_source_observations_written"] == 0
    assert safe["administrative_editions_approved"] == 0
    assert safe["semantic_or_canonical_writes"] == 0
    assert safe["public_promotions"] == 0
    assert store.calls == []
