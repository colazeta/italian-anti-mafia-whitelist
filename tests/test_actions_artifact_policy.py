from __future__ import annotations

import json
from pathlib import Path

from white_list_archive.publishing.actions_verification import (
    cosenza_address_verification,
    pistoia_verification,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
POLICY = ROOT / "docs" / "architecture" / "actions-artifact-policy.json"


def _scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _action_step_indent(line: str, action: str) -> int | None:
    stripped = line.lstrip()
    indent = len(line) - len(stripped)
    if stripped == f"- uses: {action}":
        return indent
    if stripped == f"uses: {action}":
        # Named steps are encoded as `- name:` at the step indent and `uses:`
        # two spaces deeper. Stop scanning at the next sibling step.
        return max(0, indent - 2)
    return None


def _artifact_uploads() -> list[dict[str, str]]:
    uploads: list[dict[str, str]] = []
    action = "actions/upload-artifact@v4"
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        lines = workflow.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            step_indent = _action_step_indent(line, action)
            if step_indent is None:
                continue
            name = None
            artifact_path = None
            for following in lines[index + 1 :]:
                item = following.lstrip()
                indent = len(following) - len(item)
                if item.startswith("- ") and indent <= step_indent:
                    break
                if item.startswith("name:"):
                    name = _scalar(item.split(":", 1)[1])
                if item.startswith("path:"):
                    artifact_path = _scalar(item.split(":", 1)[1])
                    assert artifact_path not in {"", "|", ">"}, (
                        f"{workflow}: public artifact paths must be one explicit scalar path"
                    )
            assert name and artifact_path, f"{workflow}: upload-artifact needs explicit name/path"
            uploads.append(
                {
                    "workflow": str(workflow.relative_to(ROOT)),
                    "name": name,
                    "path": artifact_path,
                }
            )
    return uploads


def _pages_upload_paths() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    action = "actions/upload-pages-artifact@v4"
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        lines = workflow.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            step_indent = _action_step_indent(line, action)
            if step_indent is None:
                continue
            artifact_path = None
            for following in lines[index + 1 :]:
                item = following.lstrip()
                indent = len(following) - len(item)
                if item.startswith("- ") and indent <= step_indent:
                    break
                if item.startswith("path:"):
                    artifact_path = _scalar(item.split(":", 1)[1])
            assert artifact_path
            found.append((str(workflow.relative_to(ROOT)), artifact_path))
    return found


def test_every_actions_artifact_is_explicitly_classified():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    expected = {
        (item["workflow"], item["name"], item["path"])
        for item in policy["upload_artifacts"]
    }
    observed = {
        (item["workflow"], item["name"], item["path"])
        for item in _artifact_uploads()
    }
    assert observed == expected, (
        "GitHub Actions upload-artifact surfaces changed without updating the reviewed "
        f"publication policy. Missing from workflows={sorted(expected-observed)}; "
        f"unclassified in policy={sorted(observed-expected)}"
    )


def test_operational_artifacts_cannot_upload_internal_bundles():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    forbidden = (
        "data-explorer-preview",
        "source-pdfs",
        "review-pack",
        "address_results",
        "source_evidence",
        "/cosenza-capture/",
        "/cosenza-v2/",
        "source-occurrences",
    )
    for item in policy["upload_artifacts"]:
        assert "private" not in item["name"].casefold()
        if item["classification"] != "public_operational_verification":
            continue
        path = item["path"].casefold()
        assert not any(token in path for token in forbidden), item
        assert (
            "/public-actions/" in path
            or path == "/tmp/private-evidence-check/*.verification.json"
            or path == "/tmp/private-evidence-recovery/receipts/*.json"
        ), item


def test_pages_artifact_is_only_the_deliberate_public_site():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    expected = policy["pages_artifact"]
    assert _pages_upload_paths() == [(expected["workflow"], expected["path"])]
    assert expected["path"] == "public-site/"
    assert expected["classification"] == "deliberately_public_publication"


def test_pistoia_public_verification_drops_rows_urls_and_provider_coordinates(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    sample = tmp_path / "sample.csv"
    sample.write_text("source_address,entity_name\nPISTOIA Via Secret 1,Example SRL\n", encoding="utf-8")
    manifest.write_text(
        json.dumps(
            {
                "prefecture": "Pistoia",
                "region": "Toscana",
                "dataset_code": "INDIR_TOSC",
                "unique_source_backed_addresses": 287,
                "source_evidence": {
                    "pistoia-listed": {
                        "population_scope": "listed",
                        "reference_date": "2026-08-21",
                        "capture_sha256": "a" * 64,
                        "parsed_records": 272,
                        "exact_toscana_address_occurrences": 250,
                        "non_exact_or_non_toscana_occurrences": 22,
                        "resource_url": "https://do-not-publish.example/source.pdf",
                    }
                },
                "orchestration": {
                    "candidate": 5,
                    "not_found": 282,
                    "processed_address_count": 287,
                    "all_processed_addresses_accounted_for": True,
                    "public_nominatim_used": False,
                    "regions": [
                        {
                            "dataset_code": "INDIR_TOSC",
                            "provider_version": "v1",
                            "zip_sha256": "b" * 64,
                            "csv_sha256": "c" * 64,
                            "planned_address_count": 287,
                            "processed_address_count": 287,
                            "candidate": 5,
                            "not_found": 282,
                            "skipped_existing_count": 0,
                            "source_url": "https://provider-coordinate.example/secret",
                        }
                    ],
                },
                "review": {
                    "review_rows": 150,
                    "rows_with_source_evidence": 150,
                    "sample_sha256": "d" * 64,
                    "database_uuid_independent": True,
                },
                "validation": {"review_strata": {"not_found": 145, "matched_street": 5}},
                "review_status": "PACK_READY_REQUIRES_SUBSTANTIVE_REVIEW",
            }
        ),
        encoding="utf-8",
    )
    record = pistoia_verification(manifest=manifest, review_sample=sample)
    text = json.dumps(record, sort_keys=True)
    for secret in (
        "PISTOIA Via Secret 1",
        "Example SRL",
        "do-not-publish.example",
        "provider-coordinate.example",
        "source_url",
        "resource_url",
    ):
        assert secret not in text
    assert record["internal_review_rows_uploaded"] is False
    assert record["source_pdf_uploaded"] is False
    assert record["internal_output_bindings"]["review_sample"]["sha256"]


def test_cosenza_address_public_verification_binds_but_does_not_emit_rows(tmp_path: Path):
    summary = tmp_path / "summary.json"
    sample = tmp_path / "review.csv"
    results = tmp_path / "address_results.csv"
    frozen = tmp_path / "frozen.json"
    summary.write_text(
        json.dumps(
            {
                "total_canonical_addresses": 1298,
                "addresses_with_provider_match": 624,
                "match_rate_pct": 48.07,
                "not_found": 636,
                "not_found_rate_pct": 49.0,
                "errors": 0,
                "error_rate_pct": 0.0,
                "unprocessed": 38,
                "unprocessed_rate_pct": 2.93,
                "status_counts": {"candidate": 624, "not_found": 636, "unprocessed": 38},
                "precision_counts": {"civic_access": 309, "street": 225},
                "country_route_counts": {"italian_anncsu": 1260},
                "source_country_counts": {"UNKNOWN": 1297, "FR": 1},
                "derived_country_counts": {"IT": 1260, "UNKNOWN": 38},
                "effective_country_counts": {"IT": 1260, "FR": 1, "UNKNOWN": 37},
                "source_provider_country_conflicts": 0,
                "provider_endpoint_filter": "https://do-not-publish.example/anncsu",
            }
        ),
        encoding="utf-8",
    )
    sample.write_text("source_address\nCOSENZA Private Row 1\n", encoding="utf-8")
    results.write_text("source_address,entity\nCOSENZA Private Row 1,Example SRL\n", encoding="utf-8")
    frozen.write_text(
        json.dumps(
            {
                "review_rows": 150,
                "population": 1298,
                "candidate_population": 624,
                "candidate_sample_rows": 78,
                "candidate_review_complete": True,
                "candidate_weighted_precision_pct": 82.49,
                "candidate_coverage_pct": 48.07,
                "estimated_validated_yield_pct": 39.65,
                "precision_excludes_not_found": True,
                "strata": {},
            }
        ),
        encoding="utf-8",
    )
    record = cosenza_address_verification(
        summary=summary,
        review_sample=sample,
        address_results=results,
        frozen_review_summary=frozen,
    )
    text = json.dumps(record, sort_keys=True)
    assert "COSENZA Private Row 1" not in text
    assert "Example SRL" not in text
    assert "do-not-publish.example" not in text
    assert record["internal_output_bindings"]["full_address_results"]["sha256"]
    assert record["internal_review_rows_uploaded"] is False
