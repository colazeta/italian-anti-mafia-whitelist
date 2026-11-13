from __future__ import annotations

import hashlib
import json

import pytest

from white_list_archive.acquisition.historical_object_audit import (
    PINS, inspect_primary_store, MAX_EXPECTED_SOURCE_BYTES,
)


class FakeStore:
    def __init__(self, responses):
        self.responses = responses
        self.reads = []

    def read_digest_verified(self, digest):
        self.reads.append(digest)
        answer = self.responses[digest]
        if isinstance(answer, Exception):
            raise answer
        return answer


def test_primary_readback_requires_actual_bytes_and_preserves_source_boundaries():
    # Synthetic bytes are bound to fresh test-only SHA values, not production evidence.
    payloads = [f"synthetic-{i}".encode() for i in range(4)]
    pins = tuple((f"test-scope-{i}", hashlib.sha256(raw).hexdigest())
                 for i, raw in enumerate(payloads))
    store = FakeStore({sha: raw for (_, sha), raw in zip(pins, payloads)})
    result = inspect_primary_store(store, pins)
    assert result["verified_primary_r2"] == 4
    assert result["unknown_or_unverified"] == 0
    assert store.reads == [sha for _, sha in pins]
    assert all(x["verification"] == "verified_primary_r2" for x in result["results"])
    assert result["database_writes"] == result["source_captures_created"] == 0
    assert result["public_promotions"] == 0
    assert result["catalogue_provenance_verified"] is False
    assert result["independent_backup_or_restore_verified"] is False
    assert result["parser_or_edition_approved"] is False


def test_errors_and_wrong_bytes_never_create_verified_claim_or_leak_details():
    payloads = [f"private-input-{i}".encode() for i in range(4)]
    pins = tuple((f"reviewed-{i}", hashlib.sha256(raw).hexdigest())
                 for i, raw in enumerate(payloads))
    store = FakeStore({
        pins[0][1]: payloads[0],
        pins[1][1]: ValueError("private-endpoint/secret/private-name"),
        pins[2][1]: b"wrong bytes with private row",
        pins[3][1]: b"",
    })
    result = inspect_primary_store(store, pins)
    assert result["verified_primary_r2"] == 1
    assert result["unknown_or_unverified"] == 3
    assert [x["primary_bytes_verified"] for x in result["results"]] == [True, False, False, False]
    safe = json.dumps(result)
    for secret in ("private-endpoint", "secret", "private-name", "wrong bytes", "private row"):
        assert secret not in safe
    assert result["postgresql_persistence_verified_by_this_check"] is False


def test_pin_validation_precedes_external_reads():
    store = FakeStore({})
    with pytest.raises(ValueError):
        inspect_primary_store(store, [PINS[0]] * 4)
    with pytest.raises(ValueError):
        inspect_primary_store(store, [(f"test-{i}", PINS[0][1]) for i in range(4)])
    assert store.reads == []


def test_current_historical_pin_set_is_closed_and_distinct():
    assert len(PINS) == len(set(PINS)) == 4
    assert all(len(digest) == 64 for _, digest in PINS)
    assert MAX_EXPECTED_SOURCE_BYTES == 8_000_000
