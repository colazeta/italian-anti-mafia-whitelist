"""Persist an already archived capture without weakening the archive-first boundary.

This module deliberately starts *after* durable ContentObject and capture-catalogue
readback. It never downloads a live source and never creates an administrative
SourceEdition. A SourceSeries is logical membership, not document identity.
"""
from __future__ import annotations

from typing import Any

from white_list_archive.persistence.capture_manifest import (
    _canonical_capture_uuid,
    _parse_captured_at,
    _parse_last_modified,
    _parse_optional_date,
)
from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.evidence import EvidenceStore, freeze_capture_manifest, object_key


def _required_code(manifest: dict[str, Any], field: str) -> str:
    value = manifest.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Archive-first database persistence requires explicit {field}")
    return value


def _expected_storage_uri(store: EvidenceStore, manifest: dict[str, Any]) -> str:
    return (
        f"{store.config.endpoint.rstrip('/')}/{store.config.bucket}/"
        f"{object_key(manifest)}"
    )


def _verify_archived_boundary(archived, store: EvidenceStore) -> dict[str, Any]:
    """Re-read both durable objects before any relational state is accepted."""
    manifest = freeze_capture_manifest(archived.manifest)
    if archived.content_receipt.get("sha256") != manifest["sha256"]:
        raise ValueError("Content receipt belongs to another ContentObject")
    if archived.content_receipt.get("byte_size") != manifest["byte_size"]:
        raise ValueError("Content receipt byte size disagrees with capture manifest")
    if archived.content_receipt.get("content_type") != manifest["content_type"]:
        raise ValueError("Content receipt MIME type disagrees with capture manifest")
    expected_uri = _expected_storage_uri(store, manifest)
    if archived.content_receipt.get("storage_uri") != expected_uri:
        raise ValueError("Content receipt does not point to the configured durable object")

    # Receipts are not the evidence. Perform independent provider reads again immediately
    # before database persistence; a stale/tampered receipt cannot authorise promotion.
    store.read_verified(manifest)
    CaptureCatalogue(store).verify_receipt(manifest, archived.catalogue_receipt)
    return manifest


