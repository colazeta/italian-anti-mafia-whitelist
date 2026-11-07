from datetime import datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from white_list_archive.acquisition.auto_transform import EditionReviewRequired
from white_list_archive.acquisition.transform_resilience import (
    quarantine_age, transient_io_failure, with_bounded_retry,
)


def test_retry_is_bounded_and_can_reuse_after_transient_commit_failure():
    progress = {"stage": "snapshot_readback"}
    calls, delays = [], []
    def operation():
        calls.append(1)
        if len(calls) < 3:
            raise EndpointConnectionError(endpoint_url="private-coordinate")
        return {"status": "reused_private_interpretation"}
    assert with_bounded_retry(operation, progress, sleep=delays.append)["attempts"] == 3
    assert delays == [1, 2]
    calls.clear()
    def failing():
        calls.append(1)
        raise EndpointConnectionError(endpoint_url="private-coordinate")
    with pytest.raises(EndpointConnectionError):
        with_bounded_retry(failing, progress, sleep=lambda _: None)
    assert len(calls) == 3


@pytest.mark.parametrize("stage,error", [
    ("parser_compatibility", EditionReviewRequired("private")),
    ("parsing", EndpointConnectionError(endpoint_url="private")),
    ("archive_integrity", RuntimeError("hash mismatch")),
    ("capture_persistence", ValueError("invalid input")),
])
def test_review_parser_and_integrity_failures_never_retry(stage, error):
    calls = []
    def operation():
        calls.append(1)
        raise error
    with pytest.raises(type(error)):
        with_bounded_retry(operation, {"stage": stage}, sleep=lambda _: pytest.fail("retry"))
    assert len(calls) == 1


def test_database_retry_requires_explicit_transient_sqlstate():
    import psycopg
    assert transient_io_failure(psycopg.errors.SerializationFailure(), "capture_persistence")
    assert not transient_io_failure(psycopg.OperationalError("TLS validation failed"), "capture_persistence")
    assert not transient_io_failure(psycopg.errors.InsufficientPrivilege(), "capture_persistence")


class Client:
    def __init__(self):
        self.objects = {}
    def put_object(self, **kw):
        assert kw["IfNoneMatch"] == "*"
        if kw["Key"] in self.objects:
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        self.objects[kw["Key"]] = kw["Body"]
    def get_object(self, **kw):
        return {"Body": BytesIO(self.objects[kw["Key"]])}


def test_ageing_retains_first_observation_and_distinguishes_changed_bytes():
    client = Client()
    store = SimpleNamespace(client=client, config=SimpleNamespace(bucket="private"))
    job = {"source_key": "synthetic", "captures": {"primary": {"state": {"sha256": "a" * 64}}}}
    outcome = {"stage": "parser_compatibility", "reason": "edition_bound_parser_requires_review"}
    now = datetime(2026, 11, 7, tzinfo=timezone.utc)
    first = quarantine_age(store, job, outcome, now=now)
    again = quarantine_age(store, job, outcome, now=now + timedelta(days=2))
    assert again["first_observed_at"] == first["first_observed_at"]
    assert again["age_seconds"] == 172800
    assert len(client.objects) == 1
    job["captures"]["primary"]["state"]["sha256"] = "b" * 64
    assert quarantine_age(store, job, outcome, now=now + timedelta(days=2))["age_seconds"] == 0
    assert len(client.objects) == 2
    assert b"company" not in b"".join(client.objects.values())


def test_ageing_corruption_fails_closed():
    client = Client()
    store = SimpleNamespace(client=client, config=SimpleNamespace(bucket="private"))
    job = {"source_key": "synthetic", "captures": {}}
    outcome = {"stage": "parsing", "reason": "stage_failed"}
    quarantine_age(store, job, outcome)
    key = next(iter(client.objects))
    client.objects[key] = b'{"identity":{},"first_observed_at":"2020-01-01T00:00:00+00:00"}'
    with pytest.raises(ValueError, match="identity"):
        quarantine_age(store, job, outcome)
