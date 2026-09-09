import csv
import json
from pathlib import Path

import pytest

from white_list_archive.publishing.explorer_address_quality_patch import (
    build_quality_payload,
    patch_explorer,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _fixture_files(tmp_path: Path):
    results = tmp_path / "address_results.csv"
    _write_csv(
        results,
        [
            {
                "address_id": "1",
                "match_status": "candidate",
                "precision_code": "civic_access",
                "latitude": "39.1",
                "longitude": "16.2",
                "provider_name": "anncsu",
                "provider_version": "2026-08",
                "provider_data_updated": "2026-08-01",
                "provider_endpoint": "file://INDIR_CALA.csv",
            },
            {
                "address_id": "2",
                "match_status": "candidate",
                "precision_code": "street",
                "latitude": "39.2",
                "longitude": "16.3",
                "provider_name": "anncsu",
                "provider_version": "2026-08",
                "provider_data_updated": "2026-08-01",
                "provider_endpoint": "file://INDIR_CALA.csv",
            },
            {
                "address_id": "3",
                "match_status": "candidate",
                "precision_code": "unknown",
                "latitude": "",
                "longitude": "",
                "provider_name": "anncsu",
                "provider_version": "2026-08",
                "provider_data_updated": "2026-08-01",
                "provider_endpoint": "file://INDIR_CALA.csv",
            },
            {
                "address_id": "4",
                "match_status": "not_found",
                "precision_code": "",
                "latitude": "",
                "longitude": "",
                "provider_name": "anncsu",
                "provider_version": "2026-08",
                "provider_data_updated": "2026-08-01",
                "provider_endpoint": "file://INDIR_CALA.csv",
            },
        ],
    )
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "generated_at": "2026-09-09T10:00:00+00:00",
                "total_canonical_addresses": 4,
                "addresses_with_provider_match": 3,
                "status_counts": {"candidate": 3, "not_found": 1},
                "precision_counts": {"civic_access": 1, "street": 1, "unknown": 1},
                "provider_filter": "anncsu",
                "provider_endpoint_filter": "file://INDIR_CALA.csv",
            }
        ),
        encoding="utf-8",
    )
    frozen_summary = tmp_path / "review-summary.json"
    frozen_summary.write_text(
        json.dumps(
            {
                "population": 4,
                "candidate_population": 3,
                "candidate_coverage_pct": 75.0,
                "candidate_weighted_precision_pct": 83.33,
                "estimated_validated_yield_pct": 62.5,
                "not_found_population": 1,
                "precision_excludes_not_found": True,
                "strata": {
                    "matched_civic_access": {
                        "population": 1,
                        "sample": 1,
                        "correct": 1,
                        "incorrect": 0,
                        "review_completion_pct": 100.0,
                        "determinate_precision_pct": 100.0,
                        "is_candidate_stratum": True,
                    },
                    "matched_street": {
                        "population": 1,
                        "sample": 1,
                        "correct": 0,
                        "incorrect": 1,
                        "review_completion_pct": 100.0,
                        "determinate_precision_pct": 0.0,
                        "is_candidate_stratum": True,
                    },
                    "matched_without_coordinates": {
                        "population": 1,
                        "sample": 1,
                        "correct": 1,
                        "incorrect": 0,
                        "review_completion_pct": 100.0,
                        "determinate_precision_pct": 100.0,
                        "is_candidate_stratum": True,
                    },
                    "not_found": {
                        "population": 1,
                        "sample": 1,
                        "correct": 0,
                        "incorrect": 0,
                        "review_completion_pct": 0.0,
                        "determinate_precision_pct": None,
                        "is_candidate_stratum": False,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    frozen_metadata = tmp_path / "review-metadata.json"
    frozen_metadata.write_text(
        json.dumps(
            {
                "review_name": "Fixture substantive review",
                "review_date": "2026-09-07",
                "sample_fingerprint": "abcdef0123456789",
                "versioned_decision_file": "data/validation/fixture.csv",
                "population": 4,
            }
        ),
        encoding="utf-8",
    )
    return results, summary, frozen_summary, frozen_metadata


def _payload(tmp_path: Path):
    results, summary, frozen_summary, frozen_metadata = _fixture_files(tmp_path)
    return build_quality_payload(
        summary_path=summary,
        address_results_path=results,
        frozen_review_summary_path=frozen_summary,
        frozen_review_metadata_path=frozen_metadata,
        address_results_href="address-validation/address_results.csv",
    )


def test_quality_payload_reconciles_operational_and_review_metrics(tmp_path: Path):
    payload = _payload(tmp_path)
    op = payload["operational"]
    assert op["total_canonical_addresses"] == 4
    assert op["attempted"] == 4
    assert op["accounted"] == 4
    assert op["candidate"] == 3
    assert op["accepted"] == 0
    assert op["not_found"] == 1
    assert op["coordinate_bearing"] == 2
    assert op["normalisation_only"] == 1
    assert op["providers"][0]["provider_version"] == "2026-08"
    assert payload["frozen_review"]["candidate_weighted_precision_pct"] == 83.33


def test_quality_payload_fails_closed_on_count_mismatch(tmp_path: Path):
    results, summary, frozen_summary, frozen_metadata = _fixture_files(tmp_path)
    data = json.loads(summary.read_text(encoding="utf-8"))
    data["total_canonical_addresses"] = 5
    summary.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="do not match validation summary"):
        build_quality_payload(
            summary_path=summary,
            address_results_path=results,
            frozen_review_summary_path=frozen_summary,
            frozen_review_metadata_path=frozen_metadata,
            address_results_href="address-validation/address_results.csv",
        )


def test_quality_patch_adds_retro_metrics_and_drilldown(tmp_path: Path):
    index = tmp_path / "index.html"
    index.write_text(
        """<!doctype html><html><head><style>.x{}</style></head><body>
<div class=\"menubar\"><button class=\"tab\" data-view=\"address-validation\">Validazione indirizzi</button><button class=\"tab\" data-view=\"method\">Metodo</button></div>
<section class=\"view\" id=\"view-address-validation\"></section><section class=\"view\" id=\"view-method\"></section>
</body></html>""",
        encoding="utf-8",
    )
    patch_explorer(index, _payload(tmp_path))
    html_text = index.read_text(encoding="utf-8")
    assert 'data-view="address-quality"' in html_text
    assert 'id="view-address-quality"' in html_text
    assert "QUALITÀ NORMALIZZAZIONE INDIRIZZI" in html_text
    assert "Stato produzione" in html_text
    assert "GOLD STANDARD CONGELATO" in html_text
    assert "address-validation/address_results.csv" in html_text
    assert "Apri Validazione indirizzi" in html_text
