"""Safety and regression tests for automatic private extraction of new source URLs."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from white_list_archive.acquisition import candidate_extract as c

HASH_OLD = "a" * 64
HASH_NEW = "b" * 64
SHA_CODE = "c" * 40
LANDING = "https://prefettura.interno.gov.it/it/prefetture/catania/white-list"
OLD_LIST = "https://prefettura.interno.gov.it/sites/default/files/18/2026-11/white-list-iscritti-aggiornato-06-novembre-2026.xlsx"
OLD_APPLICANTS = "https://prefettura.interno.gov.it/sites/default/files/18/2026-11/white-list-richiedenti-aggiornato-06-novembre-2026.xlsx"
NEW_LIST = "https://prefettura.interno.gov.it/sites/default/files/18/2026-11/white-list-iscritti-aggiornato-13-novembre-2026.xlsx"
NEW_APPLICANTS = "https://prefettura.interno.gov.it/sites/default/files/18/2026-11/white-list-richiedenti-aggiornato-13-novembre-2026.xlsx"


def _capture(sha=HASH_NEW, when="2026-11-13T12:00:00Z", source="catania-robot-discovery"):
    return {
        "source_key": source, "capture_id": "synthetic-capture-01",
        "sha256": sha, "byte_size": 200, "captured_at": when,
    }


def _fixture():
    listed = {
        "authority_key": "catania", "source_key": "catania-listed",
        "population_scope": "listed", "parser": "catania_listed_2026_11",
        "resource_url": OLD_LIST, "sha256": HASH_OLD,
        "reference_date": "2026-11-06", "expected_source_rows": 100,
    }
    applicants = {
        "authority_key": "catania", "source_key": "catania-applicants",
        "population_scope": "applicant", "parser": "catania_applicants_2026_11",
        "resource_url": OLD_APPLICANTS, "sha256": HASH_OLD,
        "reference_date": "2026-11-06",
    }
    state = {
        "schema_version": 1, "robots": {"catania": {
            "population_mapping_reviewed": True,
            "resources": {
                OLD_LIST: {"role": "source", "capture_history": [_capture()]},
                NEW_LIST: {"role": "candidate", "capture_history": [_capture()]},
                NEW_APPLICANTS: {"role": "candidate", "capture_history": [_capture()]},
            },
        }},
    }
    catalog = {
        "schema_version": 1,
        "robots": [{"authority_key": "catania",
                    "allowed_hosts": ["prefettura.interno.gov.it"],
                    "landing_pages": [LANDING]}],
    }
    return state, {"sources": [listed, applicants]}, catalog


def test_new_document_urls_route_to_unique_review_hypotheses_only():
    state, cfg, robots = _fixture()
    jobs, deferred = c.select_candidate_jobs(state, cfg, robots)
    assert not deferred
    assert {j["url"]: j["config"]["parser"] for j in jobs} == {
        NEW_LIST: "catania_listed_2026_11",
        NEW_APPLICANTS: "catania_applicants_2026_11",
    }
    assert {j["capture"]["source_key"] for j in jobs} == {"catania-robot-discovery"}
    assert all(j["capture"]["sha256"] == HASH_NEW for j in jobs)
    assert all(j["url"] not in {OLD_LIST, OLD_APPLICANTS} for j in jobs)


def test_does_not_bind_unknown_or_malicious_candidates():
    state, cfg, robots = _fixture()
    docs = state["robots"]["catania"]["resources"]
    docs["https://evil.example/white-list-iscritti.xlsx"] = {
        "role": "candidate", "capture_history": [_capture()]
    }
    docs["https://prefettura.interno.gov.it/sites/default/files/18/modello-white-list.xlsx"] = {
        "role": "candidate", "capture_history": [_capture()]
    }
    docs["https://prefettura.interno.gov.it/sites/default/files/18/white-list-iscritti.pdf"] = {
        "role": "candidate", "capture_history": [_capture()]
    }
    jobs, deferred = c.select_candidate_jobs(state, cfg, robots)
    assert len(jobs) == 2
    assert len(deferred) == 1
    assert deferred[0]["reason"] == "no_unique_parser_hypothesis"


def test_missing_or_wrong_capture_identity_cannot_be_extracted():
    state, cfg, robots = _fixture()
    source = state["robots"]["catania"]["resources"][NEW_LIST]
    source["capture_history"] = [_capture(source="catania-listed")]
    jobs, deferred = c.select_candidate_jobs(state, cfg, robots)
    assert len(jobs) == 1
    assert deferred == [{"reason": "missing_verified_discovery_capture"}]
    source["capture_history"] = [_capture(when="2026-11-13T12:00:00")]
    jobs, deferred = c.select_candidate_jobs(state, cfg, robots)
    assert len(jobs) == 1
    assert deferred == [{"reason": "missing_verified_discovery_capture"}]


def test_capture_chronology_uses_utc_not_lexicographic_order():
    state, cfg, robots = _fixture()
    item = state["robots"]["catania"]["resources"][NEW_LIST]
    older = {**_capture("e"*64, "2026-11-13T15:00:00+05:00"),
             "capture_id": "older"}
    newer = {**_capture("f"*64, "2026-11-13T12:00:00+00:00"),
             "capture_id": "newer"}
    item["capture_history"] = [newer, older]
    jobs, _ = c.select_candidate_jobs(state, cfg, robots)
    assert next(j for j in jobs if j["url"] == NEW_LIST)["capture"]["sha256"] == "f"*64


def test_ambiguous_parser_selection_never_promotes_a_candidate():
    state, cfg, robots = _fixture()
    cfg["sources"].append({
        **cfg["sources"][0], "source_key": "catania-other-listed",
        "parser": "another_listed_parser",
    })
    jobs, deferred = c.select_candidate_jobs(state, cfg, robots)
    assert len(jobs) == 1
    assert jobs[0]["source_key_hypothesis"] == "catania-applicants"
    assert deferred == [{"reason": "no_unique_parser_hypothesis"}]


class MissingObject(Exception):
    response = {"Error": {"Code": "NoSuchKey"}}


class ObjectExists(Exception):
    response = {"Error": {"Code": "PreconditionFailed"}}


class FakeClient:
    def __init__(self):
        self.objects = {}
        self.writes = 0

    def get_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise MissingObject()
        return {"Body": BytesIO(self.objects[Key])}

    def put_object(self, *, Bucket, Key, Body, ContentType, IfNoneMatch):
        assert Bucket == "protected"
        assert IfNoneMatch == "*"
        if Key in self.objects:
            raise ObjectExists()
        self.objects[Key] = Body
        self.writes += 1


def _store():
    return SimpleNamespace(client=FakeClient(), config=SimpleNamespace(bucket="protected"))


def test_archived_bytes_are_parsed_once_and_rows_stay_in_private_store(monkeypatch):
    state, cfg, robots = _fixture()
    jobs, _ = c.select_candidate_jobs(state, cfg, robots)
    job = next(j for j in jobs if j["url"] == NEW_LIST)
    store = _store()
    seen = []

    def verify(storage, entry):
        seen.append(("verified", entry["state"]["source_key"]))
        data = b"synthetic Excel contents"
        return ({
            "source_key": "catania-robot-discovery",
            "capture_id": "synthetic-capture-01",
            "sha256": HASH_NEW,
        }, {"receipt": "verified"}, data)

    class Batch:
        records = [
            {"parser_name": "catania_listed_2026_11",
             "parser_version": "2", "source_status": "listed",
             "name": "Private fixture firm", "identifiers": ["12345678901"]}
        ]
        diagnostics = {"public_records": 1, "sector_rows": 1, "dropped_date_rows": 0}

    monkeypatch.setattr(c, "_verified_capture", verify)
    from white_list_archive.publishing import public_national_registry as registry
    monkeypatch.setattr(registry, "_parse_source", lambda path, parse_cfg: (
        seen.append(("parsed", parse_cfg["reference_date"])) or Batch()
    ))
    first = c.extract_one(job, store=store, code_revision=SHA_CODE)
    assert first["status"] == "extracted_candidate_for_review"
    assert first["records"] == 1
    assert first["qa_flags"] == ["source_row_count_changed"]
    assert seen == [("verified", "catania-robot-discovery"), ("parsed", "")]
    assert store.client.writes == 1

    key, = store.client.objects
    payload = json.loads(store.client.objects[key])
    assert payload["records"][0]["name"] == "Private fixture firm"
    assert payload["identity"]["source_reference_date"] is None
    assert payload["identity"]["publication_approved"] is False
    assert payload["identity"]["capture_source_key"] == "catania-robot-discovery"
    assert payload["review_status"] == "unapproved_candidate_extraction"

    second = c.extract_one(job, store=store, code_revision=SHA_CODE)
    assert second["status"] == "reused_candidate_extraction"
    assert store.client.writes == 1
    assert seen == [("verified", "catania-robot-discovery"), ("parsed", "")]


def test_conflicting_existing_candidate_is_rejected_instead_of_overwritten():
    state, cfg, robots = _fixture()
    job = c.select_candidate_jobs(state, cfg, robots)[0][0]
    store = _store()
    identity = c._identity(job, SHA_CODE)
    key = c._key(identity)
    store.client.objects[key] = b'{"identity":{"fabricated":"yes"},"records":[]}'
    with pytest.raises(ValueError, match="Conflicting or damaged"):
        c._read_existing(store, key, identity)
    assert store.client.writes == 0


def test_private_report_cannot_expose_company_identifiers_or_promote_publication():
    aggregate = {"schema_version": 1, "shard": 0, "shards": 4,
                 "candidate_files": 1, "extracted": 1, "reused": 0,
                 "quarantined": 0, "blocked": 0, "deferred": 0,
                 "private_readback_verified": 1,
                 "source_quality_flags": 0, "publications": 0,
                 "outcomes": [{"source_key": "catania-listed",
                               "company_name": "Private fixture firm",
                               "tax_identifier": "12345678901"}]}
    public = c._public(aggregate)
    assert public["extracted"] == 1
    assert public["publications"] == 0
    assert "Private fixture firm" not in json.dumps(public)
    assert "12345678901" not in json.dumps(public)
    assert "outcomes" not in public


def test_candidate_extraction_is_wired_to_trusted_main_transform_and_never_pages():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/transform-reviewed-captures.yml").read_text()
    assert "candidate_extract" in workflow
    assert "--robot-catalog data/source_registry/prefecture_robots.json" in workflow
    assert "steps.load-capture-index.outcome == 'success'" in workflow
    assert "if: ${{ always()" in workflow
    assert "environment: evidence-archive" in workflow
    assert "Retain aggregate candidate-extraction status only" in workflow
    assert "actions/deploy-pages" not in workflow
