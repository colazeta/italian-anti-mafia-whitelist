"""No real company observations or original files are used in these regressions."""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from white_list_archive.acquisition import ascoli_private_snapshot_backfill as backfill


CAPTURE_ID = "11111111-1111-4111-8111-111111111111"
URL = "https://prefettura.interno.gov.it/sites/default/files/31/2026-08/elenco-degli-iscritti.pdf"


def source():
    return {
        "source_key": "ascoli-piceno-listed",
        "parser": "ascoli_piceno_listed",
        "authority_key": "ascoli-piceno",
        "register_key": "ascoli-piceno-ordinary",
        "population_scope": "listed",
        "reference_date": "2026-08-11",
        "sha256": backfill.APPROVED_SHA256,
        "expected_source_rows": 544,
        "resource_url": URL,
    }


def manifest():
    return {
        "source_key": backfill.REGISTERED_KEY,
        "capture_id": CAPTURE_ID,
        "sha256": backfill.APPROVED_SHA256,
        "byte_size": backfill.qa.EXPECTED_BYTES,
        "resource_url": URL,
        "reference_date": None,
        "http_status": 200,
        "origin_type": "official_current",
        "authority_rank_code": "primary_official",
        "resource_type_code": "pdf",
    }


def qa_receipt():
    return {
        "status": "strict_parser_compatible_source_only",
        "source_occurrences_strict_qa": 544,
        "immutable_capture_catalogue_status": "verified_immutable_capture_provenance",
        "catalogue_listing_complete": True,
        "verified_immutable_capture_checks": 1,
        "explicit_writer_provenance_ready_checks": 1,
    }


def fake_store(*, truncated=False, count=1):
    return SimpleNamespace(
        client=SimpleNamespace(list_objects_v2=lambda **kwargs: {
            "IsTruncated": truncated,
            "Contents": [
                {"Key": f"captures/v1/{backfill.REGISTERED_KEY}/{CAPTURE_ID}.json"}
                for _ in range(count)
            ],
        }),
        config=SimpleNamespace(bucket="private-bucket"),
    )


def test_catalogue_scan_requires_one_unique_complete_registered_capture(monkeypatch):
    monkeypatch.setattr(backfill, "CaptureCatalogue", lambda store: SimpleNamespace(
        _read_record=lambda key: (b"{}", {"sha256": backfill.APPROVED_SHA256})
    ))
    monkeypatch.setattr(backfill, "load_catalogued_capture",
                        lambda *args, **kwargs: (manifest(), {}))
    assert backfill._exact_catalogued_manifest(fake_store())["sha256"] == backfill.APPROVED_SHA256
    for store in (fake_store(truncated=True), fake_store(count=0), fake_store(count=2)):
        with pytest.raises(ValueError):
            backfill._exact_catalogued_manifest(store)


def test_selected_approved_input_remains_registered_capture_without_alias_relabel(monkeypatch):
    config = {"sources": [source()]}
    selected = config["sources"][0]
    monkeypatch.setattr(backfill.qa, "_selected", lambda c, i: selected)
    monkeypatch.setattr(backfill.qa, "inspect_ascoli_original", lambda *a: qa_receipt())
    monkeypatch.setattr(backfill, "_exact_catalogued_manifest", lambda store: manifest())
    job = backfill.build_exact_job(fake_store(), config, [])
    assert selected["source_key"] == "ascoli-piceno-listed"
    assert job["source_key"] == backfill.REGISTERED_KEY
    assert job["config"]["source_key"] == backfill.REGISTERED_KEY
    assert job["config"]["reference_date"] == "2026-08-11"
    assert job["captures"]["primary"]["state"]["capture_id"] == CAPTURE_ID
    assert job["captures"]["primary"]["state"]["sha256"] == backfill.APPROVED_SHA256
    assert job["config"] is not selected
    assert "publication_approved" not in job


@pytest.mark.parametrize("change", [
    ("sha256", "0"*64), ("resource_url", "https://another.example/file.pdf"),
    ("byte_size", 2), ("reference_date", "2026-11-15"),
    ("http_status", 404), ("origin_type", "unknown"),
    ("authority_rank_code", "third_party"), ("resource_type_code", ""),
])
def test_manifest_drift_fails_before_any_private_write(monkeypatch, change):
    selected = source()
    monkeypatch.setattr(backfill.qa, "_selected", lambda c, i: selected)
    monkeypatch.setattr(backfill.qa, "inspect_ascoli_original", lambda *a: qa_receipt())
    modified = manifest()
    modified[change[0]] = change[1]
    monkeypatch.setattr(backfill, "_exact_catalogued_manifest", lambda store: modified)
    with pytest.raises(ValueError):
        backfill.build_exact_job(fake_store(), {"sources": [selected]}, [])