def _series_id(cur, source_key: str):
    cur.execute(
        "SELECT series_id FROM source.source_series WHERE series_code=%s",
        (source_key,),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError(
            f"SourceSeries {source_key!r} must exist before relational capture persistence"
        )
    return row[0]


def _resource_id(cur, manifest: dict[str, Any], resource_type_code: str):
    locator = manifest["resource_url"]
    cur.execute(
        """
        SELECT resource_id, web_url, resource_type_code
        FROM source.source_resource WHERE canonical_locator=%s
        """,
        (locator,),
    )
    row = cur.fetchone()
    if row:
        if row[1] != locator or row[2] != resource_type_code:
            raise ValueError("Existing SourceResource metadata conflicts with capture provenance")
        return row[0]
    cur.execute(
        """
        INSERT INTO source.source_resource(canonical_locator, web_url, resource_type_code)
        VALUES (%s,%s,%s)
        RETURNING resource_id
        """,
        (locator, locator, resource_type_code),
    )
    return cur.fetchone()[0]


def _content_object_id(cur, manifest: dict[str, Any], store: EvidenceStore):
    expected_uri = _expected_storage_uri(store, manifest)
    cur.execute(
        """
        SELECT content_object_id, mime_type, file_size, storage_uri, storage_status_code
        FROM source.content_object WHERE sha256=%s FOR UPDATE
        """,
        (manifest["sha256"],),
    )
    row = cur.fetchone()
    if row:
        content_id, _mime_type, file_size, storage_uri, storage_status = row
        # ContentObject identity is the byte digest. A capture can legitimately report
        # a different MIME label for identical bytes; that label remains frozen in the
        # immutable CaptureCatalogue manifest rather than rewriting ContentObject metadata.
        if file_size != manifest["byte_size"]:
            raise ValueError("Existing ContentObject byte size conflicts with archived bytes")
        if storage_status == "durable" and storage_uri != expected_uri:
            raise ValueError("Refusing to replace an existing durable ContentObject location")
        if storage_status != "durable":
            # A second provider read happens inside promote(). The transaction may roll
            # back, but the already archived bytes and catalogue record remain intact.
            store.promote(cur.connection, manifest)
        return content_id

    cur.execute(
        """
        INSERT INTO source.content_object(
            sha256, mime_type, file_size, storage_uri, storage_status_code
        ) VALUES (%s,%s,%s,%s,'durable')
        RETURNING content_object_id
        """,
        (
            manifest["sha256"],
            manifest["content_type"],
            manifest["byte_size"],
            expected_uri,
        ),
    )
    return cur.fetchone()[0]


def _capture_id(
    cur,
    *,
    manifest: dict[str, Any],
    series_id,
    resource_id,
    content_object_id,
    origin_type: str,
    authority_rank_code: str,
):
    capture_id = _canonical_capture_uuid(manifest.get("capture_id"))
    if capture_id is None:
        raise ValueError("Archive-first capture persistence requires a canonical capture_id UUID")
    captured_at = _parse_captured_at(manifest["captured_at"])
    reference_date = _parse_optional_date(manifest.get("reference_date"), "reference_date")
    last_modified = _parse_last_modified(manifest.get("last_modified"))
    resolved_url = manifest.get("resolved_url", manifest["resource_url"])
    expected = (
        series_id,
        resource_id,
        content_object_id,
        captured_at,
        manifest.get("http_status"),
        origin_type,
        authority_rank_code,
        resolved_url,
        manifest.get("etag"),
        last_modified,
        reference_date,
    )
    cur.execute(
        """
        SELECT series_id, resource_id, content_object_id, captured_at, http_status,
               origin_type_code, authority_rank_code, resolved_url, etag,
               last_modified, declared_reference_date
        FROM source.source_capture WHERE capture_id=%s
        """,
        (capture_id,),
    )
    row = cur.fetchone()
    if row:
        if tuple(row) != expected:
            raise ValueError("Existing capture_id conflicts with immutable archived provenance")
        return capture_id
    cur.execute(
        """
        INSERT INTO source.source_capture(
            capture_id, series_id, resource_id, content_object_id, captured_at, http_status,
            origin_type_code, authority_rank_code, resolved_url, etag,
            last_modified, declared_reference_date
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING capture_id
        """,
        (
            capture_id,
            series_id,
            resource_id,
            content_object_id,
            captured_at,
            manifest.get("http_status"),
            origin_type,
            authority_rank_code,
            resolved_url,
            manifest.get("etag"),
            last_modified,
            reference_date,
        ),
    )
    return cur.fetchone()[0]


def persist_archived_capture(conn, archived, store: EvidenceStore) -> dict[str, str]:
    """Persist one verified private-store capture into the provenance database.

    The caller owns the transaction. Any failure rolls back relational state only;
    durable bytes and immutable capture provenance have already been written and
    independently read back by the time this function is entered.
    """
    manifest = _verify_archived_boundary(archived, store)
    source_key = _required_code(manifest, "source_key")
    origin_type = _required_code(manifest, "origin_type")
    authority_rank = _required_code(manifest, "authority_rank_code")
    resource_type = _required_code(manifest, "resource_type_code")

    with conn.cursor() as cur:
        series_id = _series_id(cur, source_key)
        resource_id = _resource_id(cur, manifest, resource_type)
        content_object_id = _content_object_id(cur, manifest, store)
        capture_id = _capture_id(
            cur,
            manifest=manifest,
            series_id=series_id,
            resource_id=resource_id,
            content_object_id=content_object_id,
            origin_type=origin_type,
            authority_rank_code=authority_rank,
        )
    return {
        "series_id": str(series_id),
        "resource_id": str(resource_id),
        "content_object_id": str(content_object_id),
        "capture_id": str(capture_id),
    }
