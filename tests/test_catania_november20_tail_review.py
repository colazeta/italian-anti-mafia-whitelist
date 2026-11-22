"""Synthetic-only private review acceptance for the 20 Nov Catania tail.

Never upload real records or expose a workbook cell through CI/log output.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
from types import SimpleNamespace

import openpyxl
import pytest

from white_list_archive.acquisition import catania_november20_tail_review as wrapper
from white_list_archive.acquisition import catania_tail_private_review as legacy
from white_list_archive.parsers.catania_candidate import HEADERS


class Locked(Exception):
    response = {"Error": {"Code": "ObjectLockedByBucketPolicy"}}


class PrivateStore:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.objects = {}
        self.writes = 0
        self.config = SimpleNamespace(bucket="private")
        self.client = self

    def read_digest_verified(self, digest):
        return self.raw

    def put_object(self, *, Bucket, Key, Body, ContentType, IfNoneMatch):
        assert Bucket == "private" and IfNoneMatch == "*"
        self.writes += 1
        if Key in self.objects:
            raise Locked()
        self.objects[Key] = Body

    def get_object(self, *, Bucket, Key):
        assert Bucket == "private"
        return {"Body": BytesIO(self.objects[Key])}


def fabricated_source(*, full=1901, ambiguous=10):
    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.title = "Foglio1"
    header = [""] * 8
    for column, name in HEADERS["listed"].items():
        header[column] = name
    header[3] = "ATTIVITA' SOGGETTE"
    sheet.append(header)
    for i in range(full):
        sheet.append([f"FICTIONAL FIRM {i}", "FICTIONAL OFFICE", "", "1",
                      "12345678901", "", "", ""])
    for i in range(ambiguous):
        sheet.append([f"PRIVATE FICTIONAL TAIL {i}", "FICTIONAL OFFICE",
                      "", "", "", "", "", ""])
    out = BytesIO()
    wb.save(out)
    wb.close()
    return out.getvalue()


def test_exact_review_creates_one_private_packet_and_reuses_it(monkeypatch):
    raw = fabricated_source()
    sha = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(legacy, "NOV20_SHA256", sha)
    monkeypatch.setattr(wrapper, "PINS", (
        ("catania-listed", "listed", sha), ("catania-applicants", "applicant", "f" * 64),
    ))
    store = PrivateStore(raw)
    first = wrapper.stage_immutable_review(store)
    second = wrapper.stage_immutable_review(store)
    assert first["private_review_packet_verified"] is True
    assert first["private_review_packet_repeat_reused"] is True
    assert first["private_review_packet_created"] is True
    assert second["private_review_packet_created"] is False
    assert first["private_review_packet_sha256"] == second["private_review_packet_sha256"]
    assert first["full_signature_rows"] == 1901
    assert first["ambiguous_tail_rows"] == 10
    assert first["public_promotions"] == first["postgresql_writes"] == 0
    assert len(store.objects) == 1
    key = legacy._private_key(sha, review_scope=legacy.NOV20_SCOPE)
    assert "20261120" in key and key != legacy._private_key(sha)
    packet = json.loads(store.objects[key])
    assert packet["scope"] == legacy.NOV20_SCOPE
    assert packet["rows"][0]["cells"][0]["raw_value"] == "PRIVATE FICTIONAL TAIL 0"
    assert packet["publication_approved"] is False
    assert packet["no_edition_date_assigned"] is True
    summary = json.dumps(first) + json.dumps(second)
    assert "PRIVATE FICTIONAL" not in summary
    assert "physical_row" not in summary
    assert "operations/v1" not in summary


@pytest.mark.parametrize("kind", ["pin", "full", "tail"])
def test_wrong_pin_or_layout_refused_without_private_write(monkeypatch, kind):
    raw = fabricated_source(full=(1900 if kind == "full" else 1901),
                            ambiguous=(9 if kind == "tail" else 10))
    sha = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(legacy, "NOV20_SHA256",
                        ("0" * 64 if kind == "pin" else sha))
    monkeypatch.setattr(wrapper, "PINS", (
        ("catania-listed", "listed", sha), ("catania-applicants", "applicant", "f" * 64),
    ))
    store = PrivateStore(raw)
    with pytest.raises(ValueError):
        wrapper.stage_immutable_review(store)
    assert store.objects == {}


def test_old_packet_identity_is_unchanged():
    digest = "a" * 64
    identity = f"catania-listed-tail-review:v{legacy.REVIEW_VERSION}:{digest}"
    h = hashlib.sha256(identity.encode("ascii")).hexdigest()
    assert legacy._private_key(digest) == (
        f"operations/v1/catania-tail-review/{h[:2]}/{h}.json"
    )


def test_new_entrypoint_redacts_provider_exception(monkeypatch, capsys):
    from white_list_archive.storage import evidence

    def no_credentials():
        raise ValueError("PRIVATE SECRET SOURCE VALUES")

    monkeypatch.setattr(evidence.StoreConfig, "from_env", no_credentials)
    assert wrapper.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["scope"] == legacy.NOV20_SCOPE
    assert report["source_edition_approved"] is False
    assert report["private_review_packet_verified"] is False
    assert "SECRET" not in json.dumps(report)