@pytest.mark.parametrize("change", [
    ("status", "parser_review_required"),
    ("source_occurrences_strict_qa", 543),
    ("immutable_capture_catalogue_status", "unknown"),
    ("catalogue_listing_complete", False),
    ("verified_immutable_capture_checks", 0),
    ("explicit_writer_provenance_ready_checks", 0),
])
def test_incomplete_independent_qa_blocks_materialisation(monkeypatch, change):
    selected = source()
    report = qa_receipt()
    report[change[0]] = change[1]
    monkeypatch.setattr(backfill.qa, "_selected", lambda c, i: selected)
    monkeypatch.setattr(backfill.qa, "inspect_ascoli_original", lambda *a: report)
    monkeypatch.setattr(backfill, "_exact_catalogued_manifest",
                        lambda store: pytest.fail("Catalogue writer selection must not happen"))
    with pytest.raises(ValueError):
        backfill.build_exact_job(fake_store(), {"sources": [selected]}, [])


def test_private_materialisation_checks_prior_revisions_and_independent_readback(monkeypatch):
    job = {"source_key": backfill.REGISTERED_KEY, "config": source(), "captures": {}}
    monkeypatch.setattr(backfill, "build_exact_job", lambda *args: job)
    @contextmanager
    def connection(dsn):
        assert dsn == "secret-test-dsn"
        yield object()
    monkeypatch.setattr(backfill.transform, "private_connection", connection)
    seen = []
    def lookup(conn, row):
        seen.append("lookup")
        return len(seen) > 1
    monkeypatch.setattr(backfill, "existing_snapshot", lookup)
    calls = []
    def writer(row, **kwargs):
        calls.append(row)
        return {"status": "parsed_private_review_required", "records": 544,
                "database_readback": "verified", "database_tls_verified": True,
                "publication_approved": False, "qa_flags": []}
    monkeypatch.setattr(backfill.transform, "transform_one", writer)
    kw = {"authority_registry": Path("authorities.csv"), "series_registry": Path("series.csv")}
    result = backfill.materialise_exact_source(None, "secret-test-dsn", "a"*40, {}, [], **kw)
    assert result == {"status": "source_snapshot_verified", "existing_verified": 0,
                      "materialised": 1, "source_occurrences_verified": 544,
                      "publications": 0, "administrative_editions_approved": 0}
    assert len(calls) == 1 and seen == ["lookup", "lookup"]
    monkeypatch.setattr(backfill, "existing_snapshot", lambda *args: True)
    monkeypatch.setattr(backfill.transform, "transform_one",
                        lambda *args, **kwargs: pytest.fail("Existing must not reparse"))
    repeated = backfill.materialise_exact_source(None, "secret-test-dsn", "a"*40, {}, [], **kw)
    assert repeated["existing_verified"] == 1 and repeated["materialised"] == 0


def test_readback_or_publication_deviation_never_claims_materialisation(monkeypatch):
    monkeypatch.setattr(backfill, "build_exact_job", lambda *a: {"config": source(), "captures": {}})
    @contextmanager
    def connection(_):
        yield object()
    monkeypatch.setattr(backfill.transform, "private_connection", connection)
    monkeypatch.setattr(backfill, "existing_snapshot", lambda *a: False)
    monkeypatch.setattr(backfill.transform, "transform_one", lambda *a, **k: {
        "status": "parsed_private_review_required", "records": 544,
        "database_readback": "verified", "database_tls_verified": True,
        "publication_approved": True, "qa_flags": [],
    })
    with pytest.raises(ValueError):
        backfill.materialise_exact_source(None, "dsn", "a"*40, {}, [],
            authority_registry=Path("a"), series_registry=Path("b"))


def test_main_errors_are_redacted(monkeypatch, capsys):
    from white_list_archive.storage import evidence
    monkeypatch.setattr(evidence.StoreConfig, "from_env",
                        lambda: (_ for _ in ()).throw(RuntimeError("private archive secret")))
    assert backfill.main() == 1
    output = capsys.readouterr().out
    assert "private" not in output or "private archive secret" not in output
    assert "secret" not in output
    assert json.loads(output)["publications"] == 0
