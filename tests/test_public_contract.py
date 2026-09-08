import copy
import json
import subprocess
from pathlib import Path

import pytest

from white_list_archive.publishing.public_contract import public_record, validate_registry

ROOT = Path(__file__).resolve().parents[1]


def record():
    return dict(record_locator="a:2026-08-03:1", source_key="a", authority_key="a",
                register_key="r", source_status="listed", reference_date="2026-08-03",
                source_row_ordinal=1, capture_sha256="hash", name="Example",
                identifiers=[{"raw_value": "123", "candidate_schemes": ["IT_CF"]}],
                requested_activities=["Transport"], source_fields={"outcome": {"dates": []}})


@pytest.mark.parametrize("location", ["record", "identifier", "outcome", "date"])
def test_unapproved_nested_fields_fail_closed(location):
    r = record()
    targets = {"record": r, "identifier": r["identifiers"][0], "outcome": r["source_fields"]["outcome"]}
    if location == "date":
        targets[location] = {}
        r["source_fields"]["outcome"]["dates"].append(targets[location])
    targets[location]["reviewer_private_notes"] = "must never leave the internal archive"
    with pytest.raises(ValueError, match="Unapproved"):
        public_record(r)


def test_approved_company_observation_is_preserved_exactly():
    r = record()
    assert public_record(copy.deepcopy(r)) == r


def test_summary_counts_observations_not_unique_names_and_separates_dates():
    r = record()
    other = {**r, "record_locator": "b:2026-09-05:1", "source_key": "b", "authority_key": "b", "reference_date": "2026-09-05"}
    data = {"records": [r, other], "meta": {"record_count": 9999, "sources": [{"document_checked_at": "2026-09-08T01:00:00Z"}, {"document_checked_at": "2026-09-08T01:01:00Z"}]}}
    script = "const {archiveSummary}=require('./public-site/summary.js');let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>console.log(JSON.stringify(archiveSummary(JSON.parse(s),{prefectures:[{}, {}, {}]}))));"
    result = json.loads(subprocess.check_output(["node", "-e", script], input=json.dumps(data), text=True, cwd=ROOT))
    assert result == {"observations": 2, "authorities": 2, "registers": 1, "documents": 2, "earliest": "2026-08-03", "latest": "2026-09-05", "documentsCheckedAt": "2026-09-08T01:00:00Z", "directoryAuthorities": 3}


def test_registry_aggregate_and_source_identity_reconcile():
    r = record()
    data = {"records": [r], "meta": dict(record_count=1, authority_count=1, register_count=1, source_count=1,
        authority_counts={"a": 1}, register_counts={"r": 1}, status_counts={"listed": 1},
        sources=[dict(source_key="a", reference_date="2026-08-03", sha256="hash")])}
    validate_registry(data)
    bad = copy.deepcopy(data)
    bad["meta"]["record_count"] = 2
    with pytest.raises(ValueError):
        validate_registry(bad)
    bad = copy.deepcopy(data)
    bad["meta"]["sources"][0]["sha256"] = "different"
    with pytest.raises(ValueError):
        validate_registry(bad)
