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
        repository_root=tmp_path,
        monitoring_path=monitoring,
        captures_root=captures,
        generated_at="2026-09-23T00:30:00+00:00",
    )

    versions = result["known_versions"]
    assert result["recovery_search_complete"] is False
    assert result["published_release_scopes"] == []
    assert len(versions) == 4
    milano_checks = [row for row in versions if row["authority_key"] == "milano" and row["sha256"] == repeated]
    assert len(milano_checks) == 2
    assert all(row["source_key"] is None for row in milano_checks)
    assert len({row["evidence_version_key"] for row in milano_checks}) == 2
    assert all("data/monitoring/national_coverage.json#check-" in row["evidence_refs"][-1]
               for row in milano_checks)

    coverage = next(row for row in versions if row["sha256"] == coverage_only)
    assert coverage["source_key"] is None
    assert coverage["byte_size"] is None

    legacy = next(row for row in versions if row["sha256"] == legacy_sha)
    assert legacy["source_key"] == "cosenza-combined"
    assert legacy["byte_size"] == 1234
    assert legacy["evidence_version_key"] == "legacy-manifest:data/captures/cosenza/combined_2026-08-03.json"
    assert legacy["evidence_refs"] == ["data/captures/cosenza/combined_2026-08-03.json"]
    # The lower-specificity Cosenza known-hash inventory must not duplicate the manifest.
    assert len([row for row in versions if row["sha256"] == legacy_sha]) == 1


def test_equal_time_same_bytes_monitoring_checks_remain_distinct(tmp_path):
    monitoring = tmp_path / "data" / "monitoring" / "national_coverage.json"
    captures = tmp_path / "data" / "captures"
    digest = "a" * 64
    check = {
        "authority_key": "milano",
        "at": "2026-09-23T00:25:18Z",
        "evidence": "docs/sources/milano-transition.md",
        "content_sha256": digest,
    }
    write_json(
        monitoring,
        {
            "checks": [dict(check), dict(check)],
            "prefectures": [],
        },
    )

    result = build_repository_recovery_expectations(
        repository_root=tmp_path,
        monitoring_path=monitoring,
        captures_root=captures,
        generated_at="2026-09-23T01:15:00+00:00",
    )

    versions = result["known_versions"]
    assert len(versions) == 2
    assert {row["sha256"] for row in versions} == {digest}
    assert len({row["evidence_version_key"] for row in versions}) == 2
    assert versions[0]["evidence_refs"][-1].endswith("#check-0")
    assert versions[1]["evidence_refs"][-1].endswith("#check-1")


def test_public_history_is_release_scope_not_raw_content_version(tmp_path):
    monitoring = tmp_path / "data" / "monitoring" / "national_coverage.json"
    captures = tmp_path / "data" / "captures"
    history = tmp_path / "data" / "history" / "public_history.json"
    edition_id = "f" * 64
    document_digest = "e" * 64
    write_json(monitoring, {"checks": [], "prefectures": []})
    write_json(
        history,
        {
            "version": 1,
            "editions": [
                {
                    "id": edition_id,
                    "authority_key": "milano",
                    "source_key": "milano-combined",
                    "reference_date": "2026-09-22",
                    "reference_date_raw": "2026-09-22",
                    "document_sha256": document_digest,
                    "parser_signature": "milano-html@3",
                    "evidence": ["approved-public-registry"],
                }
            ],
            "checks": [
                {
                    "edition_id": edition_id,
                    "checked_at": "2026-09-22T19:00:00+00:00",
                    "kind": "approved_document_verification",
                }
            ],
            "comparisons": [],
        },
    )

    result = build_repository_recovery_expectations(
        repository_root=tmp_path,
        monitoring_path=monitoring,
        captures_root=captures,
        public_history_path=history,
        generated_at="2026-09-23T01:15:00+00:00",
    )

    assert result["known_versions"] == []
    assert len(result["published_release_scopes"]) == 1
    scope = result["published_release_scopes"][0]
    assert scope["history_edition_id"] == edition_id
    assert scope["document_digest"] == document_digest
    assert scope["digest_semantics"] == "public_history_document_digest"
    assert scope["raw_content_object_identity_established"] is False
    assert scope["successful_checks"] == [
        {
            "checked_at": "2026-09-22T19:00:00+00:00",
            "kind": "approved_document_verification",
            "evidence_ref": "data/history/public_history.json#check-0",
        }
    ]
    assert scope["evidence_refs"][-1] == f"data/history/public_history.json#edition-{edition_id}"


def test_public_history_duplicate_edition_identity_fails_closed(tmp_path):
    monitoring = tmp_path / "data" / "monitoring" / "national_coverage.json"
    captures = tmp_path / "data" / "captures"
    history = tmp_path / "data" / "history" / "public_history.json"
    edition_id = "f" * 64
    edition = {
        "id": edition_id,
        "authority_key": "milano",
        "source_key": "milano-combined",
        "reference_date": None,
        "reference_date_raw": "",
        "document_sha256": "e" * 64,
        "parser_signature": "milano-html@3",
        "evidence": [],
    }
    write_json(monitoring, {"checks": [], "prefectures": []})
    write_json(
        history,
        {
            "version": 1,
            "editions": [edition, dict(edition)],
            "checks": [],
            "comparisons": [],
        },
    )

    import pytest
    with pytest.raises(ValueError, match="unique SHA-256"):
        build_repository_recovery_expectations(
            repository_root=tmp_path,
            monitoring_path=monitoring,
            captures_root=captures,
            public_history_path=history,
            generated_at="2026-09-23T01:15:00+00:00",
        )


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
            repository_root=tmp_path,
            monitoring_path=monitoring,
            captures_root=captures,
            generated_at="2026-09-23T00:30:00+00:00",
        )


def test_repository_evidence_rejects_paths_outside_repository_root(tmp_path):
    repo = tmp_path / "repo"
    monitoring = tmp_path / "outside.json"
    write_json(monitoring, {"checks": [], "prefectures": []})

    import pytest
    with pytest.raises(ValueError, match="inside repository_root"):
        build_repository_recovery_expectations(
            repository_root=repo,
            monitoring_path=monitoring,
            captures_root=repo / "data" / "captures",
            generated_at="2026-09-23T00:30:00+00:00",
        )


def test_current_repository_recovery_evidence_reconciles_without_promoting_public_digests():
    root = Path(__file__).resolve().parents[1]
    result = build_repository_recovery_expectations(
        repository_root=root,
        monitoring_path=root / "data" / "monitoring" / "national_coverage.json",
        captures_root=root / "data" / "captures",
        public_history_path=root / "data" / "history" / "public_history.json",
        generated_at="2026-09-23T01:30:00+00:00",
    )

    assert result["recovery_search_complete"] is False
    assert result["known_versions"]
    assert result["published_release_scopes"]
    assert len({row["evidence_version_key"] for row in result["known_versions"]}) == len(result["known_versions"])
    assert len({row["history_edition_id"] for row in result["published_release_scopes"]}) == len(
        result["published_release_scopes"]
    )
    assert all(scope["raw_content_object_identity_established"] is False
               for scope in result["published_release_scopes"])
    raw_hashes = {row["sha256"] for row in result["known_versions"]}
    for scope in result["published_release_scopes"]:
        # A matching digest may exist in both evidence layers, but the release scope
        # remains separately typed and never creates a new raw recovery row.
        if scope["document_digest"] in raw_hashes:
            assert scope["digest_semantics"] == "public_history_document_digest"
