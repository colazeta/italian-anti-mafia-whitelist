"""Immutable private capture/check metadata stored beside content-addressed evidence.

A ContentObject answers which bytes were acquired. This catalogue answers when and
from which locator one acquisition occurred. The identities are deliberately
separate: repeated acquisition of unchanged bytes reuses the ContentObject but
creates a new capture record.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import re
from uuid import UUID

from white_list_archive.storage.evidence import EvidenceStore, freeze_capture_manifest, object_key

_SOURCE_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_EXISTING_CODES = {"PreconditionFailed", "412", "ObjectLockedByBucketPolicy", "10069"}


def _canonical_json(value: dict) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _manifest_sha256(manifest: dict) -> str:
    # Must match EvidenceStore.archive's receipt definition exactly.
    return hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def capture_record_key(record: dict) -> str:
    source_key = record.get("source_key")
    capture_id = record.get("capture_id")
    if not isinstance(source_key, str) or _SOURCE_KEY.fullmatch(source_key) is None:
        raise ValueError("Invalid source_key for capture catalogue")
    if not isinstance(capture_id, str):
        raise ValueError("Capture id must be a canonical UUID string")
    try:
        parsed = UUID(capture_id)
    except ValueError as exc:
        raise ValueError("Capture id must be a canonical UUID string") from exc
    if str(parsed) != capture_id:
        raise ValueError("Capture id must be a canonical UUID string")
    return f"captures/v1/{source_key}/{capture_id}.json"


def freeze_capture_record(manifest: dict, content_receipt: dict) -> dict:
    """Bind one immutable acquisition/check to one already verified ContentObject."""
    frozen = freeze_capture_manifest(manifest)
    capture_record_key(frozen)
    required_receipt = {"sha256", "byte_size", "manifest_sha256", "verified_at"}
    if required_receipt - content_receipt.keys():
        raise ValueError("Content archive receipt is incomplete")
    if content_receipt["sha256"] != frozen["sha256"] or content_receipt["byte_size"] != frozen["byte_size"]:
        raise ValueError("Capture provenance and ContentObject receipt disagree")
    if content_receipt["manifest_sha256"] != _manifest_sha256(frozen):
        raise ValueError("Content archive receipt does not bind the frozen capture manifest")
    verified_at = content_receipt["verified_at"]
    try:
        verified = datetime.fromisoformat(str(verified_at).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid ContentObject verification timestamp") from exc
    if verified.tzinfo is None or verified.utcoffset() is None:
        raise ValueError("ContentObject verification timestamp requires timezone")

    record = {
        "schema_version": 1,
        "capture_id": frozen["capture_id"],
        "source_key": frozen["source_key"],
        "resource_url": frozen["resource_url"],
        "resolved_url": frozen.get("resolved_url"),
        "captured_at": frozen["captured_at"],
        "reference_date": frozen["reference_date"],
        "http_status": frozen.get("http_status"),
        "etag": frozen.get("etag"),
        "last_modified": frozen.get("last_modified"),
        "content_type": frozen["content_type"],
        "sha256": frozen["sha256"],
        "byte_size": frozen["byte_size"],
        "content_object_key": object_key(frozen),
        "capture_manifest_sha256": content_receipt["manifest_sha256"],
        "content_verified_at": str(verified_at),
    }
    return json.loads(_canonical_json(record))


def _validate_catalogue_receipt(receipt: dict, manifest: dict) -> tuple[dict, str]:
    if not isinstance(receipt, dict):
        raise ValueError("Capture catalogue receipt must be a mapping")
    required = {
        "schema_version", "capture_id", "source_key", "sha256", "byte_size",
        "catalogue_key", "catalogue_record_sha256", "created", "content_object_key",
    }
    if set(receipt) != required or receipt["schema_version"] != 1:
        raise ValueError("Unapproved capture catalogue receipt shape")
    frozen = freeze_capture_manifest(manifest)
    key = capture_record_key(frozen)
    if receipt["catalogue_key"] != key:
        raise ValueError("Capture catalogue receipt key disagrees with capture identity")
    if receipt["capture_id"] != frozen["capture_id"] or receipt["source_key"] != frozen["source_key"]:
        raise ValueError("Capture catalogue receipt belongs to another capture")
    if receipt["sha256"] != frozen["sha256"] or receipt["byte_size"] != frozen["byte_size"]:
        raise ValueError("Capture catalogue receipt disagrees with ContentObject identity")
    if receipt["content_object_key"] != object_key(frozen):
        raise ValueError("Capture catalogue receipt points to another ContentObject")
    digest = receipt["catalogue_record_sha256"]
    if not isinstance(digest, str) or _HEX.fullmatch(digest) is None:
        raise ValueError("Invalid capture catalogue record digest")
    if type(receipt["created"]) is not bool:
        raise ValueError("Capture catalogue creation flag must be boolean")
    return frozen, key


class CaptureCatalogue:
    """Private, conditional-write catalogue of capture/check provenance."""

    def __init__(self, store: EvidenceStore):
        self.store = store

    def read_verified(self, record: dict) -> dict:
        frozen = json.loads(_canonical_json(record))
        key = capture_record_key(frozen)
        expected = _canonical_json(frozen)
        response = self.store.client.get_object(Bucket=self.store.config.bucket, Key=key)
        stream = response["Body"]
        try:
            data = stream.read(len(expected) + 1)
        finally:
            stream.close()
        if data != expected:
            raise ValueError("Stored capture provenance failed immutable readback verification")
        try:
            decoded = json.loads(data)
        except json.JSONDecodeError as exc:  # pragma: no cover - byte comparison normally catches this
            raise ValueError("Stored capture provenance is not valid JSON") from exc
        if decoded != frozen:
            raise ValueError("Stored capture provenance changed during JSON round-trip")
        return decoded

    def verify_receipt(self, manifest: dict, receipt: dict) -> dict:
        """Verify that a release-selected capture has durable provenance, not only bytes."""
        frozen, key = _validate_catalogue_receipt(receipt, manifest)
        response = self.store.client.get_object(Bucket=self.store.config.bucket, Key=key)
        stream = response["Body"]
        try:
            data = stream.read(262_145)
        finally:
            stream.close()
        if len(data) > 262_144:
            raise ValueError("Stored capture provenance exceeds the approved size limit")
        if hashlib.sha256(data).hexdigest() != receipt["catalogue_record_sha256"]:
            raise ValueError("Stored capture provenance digest differs from release receipt")
        try:
            record = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Stored capture provenance is not valid JSON") from exc
        expected = {
            "capture_id": frozen["capture_id"],
            "source_key": frozen["source_key"],
            "resource_url": frozen["resource_url"],
            "resolved_url": frozen.get("resolved_url"),
            "captured_at": frozen["captured_at"],
            "reference_date": frozen["reference_date"],
            "http_status": frozen.get("http_status"),
            "etag": frozen.get("etag"),
            "last_modified": frozen.get("last_modified"),
            "content_type": frozen["content_type"],
            "sha256": frozen["sha256"],
            "byte_size": frozen["byte_size"],
            "content_object_key": object_key(frozen),
            "capture_manifest_sha256": _manifest_sha256(frozen),
        }
        if not isinstance(record, dict) or record.get("schema_version") != 1:
            raise ValueError("Stored capture provenance has an unsupported schema")
        if any(record.get(field) != value for field, value in expected.items()):
            raise ValueError("Stored capture provenance disagrees with frozen release capture")
        try:
            verified = datetime.fromisoformat(str(record.get("content_verified_at", "")).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Stored capture provenance has invalid verification time") from exc
        if verified.tzinfo is None or verified.utcoffset() is None:
            raise ValueError("Stored capture provenance verification time requires timezone")
        return record

    def record(self, manifest: dict, content_receipt: dict) -> dict:
        """Persist and independently read back capture provenance before parsing may start."""
        record = freeze_capture_record(manifest, content_receipt)
        key = capture_record_key(record)
        body = _canonical_json(record)
        created = True
        try:
            self.store.client.put_object(
                Bucket=self.store.config.bucket,
                Key=key,
                Body=body,
                ContentType="application/json",
                IfNoneMatch="*",
                Metadata={"sha256": hashlib.sha256(body).hexdigest()},
            )
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            code = str(code) if code is not None else None
            if code not in _EXISTING_CODES:
                raise
            created = False
        self.read_verified(record)
        return {
            "schema_version": 1,
            "capture_id": record["capture_id"],
            "source_key": record["source_key"],
            "sha256": record["sha256"],
            "byte_size": record["byte_size"],
            "catalogue_key": key,
            "catalogue_record_sha256": hashlib.sha256(body).hexdigest(),
            "created": created,
            "content_object_key": record["content_object_key"],
        }
