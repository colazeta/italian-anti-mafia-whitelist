"""Synthetic fail-closed regression tests for manifest-driven public candidate QA."""
import copy
import json

import pytest

from white_list_archive.publishing.public_candidate_gate import validate_public_candidate


def fixture(tmp_path):
    sources = [
        dict(source_key="a-listed", authority_key="a", register_key="ordinary-a",
             parser="parser_a", population_scope="listed", reference_date="2026-10-10",
             expected_source_rows=2, sha256="a"*64,
             source_page_url="https://example.org/a", resource_url="https://example.org/a.pdf"),
        dict(source_key="b-applicant", authority_key="b", register_key="ordinary-b",
             parser="parser_b", population_scope="applicant", reference_date="2026-11-12",
             expected_source_rows=1, sha256="b"*64,
             source_page_url="https://example.org/b", resource_url="https://example.org/b.pdf"),
    ]
    path=tmp_path / "approved.json"
    path.write_text(json.dumps(dict(sources=sources)))
    rows=[]
    for s in sources:
        for index in range(s["expected_source_rows"]):
            rows.append({**{key:s[key] for key in ("source_key","authority_key","register_key",
                 "population_scope","reference_date","source_page_url","resource_url")},
                 "record_locator":f"{s['source_key']}:{index}", "source_status":"listed" if index else "pending"})
    reports=[{**{key:s[key] for key in ("source_key","authority_key","register_key",
             "population_scope","reference_date","parser","sha256")},
             "document_checked_at":"2026-11-13T12:00:00Z"} for s in sources]
    registry={"records":rows,"meta":{"record_count":len(rows),"source_count":2,
            "authority_count":2,"register_count":2,
            "authority_counts":{"a":2,"b":1},"register_counts":{"ordinary-a":2,"ordinary-b":1},
            "status_counts":{"pending":2,"listed":1},"sources":reports}}
    directory={"meta":{"authority_count":3,"published_count":2,"mapped_count":2},
               "prefectures":[{"authority_key":"a","published":True},
                              {"authority_key":"b","published":True},
                              {"authority_key":"c","published":False}]}
    return path,registry,directory


def test_new_source_manifest_is_not_rejected_for_different_national_totals(tmp_path):
    path,registry,directory=fixture(tmp_path)
    assert validate_public_candidate(registry,directory,path) is False


@pytest.mark.parametrize("edit", [
    lambda c,r,p: r["records"].pop(),
    lambda c,r,p: r["records"][0].update(reference_date="2026-11-13"),
    lambda c,r,p: r["records"][0].update(authority_key="b"),
    lambda c,r,p: r["records"][0].update(record_locator=r["records"][1]["record_locator"]),
    lambda c,r,p: r["meta"].update(record_count=999),
    lambda c,r,p: r["meta"]["source_counts"].update(unknown=1) if "source_counts" in r["meta"] else r["meta"]["status_counts"].update(listed=8),
    lambda c,r,p: r["meta"]["sources"][0].update(sha256="c"*64),
    lambda c,r,p: r["meta"]["sources"][0].update(document_checked_at=""),
    lambda c,r,p: p["prefectures"][0].update(published=False),
    lambda c,r,p: p["prefectures"].append({"authority_key":"c","published":False}),
    lambda c,r,p: c["sources"].append(c["sources"][0]),
    lambda c,r,p: c["sources"][0].update(expected_source_rows=3),
])
def test_invalid_source_candidate_fails_closed(tmp_path,edit):
    path,reg,directory=fixture(tmp_path)
    cfg=json.loads(path.read_text())
    edit(cfg,reg,directory)
    path.write_text(json.dumps(cfg))
    with pytest.raises((ValueError,KeyError)):
        validate_public_candidate(reg,directory,path)


def test_semantic_source_may_have_new_raw_wrapper_without_claiming_new_reference(tmp_path):
    path,registry,directory=fixture(tmp_path)
    cfg=json.loads(path.read_text())
    cfg["sources"][0]["approval_mode"]="semantic_sha256"
    cfg["sources"][0]["semantic_sha256"]="c"*64
    path.write_text(json.dumps(cfg))
    # Semantic-mode input changes may be harmless at the *raw wrapper* level,
    # but source identity, reference date, parser, count and output remain pinned.
    registry["meta"]["sources"][0]["sha256"]="d"*64
    assert validate_public_candidate(registry,directory,path) is False
