"""Exact-identity recovery of archive-first captures from the private catalogue.

Recovery starts from a known ``(source_key, capture_id)`` pair. It deliberately does
not enumerate the object store: one incomplete listing must never become evidence that
a historical original is absent. New catalogue records preserve the complete frozen
capture manifest, so they can be rehydrated into the same manifest + receipt contract
used by the national recovery inventory. Legacy v1 catalogue objects that pre-date
complete-manifest preservation fail closed and require the historical manifest to be
supplied explicitly; optional provenance is never reconstructed from denormalised
fields.
"""
from __future__ import annotations

import hashlib

from white_list_archive.storage.capture_catalogue import (
    CaptureCatalogue,
    capture_record_key,
)
from white_list_archive.storage.evidence import freeze_capture_manifest


def load_catalogued_capture(
    catalogue: CaptureCatalogue,
    *,
    source_key: str,
    capture_id: str,
) -> tuple[dict, dict]:
    """Rehydrate one known capture/check from its immutable governed catalogue object.

    The returned receipt is reconstructed only from the exact immutable record that was
    read at the deterministic catalogue key and is immediately re-verified through the
    normal ``CaptureCatalogue.verify_receipt`` path. No write, migration, bucket listing
    or live-source lookup occurs.
    """
    key = capture_record_key({"source_key": source_key, "capture_id": capture_id})
    data, record = catalogue._read_record(key)

    embedded = record.get("capture_manifest")
    if not isinstance(embedded, dict):
        raise ValueError(
            "Legacy capture provenance lacks the complete capture manifest; "
            "supply the historical manifest explicitly"
        )

    frozen = freeze_capture_manifest(embedded)
    if frozen.get("source_key") != source_key or frozen.get("capture_id") != capture_id:
        raise ValueError("Stored capture provenance disagrees with requested capture identity")

    receipt = {
        "schema_version": 1,
        "capture_id": capture_id,
        "source_key": source_key,
        "sha256": frozen["sha256"],
        "byte_size": frozen["byte_size"],
        "catalogue_key": key,
        "catalogue_record_sha256": hashlib.sha256(data).hexdigest(),
        "created": False,
        "content_object_key": record.get("content_object_key"),
    }

    # Re-read and validate the immutable object through the canonical receipt contract.
    # This binds the embedded full manifest to the historical denormalised fields and
    # stored manifest digest before recovery is allowed to use it.
    catalogue.verify_receipt(frozen, receipt)
    return frozen, receipt
