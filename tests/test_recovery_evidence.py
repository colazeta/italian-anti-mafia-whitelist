from __future__ import annotations

import json
from pathlib import Path

from white_list_archive.storage.recovery_evidence import build_repository_recovery_expectations


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_repository_evidence_preserves_checks_and_legacy_manifests_without_inventing_series(tmp_path):
    monitoring = tmp_path / "data" / "monitoring" / "national_coverage.json"
    captures = tmp_path / "data" / "captures"
    repeated = "a" * 64
    coverage_only = "b" * 64
    legacy_sha = "c" * 64
    write_json(
        monitoring,
        {
            "checks": [
                {
                    "authority_key": "milano",
                    "at": "2026-09-21T07:06:22Z",
                    "evidence": "docs/sources/milano-transition.md",
                    "content_sha256": repeated,
                },
                {
                    "authority_key": "milano",
                    "at": "2026-09-21T18:35:20Z",
                    "evidence": "docs/sources/milano-transition.md",
                    "content_sha256": repeated,
                },
                {
                    "authority_key": "bari",
                    "at": "2026-09-08T19:46:34Z",
                    "evidence": "docs/sources/bari-check.md",
                    "content_sha256": None,
                },
            ],
            "prefectures": [
                {
                    "authority_key": "milano",
                    "known_content_sha256": [repeated, coverage_only],
                    "evidence": ["docs/sources/milano-transition.md"],
                },
                {
                    "authority_key": "cosenza",
                    "known_content_sha256": [legacy_sha],
                    "evidence": ["docs/sources/cosenza.md"],
                },
            ],
        },
    )
    write_json(
        captures / "cosenza" / "combined_2026-08-03.json",
        {
            "authority_key": "cosenza",
            "source_series_key": "cosenza-combined",
            "sha256": legacy_sha,
            "byte_size": 1234,
            "captured_at": "2026-09-06T18:25:37+00:00",
            "resource_url": "https://prefettura.example/cosenza.pdf",
        },
    )
    # Analytical JSON in the capture tree must not become a source version.
    write_json(captures / "cosenza" / "diff.json", {"sha256": "d" * 64, "byte_size": 1})

    result = build_repository_recovery_expectations(
        monitoring_path=monitoring,
        captures_root=captures,
        generated_at="2026-09-23T00:30:00+00:00",
    )

    versions = result["known_versions"]
    assert result["recovery_search_complete"] is False
    assert len(versions) == 4
    milano_checks = [row for row in versions if row["authority_key"] == "milano" and row["sha256"] == repeated]
    assert len(milano_checks) == 2
    assert all(row["source_key"] is None for row in milano_checks)
    assert len({row["evidence_version_key"] for row in milano_checks}) == 2

    coverage = next(row for row in versions if row["sha256"] == coverage_only)
    assert coverage["source_key"] is None
    assert coverage["byte_size"] is None

    legacy = next(row for row in versions if row["sha256"] == legacy_sha)
    assert legacy["source_key"] == "cosenza-combined"
    assert legacy["byte_size"] == 1234
    assert legacy["evidence_version_key"].startswith("legacy-manifest:")
    # The lower-specificity Cosenza known-hash inventory must not duplicate the manifest.
    assert len([row for row in versions if row["sha256"] == legacy_sha]) == 1


def test_repository_evidence_rejects_invalid_hashed_monitoring_check(tmp_path):
    monitoring = tmp_path / "data" / "monitoring" / "national_coverage.json"
    captures = tmp_path / "data" / "captures"
    write_json(
        monitoring,
        {
            "checks": [{"authority_key": "x", "at": "now", "content_sha256": "not-a-sha"}],
            "prefectures": [],
        },
    )

    import pytest
    with pytest.raises(ValueError, match="invalid content SHA-256"):
        build_repository_recovery_expectations(
            monitoring_path=monitoring,
            captures_root=captures,
            generated_at="2026-09-23T00:30:00+00:00",
        )
