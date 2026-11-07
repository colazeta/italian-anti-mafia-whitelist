"""Bounded I/O retries and immutable, private quarantine first-observation receipts."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, Callable

_IO_STAGES = frozenset({"archive_integrity", "capture_persistence", "capture_readback",
                        "snapshot_reuse", "snapshot_persistence", "snapshot_readback"})
_SQLSTATES = frozenset({"40001", "40P01", "08000", "08003", "08006", "57P01", "57P02", "57P03"})


def transient_io_failure(exc: Exception, stage: str) -> bool:
    """Only typed transient errors at I/O boundaries qualify; messages are unused."""
    if stage not in _IO_STAGES:
        return False
    import psycopg
    from botocore.exceptions import ClientError, ConnectTimeoutError, EndpointConnectionError, ReadTimeoutError
    if isinstance(exc, psycopg.Error):
        return exc.sqlstate in _SQLSTATES
    if isinstance(exc, (ConnectTimeoutError, EndpointConnectionError, ReadTimeoutError)):
        return True
    if isinstance(exc, ClientError):
        response = exc.response
        return (response.get("ResponseMetadata", {}).get("HTTPStatusCode") in {429, 500, 502, 503, 504}
                or response.get("Error", {}).get("Code") in {"SlowDown", "RequestTimeout", "InternalError", "ServiceUnavailable"})
    return False


def with_bounded_retry(operation: Callable[[], dict], progress: dict,
                       *, sleep: Callable[[float], None] = time.sleep) -> dict:
    """Replay the idempotent archived-input operation at most three times."""
    for attempt in range(1, 4):
        progress["attempts"] = attempt
        try:
            result = operation()
            result["attempts"] = attempt
            return result
        except Exception as exc:
            if attempt == 3 or not transient_io_failure(exc, progress["stage"]):
                raise
            sleep(2 ** (attempt - 1))


def quarantine_age(store: Any, job: dict, outcome: dict, *, now: datetime | None = None) -> dict:
    """Age the same bytes/failure since this tracker first observed them.

    Receipts are private and append-only. Capture timestamps are never used as
    evidence of the first failure; code deployments do not reset the clock.
    """
    from botocore.exceptions import ClientError
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Quarantine clock must be timezone-aware")
    identity = {"schema_version": 1, "source_key": job["source_key"],
                "inputs": {label: part["state"]["sha256"] for label, part in job["captures"].items()},
                "stage": outcome["stage"], "reason": outcome["reason"],
                "error_type": outcome.get("error_type", "unspecified")}
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    key = "operations/v1/quarantine-first-observed/" + hashlib.sha256(canonical).hexdigest() + ".json"
    receipt = {"identity": identity, "first_observed_at": now.isoformat()}
    body = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    created = True
    try:
        store.client.put_object(Bucket=store.config.bucket, Key=key, Body=body,
                                ContentType="application/json", IfNoneMatch="*")
    except ClientError as exc:
        created = False
        if not (exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 412
                or exc.response.get("Error", {}).get("Code") == "PreconditionFailed"):
            raise
    stream = store.client.get_object(Bucket=store.config.bucket, Key=key)["Body"]
    try:
        raw = stream.read(16_385)
    finally:
        stream.close()
    if created and raw != body:
        raise ValueError("Quarantine receipt failed exact readback")
    if len(raw) > 16_384:
        raise ValueError("Quarantine receipt exceeds bound")
    saved = json.loads(raw)
    if set(saved) != {"identity", "first_observed_at"} or saved["identity"] != identity:
        raise ValueError("Quarantine receipt identity mismatch")
    first = datetime.fromisoformat(saved["first_observed_at"])
    if first.tzinfo is None or first > now:
        raise ValueError("Invalid quarantine observation chronology")
    return {"basis": "first_observed_by_tracker_v1", "first_observed_at": first.isoformat(),
            "observed_at": now.isoformat(), "age_seconds": int((now - first).total_seconds()),
            "verified": True}
