"""Conservative handoff tests for the 20 November Catania source-only probe."""
import hashlib
import json

from white_list_archive.acquisition import catania_november20_archive_qa as qa


def test_frozen_pair_and_no_self_approval():
    assert len(qa.PINS) == 2
    assert {(key, population) for key, population, _ in qa.PINS} == {
        ("catania-listed", "listed"),
        ("catania-applicants", "applicant"),
    }
    assert len({sha for _, _, sha in qa.PINS}) == 2
    assert all(len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)
               for _, _, sha in qa.PINS)
    assert qa._unavailable()["date_attribution_or_edition_approved"] is False
    assert qa._unavailable()["public_promotions"] == 0


def test_unavailable_store_never_claims_verified_originals():
    class BrokenStore:
        def read_digest_verified(self, digest):
            return b"unreviewed-source-bytes"

    result = qa.audit_archived_pair(BrokenStore())
    assert result["primary_originals_verified"] == 0
    assert result["provisional_extractions"] == 0
    assert all(x["primary_bytes"] == "unknown" for x in result["results"])
    assert result["scope"] == qa.SCOPE
    assert result["robot_discovery_revision"] == qa.ROBOT_STATE_REVISION
    assert result["date_attribution_or_edition_approved"] is False
    assert result["public_promotions"] == 0


def test_source_review_boundary_rejects_unexpected_approval(monkeypatch):
    def fake_audit(store, *, pins):
        return {
            "checked_pins": 2, "review_only": True,
            "capture_catalogue_verified_by_this_probe": False,
            "date_attribution_or_edition_approved": False,
            "postgresql_writes": 0, "public_promotions": 1,
            "results": [{"source_key": key, "population": pop}
                        for key, pop, sha in pins],
        }

    monkeypatch.setattr(qa, "audit_primary_archive", fake_audit)
    import pytest
    with pytest.raises(ValueError, match="review boundary"):
        qa.audit_archived_pair(object())


def test_main_infrastructure_failure_is_redacted(monkeypatch, capsys):
    from white_list_archive.storage import evidence
    def fail_env():
        raise RuntimeError("SECRET=private credential or URI")
    monkeypatch.setattr(evidence.StoreConfig, "from_env", fail_env)
    assert qa.main() == 0
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["primary_originals_verified"] == 0
    assert report["date_attribution_or_edition_approved"] is False
    assert report["public_promotions"] == 0
    assert "SECRET" not in output
    assert "private credential" not in output
