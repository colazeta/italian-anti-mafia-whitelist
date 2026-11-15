"""Ascoli exact-original QA regressions use synthetic source records only."""
from __future__ import annotations

from copy import deepcopy
import csv
import json
from pathlib import Path
from types import SimpleNamespace

from white_list_archive.acquisition import ascoli_private_source_qa as qa

ROOT = Path(__file__).resolve().parents[1]


def _config():
    config = json.loads((ROOT / "data/publication/multi_prefecture_pilot.json").read_text())
    with (ROOT / "data/source_registry/source_series_inventory.csv").open(newline="") as handle:
        inventory = list(csv.DictReader(handle))
    return config, inventory


def _batch():
    records = [
        {"source_status": "listed" if n < 448 else "renewal_update_in_progress",
         "requested_activities": ["Sezione I"], "decision_date": "2025-01-01",
         "observed_expiry_date": "2026-01-01", "identifier_field_raw": "synthetic"}
        for n in range(544)
    ]
    return SimpleNamespace(records=records, diagnostics={
        "public_records": 544, "status_counts": qa.EXPECTED_STATUSES,
        "identifier_raw_coverage": 544, "dropped_date_rows": 0,
    })


def test_exact_frozen_source_and_registered_comprehensive_scope():
    config, inventory = _config()
    assert qa._selected(config, inventory)["sha256"] == qa.APPROVED_SHA256
    assert qa.TARGETS == (("ascoli-piceno-listed-comprehensive", qa.SCOPE, qa.APPROVED_SHA256),)
    for field, other in (("source_key", "ascoli-piceno-applicants"),
                         ("reference_date", "2026-11-15"), ("sha256", "0" * 64),
                         ("parser", "unreviewed"), ("expected_source_rows", 545)):
        changed = deepcopy(config)
        next(row for row in changed["sources"] if row["source_key"] == qa.LEGACY_KEY)[field] = other
        assert qa._selected(changed, inventory) is None
    changed = deepcopy(inventory)
    next(row for row in changed if row["source_series_key"] == qa.REGISTERED_KEY)["sector_scope"] = "per_sector"
    assert qa._selected(config, changed) is None


def test_strict_source_denominators_dates_sectors_and_statuses():
    batch = _batch()
    assert qa._strict_batch_qa(batch)
    for mutation in ("drop_sector", "drop_date", "change_status", "change_count", "drop_identifier"):
        altered = _batch()
        if mutation == "drop_sector":
            altered.records[2]["requested_activities"] = []
        elif mutation == "drop_date":
            altered.records[2]["decision_date"] = ""
        elif mutation == "change_status":
            altered.records[2]["source_status"] = "unknown"
        elif mutation == "change_count":
            altered.records.pop()
        else:
            altered.diagnostics["identifier_raw_coverage"] = 543
        assert not qa._strict_batch_qa(altered)


class UnknownProvider:
    def read_digest_verified(self, digest):
        raise RuntimeError("private source row and private bucket URL")


def test_unavailable_original_is_unknown_not_a_parser_success(monkeypatch):
    config, inventory = _config()
    monkeypatch.setattr(qa, "audit_historical_catalogue", lambda store, *, targets: {
        "results": [{
            "status": "unknown", "bounded_catalogue_listing_complete": False,
            "verified_capture_checks": 0, "explicit_writer_provenance_ready_checks": 0,
        }],
    })
    output = qa.inspect_ascoli_original(UnknownProvider(), config, inventory)
    assert output["status"] == "primary_bytes_unknown"
    assert output["strict_parser_compatible_source_only"] is False
    assert output["source_occurrences_strict_qa"] is None
    assert output["capture_or_database_writes"] == 0
    assert "private" not in json.dumps(output)
    assert qa.APPROVED_SHA256 not in json.dumps(output)


def test_positive_synthetic_parser_and_negative_receipt_remain_separate(monkeypatch):
    config, inventory = _config()
    raw = b"%PDF-synthetic-no-individual-values"
    monkeypatch.setattr(qa, "EXPECTED_BYTES", len(raw))
    original_sha = qa.hashlib.sha256
    monkeypatch.setattr(qa.hashlib, "sha256", lambda value: SimpleNamespace(
        hexdigest=lambda: qa.APPROVED_SHA256 if value == raw else "0" * 64
    ))
    monkeypatch.setattr(qa, "parse_ascoli_piceno_listed", lambda path, cfg: _batch())
    monkeypatch.setattr(qa, "audit_historical_catalogue", lambda store, *, targets: {
        "results": [{
            "status": "unknown", "bounded_catalogue_listing_complete": True,
            "verified_capture_checks": 0, "explicit_writer_provenance_ready_checks": 0,
        }],
    })
    store = SimpleNamespace(read_digest_verified=lambda digest: raw)
    report = qa.inspect_ascoli_original(store, config, inventory)
    assert report["status"] == "strict_parser_compatible_source_only"
    assert report["primary_original_sha256_verified"] is True
    assert report["strict_parser_compatible_source_only"] is True
    assert report["source_occurrences_strict_qa"] == 544
    assert report["immutable_capture_catalogue_status"] == "unknown"
    assert report["verified_immutable_capture_checks"] == 0
    assert report["parse_snapshot_created"] is False
    assert report["administrative_editions_approved"] == 0
    assert report["public_promotions"] == 0


def test_unverified_selection_short_circuits_provider_reads():
    report = qa.inspect_ascoli_original(UnknownProvider(), {}, [])
    assert report["status"] == "selection_unverified"
    assert report["frozen_selection_accepted"] is False
    assert report["primary_original_sha256_verified"] is False


def test_main_provider_failure_is_redacted(monkeypatch, capsys):
    from white_list_archive.storage import evidence
    monkeypatch.setattr(evidence.StoreConfig, "from_env",
                        lambda: (_ for _ in ()).throw(ValueError("private endpoint")))
    assert qa.main() == 0
    output = capsys.readouterr().out
    assert "private endpoint" not in output
    assert json.loads(output)["capture_or_database_writes"] == 0
