from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "data/captures/cosenza"


def _load(name: str) -> dict:
    return json.loads((CAPTURES / name).read_text(encoding="utf-8"))


def test_two_content_capture_manifests_are_frozen_and_distinct():
    june = _load("combined_2026-06-28.json")
    august = _load("combined_2026-08-03.json")

    assert june["sha256"] == "565a71d89c4d684b68303949974a6c63410b9432eefe9f3773ac540a4318a07d"
    assert august["sha256"] == "0d1ebcdaec25ea5a9f9dc859e2c68bea3ac72ceb988fed4eed4f8ba2ce338202"
    assert june["sha256"] != august["sha256"]
    assert june["text_sha256"] != august["text_sha256"]
    assert june["http_status"] == august["http_status"] == 200
    assert june["content_type"] == august["content_type"] == "application/pdf"
    assert june["page_count"] == august["page_count"] == 69
    assert june["byte_size"] == 1_072_912
    assert august["byte_size"] == 1_077_994
    assert june["captured_at"] and august["captured_at"]
    assert june["etag"] and august["etag"]
    assert june["last_modified"] and august["last_modified"]


def test_adjacent_editions_share_one_validated_structural_fingerprint():
    june = _load("combined_2026-06-28.json")
    august = _load("combined_2026-08-03.json")
    expected = "fbb124c5a43d26bef93316844b3021096060f7ed9d2cc0f8f6081f6df935dc97"
    assert june["schema_fingerprint"] == august["schema_fingerprint"] == expected
    assert june["processing_revision"] == august["processing_revision"]
    assert june["workflow_run_id"] == august["workflow_run_id"] == 34051655207
    assert june["raw_content_storage_status"] == august["raw_content_storage_status"] == "workflow_artifact_ephemeral"


def test_capture_source_series_is_registered():
    with (ROOT / "data/source_registry/source_series_inventory.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        series = {row["source_series_key"] for row in csv.DictReader(handle)}
    for manifest in [
        _load("combined_2026-06-28.json"),
        _load("combined_2026-08-03.json"),
    ]:
        assert manifest["source_series_key"] == "cosenza-combined"
        assert manifest["source_series_key"] in series
        assert manifest["authority_key"] == "cosenza"


def test_frozen_diff_matches_live_aggregate_result_and_guardrails():
    diff = _load("diff_2026-06-28_2026-08-03.json")
    assert diff["same_schema_fingerprint"] is True
    assert diff["records"] == {"before": 1325, "after": 1332, "net": 7}
    assert diff["mention_observations"] == {
        "added": 21,
        "disappeared": 14,
        "common": 1311,
        "record_content_changed": 67,
    }
    assert diff["identifier_observations"]["new_identifiers"] == 19
    assert diff["identifier_observations"]["disappeared_identifiers"] == 12
    assert diff["identifier_observations"]["stable_identifier_name_changes"] == 2
    assert diff["identifier_observations"]["ambiguous_identifiers"] == 1
    assert diff["source_status"]["changed_common_mentions"] == 55
    guardrails = " ".join(diff["interpretation_guardrails"])
    assert "not administrative registration/removal" in guardrails
    assert "not a legal-effect determination" in guardrails


def test_git_capture_tree_contains_no_raw_pdf_or_row_level_extracts():
    files = [p for p in (ROOT / "data/captures").rglob("*") if p.is_file()]
    assert not any(path.suffix.lower() == ".pdf" for path in files)
    assert not any(path.name in {"before_records.csv", "after_records.csv"} for path in files)
    assert all(path.stat().st_size < 100_000 for path in files)
