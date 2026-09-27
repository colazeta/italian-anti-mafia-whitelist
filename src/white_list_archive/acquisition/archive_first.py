"""Archive-first acquisition for official White List source payloads.

The parser boundary is deliberately after both ContentObject persistence/readback and
capture-provenance persistence/readback. Failed parsing, relational persistence or
release construction may therefore leave a quarantined durable capture, but can never
make an acquired original disappear merely because downstream processing failed.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen
from uuid import uuid4

from white_list_archive.persistence.source_series_registration import (
    reviewed_source_series_context,
)
from white_list_archive.storage.capture_catalogue import CaptureCatalogue, capture_record_key
from white_list_archive.storage.evidence import (
    EvidenceStore,
    StoreConfig,
    client_for,
    freeze_capture_manifest,
)

USER_AGENT = "italian-anti-mafia-whitelist/0.1 (+archive-first acquisition)"
DEFAULT_AUTHORITY_REGISTRY = Path("data/source_registry/territorial_authorities.csv")
DEFAULT_SERIES_REGISTRY = Path("data/source_registry/source_series_inventory.csv")


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
    origin_type: str | None = None,
    authority_rank_code: str | None = None,
    resource_type_code: str | None = None,
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
    optional_provenance = {
        "origin_type": origin_type,
        "authority_rank_code": authority_rank_code,
        "resource_type_code": resource_type_code,
    }
    for field, value in optional_provenance.items():
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-blank string when supplied")
            manifest[field] = value

    # #164 froze the content-facing manifest before external storage, but the stable
    # capture/check identity is validated by the separate catalogue contract. Perform
    # both validations here before creating a staging file or writing a ContentObject,
    # so malformed SourceSeries/capture identity cannot leave an unbound durable object.
    manifest = freeze_capture_manifest(manifest)
    capture_record_key(manifest)

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
    origin_type: str | None = None,
    authority_rank_code: str | None = None,
    resource_type_code: str | None = None,
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
        origin_type=origin_type,
        authority_rank_code=authority_rank_code,
        resource_type_code=resource_type_code,
    )


def public_capture_receipt(
    result: ArchivedCapture,
    *,
    database_persistence_state: str = "not_attempted",
) -> dict:
    """Return capture metadata safe for the public-repository workflow log.

    Provider endpoint, bucket, policy locator and private storage URI are deliberately
    absent. The private catalogue already contains the full immutable capture record.
    """
    if database_persistence_state not in {
        "not_attempted",
        "writer_unavailable",
        "persisted",
        "failed",
    }:
        raise ValueError("Unsupported database persistence state")
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
        "origin_type": manifest.get("origin_type"),
        "authority_rank_code": manifest.get("authority_rank_code"),
        "resource_type_code": manifest.get("resource_type_code"),
        "durable_content_readback_verified": True,
        "durable_capture_provenance_readback_verified": True,
        "content_object_created": bool(result.content_receipt["created"]),
        "capture_record_created": bool(result.catalogue_receipt["created"]),
        "database_capture_persistence_state": database_persistence_state,
        "database_capture_persisted": database_persistence_state == "persisted",
    }


def _persist_if_configured(
    result: ArchivedCapture,
    store: EvidenceStore,
    *,
    authority_registry: Path = DEFAULT_AUTHORITY_REGISTRY,
    series_registry: Path = DEFAULT_SERIES_REGISTRY,
) -> tuple[str, bool]:
    """Persist relational provenance when a writer exists; never endanger archived bytes.

    Durable bytes and immutable capture provenance already exist before this function
    runs. When the reviewed SourceSeries is not yet present in the relational model,
    register its repository-reviewed authority/register/series metadata in the same
    transaction before binding the capture. This never turns a URL or date into
    document identity and never creates a SourceEdition.
    """
    dsn = os.environ.get("EVIDENCE_DATABASE_URL")
    if not dsn:
        return "writer_unavailable", False
    try:
        import psycopg
        from white_list_archive.persistence.archived_capture import persist_archived_capture
        from white_list_archive.persistence.source_series_registration import (
            ensure_registered_source_series,
        )

        with psycopg.connect(dsn) as conn:
            ensure_registered_source_series(
                conn,
                source_key=result.manifest["source_key"],
                authority_csv=authority_registry,
                series_csv=series_registry,
            )
            persist_archived_capture(conn, result, store)
            conn.commit()
    except Exception:
        # Do not echo a connection exception: it can contain private provider or DB
        # coordinates. The durable provider objects remain intact and recoverable.
        return "failed", True
    return "persisted", False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-key", required=True)
    parser.add_argument("--resource-url", required=True)
    parser.add_argument(
        "--reference-date",
        help="Declared source reference date (YYYY-MM-DD). Omit when unknown; capture time is separate.",
    )
    parser.add_argument(
        "--origin-type",
        default="official_current",
        help="Explicit evidence-origin classification stored with this capture.",
    )
    parser.add_argument(
        "--authority-rank-code",
        default="primary_official",
        help="Explicit evidence-authority rank stored with this capture.",
    )
    parser.add_argument(
        "--resource-type-code",
        default="other",
        help="Explicit locator/resource type; use 'other' when no narrower reviewed type is known.",
    )
    parser.add_argument(
        "--authority-registry",
        type=Path,
        default=DEFAULT_AUTHORITY_REGISTRY,
        help="Reviewed territorial-authority inventory used for source-identity preflight and relational registration.",
    )
    parser.add_argument(
        "--series-registry",
        type=Path,
        default=DEFAULT_SERIES_REGISTRY,
        help="Reviewed SourceSeries inventory used for source-identity preflight and relational registration.",
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

    # The protected CLI may only acquire into a SourceSeries already reviewed on the
    # executing repository revision. Validate this before network I/O, staging or
    # provider access. The exact resource URL is intentionally not compared with the
    # series_url locator: recurring series can move attachments without changing
    # logical SourceSeries identity, and the acquired URL is captured separately.
    reviewed_source_series_context(
        args.source_key,
        authority_csv=args.authority_registry,
        series_csv=args.series_registry,
    )

    config = StoreConfig.from_env()
    store = EvidenceStore(client_for(config), config)
    result = acquire_and_archive(
        source_key=args.source_key,
        resource_url=args.resource_url,
        reference_date=args.reference_date or None,
        store=store,
        work_dir=args.work_dir,
        origin_type=args.origin_type,
        authority_rank_code=args.authority_rank_code,
        resource_type_code=args.resource_type_code,
    )
    database_state, database_failed = _persist_if_configured(
        result,
        store,
        authority_registry=args.authority_registry,
        series_registry=args.series_registry,
    )

    args.public_receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.public_receipt.open("x", encoding="utf-8") as handle:
        json.dump(
            public_capture_receipt(result, database_persistence_state=database_state),
            handle,
            ensure_ascii=False,
            indent=2,
        )
        handle.write("\n")

    if database_failed:
        print(
            "Source bytes and capture provenance are durably archived, but relational "
            "capture persistence failed after readback; no downstream completion may be claimed."
        )
        return 2
    if database_state == "writer_unavailable":
        print(
            "Source bytes and capture provenance are durably archived; relational writer "
            "is unavailable, so database persistence remains an explicit debt."
        )
    else:
        print("Source bytes, capture provenance and relational capture were archived and read back.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
