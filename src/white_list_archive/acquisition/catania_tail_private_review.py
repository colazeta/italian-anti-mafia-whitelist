"""Private, immutable review packet for the ambiguous tail of the exact Catania XLSX.

Only the trusted existing evidence-archive workflow invokes this source-only step.
No row values, row locations, private object keys, or provider exceptions reach
GitHub logs. The packet is NOT a parser acceptance, SourceEdition or publication.
"""
from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
from io import BytesIO

import openpyxl

from white_list_archive.acquisition.catania_november13_archive_qa import PINS, MAX_SOURCE_BYTES
from white_list_archive.parsers.catania_candidate import MAX_COLS, MAX_ROWS, _header_row
from white_list_archive.parsers.multi_prefecture_tables import _clean

REVIEW_VERSION = 1
EXPECTED_FULL = 1887
EXPECTED_AMBIGUOUS = 10
MAX_PACKET_BYTES = 1_000_000


def _cell_value(value):
    """Retain original private cell type/value; reject unknown conversions."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise ValueError("Unreviewed worksheet cell value type")


def _packet_from_original(raw: bytes, digest: str, *, expected_full: int,
                          expected_ambiguous: int) -> dict:
    workbook = openpyxl.load_workbook(BytesIO(raw), read_only=False, data_only=False)
    try:
        if workbook.sheetnames != ["Foglio1"]:
            raise ValueError("Unreviewed worksheet identity")
        sheet = workbook.active
        if (not sheet.max_row or sheet.max_row > MAX_ROWS
                or not sheet.max_column or sheet.max_column > MAX_COLS):
            raise ValueError("Unreviewed source worksheet dimensions")
        start = _header_row(sheet, "listed") + 1
        complete = []
        incomplete = 0
        ambiguous = []
        for row_number in range(start, sheet.max_row + 1):
            values = [_clean(sheet.cell(row_number, col).value)
                      for col in range(1, 9)]
            if values[3] and values[4]:
                complete.append(row_number)
            elif values[3] or values[4]:
                incomplete += 1
            elif (values[0] and values[1]) or any(values[4:]):
                cells = []
                for col in range(1, 9):
                    cell = sheet.cell(row_number, col)
                    cells.append({
                        "column": col, "data_type": cell.data_type,
                        "style_id": cell.style_id,
                        "number_format": cell.number_format,
                        "raw_value": _cell_value(cell.value),
                    })
                ambiguous.append({"worksheet": "Foglio1", "physical_row": row_number,
                                  "cells": cells})
        if (len(complete) != expected_full or len(ambiguous) != expected_ambiguous
                or incomplete or not complete or
                any(row["physical_row"] <= complete[-1] for row in ambiguous)):
            raise ValueError("Ambiguous-tail layout requires a new review")
        return {
            "schema_version": REVIEW_VERSION,
            "scope": "catania_2026_11_13_listed_private_tail_review",
            "original_sha256": digest,
            "source_population": "listed",
            "record_contract": "unapproved_source_rows",
            "review_status": "requires_original_document_review",
            "full_signature_rows": len(complete),
            "ambiguous_tail_rows": len(ambiguous),
            "rows": ambiguous,
            "no_edition_date_assigned": True,
            "no_source_record_approved": True,
            "publication_approved": False,
        }
    finally:
        workbook.close()


def _private_key(digest: str) -> str:
    identity = f"catania-listed-tail-review:v{REVIEW_VERSION}:{digest}"
    key_hash = hashlib.sha256(identity.encode("ascii")).hexdigest()
    return f"operations/v1/catania-tail-review/{key_hash[:2]}/{key_hash}.json"


def _readback(store, key: str, byte_cap: int) -> bytes:
    response = store.client.get_object(Bucket=store.config.bucket, Key=key)
    stream = response["Body"]
    try:
        data = stream.read(byte_cap + 1)
    finally:
        stream.close()
    if len(data) > byte_cap:
        raise ValueError("Private review packet exceeds byte cap")
    return data


def prepare_private_tail_review(store, *, source_sha: str = PINS[0][2],
                                expected_full: int = EXPECTED_FULL,
                                expected_ambiguous: int = EXPECTED_AMBIGUOUS) -> dict:
    """Append once and fully read back a source-row review packet privately.

    Same original and schema version reuse exactly the same key and JSON bytes.
    Existing-object conflicts cannot replace an archived review packet.
    """
    if (not isinstance(source_sha, str) or len(source_sha) != 64
            or any(c not in "0123456789abcdef" for c in source_sha)):
        raise ValueError("Invalid exact source pin")
    raw = store.read_digest_verified(source_sha)
    if (type(raw) is not bytes or not (0 < len(raw) <= MAX_SOURCE_BYTES)
            or hashlib.sha256(raw).hexdigest() != source_sha):
        raise ValueError("Source original is not verified")
    packet = _packet_from_original(
        raw, source_sha, expected_full=expected_full,
        expected_ambiguous=expected_ambiguous,
    )
    encoded = json.dumps(packet, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    if not (0 < len(encoded) <= MAX_PACKET_BYTES):
        raise ValueError("Private review packet size contract failed")
    key = _private_key(source_sha)
    created = True
    try:
        store.client.put_object(
            Bucket=store.config.bucket, Key=key, Body=encoded,
            ContentType="application/json", IfNoneMatch="*",
        )
    except Exception as exc:
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
        if code not in {"PreconditionFailed", "412", "ObjectLockedByBucketPolicy", "10069"}:
            raise
        created = False
    if _readback(store, key, MAX_PACKET_BYTES) != encoded:
        raise ValueError("Immutable private review packet readback mismatch")
    # Only aggregate QA and packet integrity leave the protected step.
    return {
        "scope": packet["scope"],
        "private_review_packet_verified": True,
        "private_review_packet_created": created,
        "private_review_packet_sha256": hashlib.sha256(encoded).hexdigest(),
        "full_signature_rows": len(range(expected_full)),
        "ambiguous_tail_rows": len(packet["rows"]),
        "source_edition_approved": False,
        "postgresql_writes": 0,
        "public_promotions": 0,
    }


def main() -> int:
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    try:
        config = StoreConfig.from_env()
        safe = prepare_private_tail_review(EvidenceStore(client_for(config), config))
    except Exception:
        print(json.dumps({"scope": "catania_2026_11_13_listed_private_tail_review",
                          "private_review_packet_verified": False,
                          "state": "blocked_review", "public_promotions": 0}))
        return 1
    print(json.dumps(safe, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
