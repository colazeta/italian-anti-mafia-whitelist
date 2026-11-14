"""Synthetic-only checks for the closed Catania original-capture audit."""
from __future__ import annotations

import json

from white_list_archive.acquisition.catania_november13_archive_qa import PINS
from white_list_archive.storage import catania_capture_provenance_audit as audit


class EmptyCatalogue:
    def list_objects_v2(self, *, Bucket, Prefix, MaxKeys):
        assert Bucket == "private" and MaxKeys <= 64
        assert Prefix in (
            "captures/v1/catania-listed/",
            "captures/v1/catania-applicants/",
        )
        return {"Contents": [], "IsTruncated": False}


class EmptyStore:
    def __init__(self):
        self.client = EmptyCatalogue()
        self.config = type("Config", (), {"bucket": "private"})()


def test_only_two_exact_pins_not_the_approved_november_six_sources():
    assert audit.TARGETS == tuple(
        (series, f"{series}-13-november-2026", digest)
        for series, _population, digest in PINS
    )
    assert len(audit.TARGETS) == 2
    assert len({entry[2] for entry in audit.TARGETS}) == 2


def test_no_capture_manifest_is_unknown_even_when_original_digest_is_known():
    result = audit.audit_catania_capture_provenance(EmptyStore())
    assert result["scope"] == audit.SCOPE
    assert result["pins_with_verified_capture_provenance"] == 0
    assert result["checked_historical_pins"] == 2
    assert {r["status"] for r in result["results"]} == {"unknown"}
    assert all(r["bounded_catalogue_listing_complete"] for r in result["results"])
    assert result["postgresql_writer_or_commit_verified_here"] is False
    assert result["capture_or_database_writes"] == 0
    assert result["administrative_editions_approved"] == 0
    assert result["public_promotions"] == 0
    output = json.dumps(result)
    assert all(digest not in output for _, _, digest in audit.TARGETS)
    assert "captures/v1/" not in output


def test_provider_failure_returns_unknown_without_exposing_details(monkeypatch, capsys):
    from white_list_archive.storage import evidence
    def unavailable(*args, **kwargs):
        raise RuntimeError("sensitive private bucket URL")
    monkeypatch.setattr(evidence.StoreConfig, "from_env", unavailable)
    assert audit.main() == 0
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["checked_historical_pins"] == 2
    assert {r["status"] for r in report["results"]} == {"unknown"}
    assert report["capture_or_database_writes"] == 0
    assert "sensitive" not in output and "private bucket URL" not in output


def test_target_selection_reuses_existing_bounded_verifier(monkeypatch):
    calls = []
    def fake_verifier(store, *, targets):
        calls.append(targets)
        return {
            "schema_version": 1, "checked_historical_pins": 2,
            "pins_with_verified_capture_provenance": 1,
            "results": [{"scope": targets[0][1],
                         "status": "verified_immutable_capture_provenance",
                         "verified_capture_checks": 1}],
            "capture_or_database_writes": 0, "public_promotions": 0,
        }
    monkeypatch.setattr(audit, "audit_historical_catalogue", fake_verifier)
    report = audit.audit_catania_capture_provenance(object())
    assert calls == [audit.TARGETS]
    assert report["pins_with_verified_capture_provenance"] == 1
    assert report["public_promotions"] == 0
