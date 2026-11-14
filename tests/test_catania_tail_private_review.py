"""Synthetic-only contracts for the protected Catania tail-review packet."""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
from types import SimpleNamespace

import openpyxl
import pytest

from white_list_archive.acquisition.catania_tail_private_review import (
    prepare_private_tail_review, _private_key,
)
from white_list_archive.parsers.catania_candidate import HEADERS


class Locked(Exception):
    response = {"Error": {"Code": "ObjectLockedByBucketPolicy"}}


class MemoryClient:
    def __init__(self):
        self.objects = {}
        self.write_calls = 0

    def put_object(self, *, Bucket, Key, Body, ContentType, IfNoneMatch):
        assert Bucket == "private" and IfNoneMatch == "*"
        self.write_calls += 1
        if Key in self.objects:
            raise Locked()
        self.objects[Key] = Body

    def get_object(self, *, Bucket, Key):
        assert Bucket == "private"
        return {"Body": BytesIO(self.objects[Key])}


class Store:
    def __init__(self, raw):
        self.raw = raw
        self.client = MemoryClient()
        self.config = SimpleNamespace(bucket="private")

    def read_digest_verified(self, digest):
        return self.raw


def synthetic_xlsx(*, ambiguous=2, incomplete=False):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Foglio1"
    headers = [""] * 8
    for position, name in HEADERS["listed"].items():
        headers[position] = name
    headers[3] = "ATTIVITA' SOGGETTE"
    ws.append(headers)
    ws.append(["INVENTED A", "FICTIONAL TOWN", "", "1", "12345678901", "", "", ""])
    ws.append(["INVENTED B", "FICTIONAL TOWN", "", "2", "12345678901", "", "", ""])
    if incomplete:
        ws.append(["UNKNOWN", "OFFICE", "", "1", "", "", "", ""])
    for i in range(ambiguous):
        ws.append([f"PRIVATE SYNTHETIC {i}", "PRIVATE SYNTHETIC LOCATION",
                   "", "", "", "", "", ""])
    result = BytesIO()
    wb.save(result)
    wb.close()
    return result.getvalue()


def test_private_packet_contains_exact_source_cells_only_inside_protected_store():
    raw = synthetic_xlsx()
    sha = hashlib.sha256(raw).hexdigest()
    store = Store(raw)
    report = prepare_private_tail_review(
        store, source_sha=sha, expected_full=2, expected_ambiguous=2,
    )
    assert report["private_review_packet_created"] is True
    assert report["private_review_packet_verified"] is True
    assert report["ambiguous_tail_rows"] == 2
    assert report["public_promotions"] == report["postgresql_writes"] == 0
    assert store.client.write_calls == 1
    private = json.loads(store.client.objects[_private_key(sha)])
    assert len(private["rows"]) == 2
    assert private["rows"][0]["cells"][0]["raw_value"] == "PRIVATE SYNTHETIC 0"
    assert private["rows"][0]["physical_row"] == 4
    assert private["review_status"] == "requires_original_document_review"
    assert private["publication_approved"] is False
    assert "PRIVATE SYNTHETIC" not in json.dumps(report)
    assert "physical_row" not in json.dumps(report)
    assert "operations/v1/" not in json.dumps(report)


def test_identical_repeat_reuses_same_key_and_verified_bytes():
    raw = synthetic_xlsx()
    sha = hashlib.sha256(raw).hexdigest()
    store = Store(raw)
    first = prepare_private_tail_review(store, source_sha=sha, expected_full=2,
                                        expected_ambiguous=2)
    again = prepare_private_tail_review(store, source_sha=sha, expected_full=2,
                                        expected_ambiguous=2)
    assert first["private_review_packet_sha256"] == again["private_review_packet_sha256"]
    assert again["private_review_packet_created"] is False
    assert len(store.client.objects) == 1


def test_existing_conflicting_packet_is_never_overwritten():
    raw = synthetic_xlsx()
    sha = hashlib.sha256(raw).hexdigest()
    store = Store(raw)
    store.client.objects[_private_key(sha)] = b"wrong-content"
    with pytest.raises(ValueError, match="readback mismatch"):
        prepare_private_tail_review(store, source_sha=sha, expected_full=2,
                                    expected_ambiguous=2)
    assert store.client.objects[_private_key(sha)] == b"wrong-content"


@pytest.mark.parametrize("mutate", ["digest", "count", "incomplete"])
def test_unverified_or_new_layout_cannot_be_staged(mutate):
    raw = synthetic_xlsx(incomplete=(mutate == "incomplete"))
    sha = hashlib.sha256(raw).hexdigest()
    store = Store(raw)
    with pytest.raises(ValueError):
        prepare_private_tail_review(
            store,
            source_sha=("0" * 64 if mutate == "digest" else sha),
            expected_full=2 if mutate != "count" else 3,
            expected_ambiguous=2,
        )
    assert store.client.objects == {}


def test_non_utf_private_data_never_enters_public_summary():
    raw = synthetic_xlsx()
    sha = hashlib.sha256(raw).hexdigest()
    report = prepare_private_tail_review(Store(raw), source_sha=sha,
                                         expected_full=2, expected_ambiguous=2)
    text = json.dumps(report, ensure_ascii=False)
    assert "INVENTED" not in text and "FICTIONAL" not in text
    assert "PRIVATE" not in text and "row_number" not in text
