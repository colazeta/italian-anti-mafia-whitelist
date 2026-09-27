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
_MAX_RECORD_BYTES = 262_144


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
    """Bind one immutable acquisition/check to one already verified ContentObject.

    New records embed the complete frozen manifest as well as the historical
    denormalised fields. The nested copy makes optional/future capture provenance
    independently recoverable when relational persistence is unavailable.
    """
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
        "capture_manifest": frozen,
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


def _validate_stored_record(record: dict, frozen: dict) -> None:
    """Validate immutable capture identity while allowing explicit legacy v1 records.

    Records written before complete-manifest preservation lack ``capture_manifest``.
    They remain readable and are never rewritten in place. Their manifest digest and
    denormalised fields still have to bind the exact supplied historical manifest.
    """
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
    if "capture_manifest" in record and record["capture_manifest"] != frozen:
        raise ValueError("Stored complete capture manifest disagrees with frozen capture")
    try:
        verified = datetime.fromisoformat(str(record.get("content_verified_at", "")).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Stored capture provenance has invalid verification time") from exc
    if verified.tzinfo is None or verified.utcoffset() is None:
        raise ValueError("Stored capture provenance verification time requires timezone")


class CaptureCatalogue:
    """Private, conditional-write catalogue of capture/check provenance."""

    def __init__(self, store: EvidenceStore):
        self.store = store

    def _read_record(self, key: str) -> tuple[bytes, dict]:
        response = self.store.client.get_object(Bucket=self.store.config.bucket, Key=key)
        stream = response["Body"]
        try:
            data = stream.read(_MAX_RECORD_BYTES + 1)
        finally:
            stream.close()
        if len(data) > _MAX_RECORD_BYTES:
            raise ValueError("Stored capture provenance exceeds the approved size limit")
        try:
            decoded = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Stored capture provenance is not valid JSON") from exc
        if not isinstance(decoded, dict):
            raise ValueError("Stored capture provenance must be a JSON object")
        return data, decoded

    def read_verified(self, record: dict) -> dict:
        frozen = json.loads(_canonical_json(record))
        key = capture_record_key(frozen)
        expected = _canonical_json(frozen)
        data, decoded = self._read_record(key)
        if data != expected:
            raise ValueError("Stored capture provenance failed immutable readback verification")
        if decoded != frozen:
            raise ValueError("Stored capture provenance changed during JSON round-trip")
        return decoded

    def verify_receipt(self, manifest: dict, receipt: dict) -> dict:
        """Verify that a release-selected capture has durable provenance, not only bytes."""
        frozen, key = _validate_catalogue_receipt(receipt, manifest)
        data, record = self._read_record(key)
        if hashlib.sha256(data).hexdigest() != receipt["catalogue_record_sha256"]:
            raise ValueError("Stored capture provenance digest differs from release receipt")
        _validate_stored_record(record, frozen)
        return record

    def record(self, manifest: dict, content_receipt: dict) -> dict:
        """Persist and independently read back capture provenance before parsing may start.

        A retry of the same capture/check never rewrites an existing catalogue object.
        ``content_verified_at`` is a processing/readback time rather than capture
        identity, so an existing valid record keeps its original verification time.
        """
        record = freeze_capture_record(manifest, content_receipt)
        frozen = freeze_capture_manifest(manifest)
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

        if created:
            self.read_verified(record)
            stored_record = record
            stored_body = body
        else:
            # Explicit compatibility path: pre-upgrade v1 catalogue records do not
            # contain the nested complete manifest. Validate them against the frozen
            # manifest but never upgrade/overwrite the historical object in place.
            stored_body, stored_record = self._read_record(key)
            _validate_stored_record(stored_record, frozen)

        return {
            "schema_version": 1,
            "capture_id": stored_record["capture_id"],
            "source_key": stored_record["source_key"],
            "sha256": stored_record["sha256"],
            "byte_size": stored_record["byte_size"],
            "catalogue_key": key,
            "catalogue_record_sha256": hashlib.sha256(stored_body).hexdigest(),
            "created": created,
            "content_object_key": stored_record["content_object_key"],
        }
