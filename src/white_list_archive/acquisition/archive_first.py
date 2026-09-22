"""Archive-first acquisition for official White List source payloads.

The parser boundary is deliberately after both ContentObject persistence/readback and
capture-provenance persistence/readback. Failed parsing or release construction may
therefore leave a quarantined durable capture, but can never make an acquired original
disappear merely because downstream processing failed.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen
from uuid import uuid4

from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for

USER_AGENT = "italian-anti-mafia-whitelist/0.1 (+archive-first acquisition)"


@dataclass(frozen=True)
class ArchivedCapture:
    path: Path
    manifest: dict
    content_receipt: dict
    catalogue_receipt: dict

    @property
    def sha256(self) -> str:
        return self.manifest["sha256"]


def _timestamp(value: datetime | None) -> str:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Capture timestamp requires an explicit timezone")
    return value.astimezone(timezone.utc).isoformat()


def archive_payload(
    *,
    data: bytes,
    source_key: str,
    resource_url: str,
    reference_date: str | None,
    content_type: str,
    store: EvidenceStore,
    work_dir: Path,
    captured_at: datetime | None = None,
    capture_id: str | None = None,
    resolved_url: str | None = None,
    http_status: int | None = None,
    etag: str | None = None,
    last_modified: str | None = None,
) -> ArchivedCapture:
    """Durably freeze bytes and acquisition provenance before returning parser input."""
    if not isinstance(data, bytes) or not data:
        raise ValueError("A non-empty byte payload is required")
    if not isinstance(resource_url, str) or not resource_url.startswith("https://"):
        raise ValueError("Official source resource URL must use HTTPS")
    if not isinstance(content_type, str) or not content_type.strip():
        raise ValueError("Content type is required")

    cid = capture_id or str(uuid4())
    captured = _timestamp(captured_at)
    digest = hashlib.sha256(data).hexdigest()
    manifest = {
        "schema_version": 2,
        "capture_id": cid,
        "source_key": source_key,
        "resource_url": resource_url,
        "resolved_url": resolved_url or resource_url,
        "captured_at": captured,
        "reference_date": reference_date,
        "http_status": http_status,
        "etag": etag,
        "last_modified": last_modified,
        "content_type": content_type,
        "sha256": digest,
        "byte_size": len(data),
    }

    # A staging path is not document identity. Use a fresh path even when a caller
    # deliberately reuses capture_id while testing immutability; never delete or
    # overwrite a recoverable local original merely to restart a transaction.
    work_dir.mkdir(parents=True, exist_ok=True)
    staging_id = uuid4()
    local_path = work_dir / f"{source_key}-{cid}-{staging_id}.source"
    with local_path.open("xb") as handle:
        handle.write(data)

    # EvidenceStore.archive validates/freezes provenance before transport, verifies the
    # local bytes, conditionally persists the ContentObject and performs a full GET.
    content_receipt = store.archive(local_path, manifest)
    readback = store.read_verified(manifest)
    if readback != data:
        raise ValueError("Durable ContentObject readback differs from acquired payload")

    # The capture/check remains a separate immutable object even when bytes were seen
    # before. Parsing is not allowed until this record itself has been read back.
    catalogue_receipt = CaptureCatalogue(store).record(manifest, content_receipt)
    return ArchivedCapture(
        path=local_path,
        manifest=manifest,
        content_receipt=content_receipt,
        catalogue_receipt=catalogue_receipt,
    )


def acquire_and_archive(
    *,
    source_key: str,
    resource_url: str,
    reference_date: str | None,
    store: EvidenceStore,
    work_dir: Path,
    fetch: Callable | None = None,
    now: Callable[[], datetime] | None = None,
) -> ArchivedCapture:
    """Retrieve one official URL and archive it before exposing a local parser path.

    The fetch callable is injectable for deterministic tests. Network or storage
    failures leave no parsed facts. A storage/catalogue failure intentionally leaves
    any already-created ContentObject untouched for later recovery.
    """
    if not resource_url.startswith("https://"):
        raise ValueError("Official source resource URL must use HTTPS")
    request = Request(resource_url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    opener = fetch or urlopen
    with opener(request, timeout=90) as response:  # noqa: S310 - caller supplies reviewed official URL
        data = response.read()
        headers = response.headers
        content_type = headers.get("Content-Type") or "application/octet-stream"
        final_url = response.geturl() if hasattr(response, "geturl") else resource_url
        status = getattr(response, "status", None)
        etag = headers.get("ETag")
        last_modified = headers.get("Last-Modified")
    clock = now or (lambda: datetime.now(timezone.utc))
    return archive_payload(
        data=data,
        source_key=source_key,
        resource_url=resource_url,
        reference_date=reference_date,
        content_type=content_type,
        store=store,
        work_dir=work_dir,
        captured_at=clock(),
        resolved_url=final_url,
        http_status=status,
        etag=etag,
        last_modified=last_modified,
    )


def public_capture_receipt(result: ArchivedCapture) -> dict:
    """Return capture metadata safe for a public-repository Actions artifact.

    Provider endpoint, bucket, policy locator and private storage URI are deliberately
    absent. The private catalogue already contains the full immutable capture record.
    """
    manifest = result.manifest
    return {
        "schema_version": 1,
        "capture_id": manifest["capture_id"],
        "source_key": manifest["source_key"],
        "resource_url": manifest["resource_url"],
        "resolved_url": manifest["resolved_url"],
        "captured_at": manifest["captured_at"],
        "reference_date": manifest["reference_date"],
        "content_type": manifest["content_type"],
        "sha256": manifest["sha256"],
        "byte_size": manifest["byte_size"],
        "http_status": manifest["http_status"],
        "durable_content_readback_verified": True,
        "durable_capture_provenance_readback_verified": True,
        "content_object_created": bool(result.content_receipt["created"]),
        "capture_record_created": bool(result.catalogue_receipt["created"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-key", required=True)
    parser.add_argument("--resource-url", required=True)
    parser.add_argument(
        "--reference-date",
        help="Declared source reference date (YYYY-MM-DD). Omit when unknown; capture time is separate.",
    )
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument(
        "--public-receipt",
        type=Path,
        required=True,
        help="New path for redacted capture metadata; original bytes are never written here.",
    )
    args = parser.parse_args(argv)
    if args.public_receipt.exists():
        parser.error("Public receipt path already exists; capture metadata is append-only")

    config = StoreConfig.from_env()
    result = acquire_and_archive(
        source_key=args.source_key,
        resource_url=args.resource_url,
        reference_date=args.reference_date or None,
        store=EvidenceStore(client_for(config), config),
        work_dir=args.work_dir,
    )
    args.public_receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.public_receipt.open("x", encoding="utf-8") as handle:
        json.dump(public_capture_receipt(result), handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print("Source bytes and capture provenance archived and independently read back.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
