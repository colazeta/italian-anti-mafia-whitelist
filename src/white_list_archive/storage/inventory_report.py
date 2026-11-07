"""Append-only private recovery inventories in the existing operations namespace.

This is operational evidence, not a second source catalogue or an independent backup.
The retained report includes the entire explicit denominator and its exclusions.
"""
from __future__ import annotations

import gzip
import hashlib
from io import BytesIO
import json
import re
from typing import Any
from uuid import uuid4

_MAX_RAW_BYTES = 50_000_000
_MAX_COMPRESSED_BYTES = 10_000_000
_SHA40 = re.compile(r'[0-9a-f]{40}')


def persist_inventory_report(
    store: Any, *, inventory: dict, robot_metrics: dict, code_revision: str,
) -> str:
    """Create one private attempt, verify all bytes and return only its digest.

    Use the existing protected store; never overwrite/delete earlier reports, even
    when provider readback fails. Provider exception messages are not safe logs.
    """
    if not isinstance(code_revision, str) or not _SHA40.fullmatch(code_revision):
        raise ValueError('Inventory report requires an exact code revision')
    robot_head = robot_metrics.get('robot_state_sha')
    if not isinstance(robot_head, str) or not _SHA40.fullmatch(robot_head):
        raise ValueError('Inventory report requires an exact robot-state revision')
    if inventory.get('schema_version') != 1 or not isinstance(inventory.get('items'), list):
        raise ValueError('Inventory report requires a complete recovery denominator')
    if inventory.get('metrics', {}).get('denominator_items') != len(inventory['items']):
        raise ValueError('Inventory report denominator count conflicts with its items')
    report = {
        'schema_version': 1,
        'report_kind': 'national_recovery_inventory',
        'code_revision': code_revision,
        'robot_selection': robot_metrics,
        'inventory': inventory,
    }
    return persist_private_inventory_document(store, report)


def persist_private_inventory_document(store: Any, report: dict, *, key: str | None = None) -> str:
    """Write a private inventory document, with exact compressed/decompressed readback.

    A caller-supplied key is restricted to one run-attempt shard namespace. This
    supports bounded jobs without publishing their full reports as CI artifacts.
    """
    if key is not None and not re.fullmatch(
        r'operations/v1/recovery-inventory-shards/[0-9]+-[0-9]+/shard-[0-3]\.json\.gz', key,
    ):
        raise ValueError('Invalid private inventory shard key')
    body = json.dumps(report, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(body) > _MAX_RAW_BYTES:
        raise ValueError('Private inventory report exceeds its raw bound')
    compressed = gzip.compress(body, mtime=0)
    if len(compressed) > _MAX_COMPRESSED_BYTES:
        raise ValueError('Private inventory report exceeds its compressed bound')
    key = key or f'operations/v1/recovery-inventory/{uuid4()}.json.gz'
    try:
        store.client.put_object(Bucket=store.config.bucket, Key=key, Body=compressed,
                                ContentType='application/json', ContentEncoding='gzip',
                                IfNoneMatch='*')
        response = store.client.get_object(Bucket=store.config.bucket, Key=key)
        stream = response['Body']
        try:
            actual = stream.read(len(compressed) + 1)
        finally:
            stream.close()
    except Exception:
        raise RuntimeError('Private inventory report persistence/readback failed') from None
    if actual != compressed:
        raise RuntimeError('Private inventory report failed exact readback')
    try:
        with gzip.GzipFile(fileobj=BytesIO(actual)) as recovered:
            decoded = recovered.read(len(body) + 1)
    except Exception:
        raise RuntimeError('Private inventory report decompression failed') from None
    if decoded != body:
        raise RuntimeError('Private inventory report failed decompressed readback')
    return hashlib.sha256(body).hexdigest()


def read_private_inventory_document(store: Any, *, key: str) -> dict:
    """Read a bounded canonical JSON shard from the exact private run-attempt key."""
    if not re.fullmatch(
        r'operations/v1/recovery-inventory-shards/[0-9]+-[0-9]+/shard-[0-3]\.json\.gz', key,
    ):
        raise ValueError('Invalid private inventory shard key')
    try:
        response = store.client.get_object(Bucket=store.config.bucket, Key=key)
        stream = response['Body']
        try:
            compressed = stream.read(_MAX_COMPRESSED_BYTES + 1)
        finally:
            stream.close()
        if len(compressed) > _MAX_COMPRESSED_BYTES:
            raise ValueError('Compressed inventory shard exceeds its bound')
        with gzip.GzipFile(fileobj=BytesIO(compressed)) as recovered:
            raw = recovered.read(_MAX_RAW_BYTES + 1)
        if len(raw) > _MAX_RAW_BYTES:
            raise ValueError('Inventory shard exceeds its raw bound')
        document = json.loads(raw)
        canonical = json.dumps(document, sort_keys=True, separators=(',', ':'),
                               ensure_ascii=False, allow_nan=False).encode('utf-8')
        if canonical != raw or not isinstance(document, dict):
            raise ValueError('Inventory shard must be a canonical JSON document')
        return document
    except Exception:
        raise RuntimeError('Private inventory shard could not be verified') from None
