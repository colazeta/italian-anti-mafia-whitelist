"""Conservative recovery inventory for the temporal source archive.

The inventory starts from an explicit capture denominator. It never treats a bucket
listing, failed GET or absent local file as proof that an original is missing. A capture
is ``verified`` only when both its durable ContentObject and immutable capture
provenance can be read back and verified. A capture is ``missing`` only when durable
absence has been independently confirmed and the caller also declares the recovery
search complete. Otherwise uncertainty remains ``not_verified``.
"""
from __future__ import annotations

from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
from pathlib import Path
from typing import Any
from threading import Lock

from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.evidence import EvidenceStore, freeze_capture_manifest

SCHEMA_VERSION = 1
STATUSES = frozenset({"verified", "recoverable_pending", "missing", "not_verified"})


def _verified_recovery_copy(paths: list[str], *, sha256: str, byte_size: int) -> bool:
    """Return true when an explicitly supplied recovery package contains exact bytes."""
    for raw_path in paths:
        path = Path(raw_path)
        try:
            with path.open("rb") as handle:
                data = handle.read(byte_size + 1)
        except (FileNotFoundError, IsADirectoryError, PermissionError, OSError):
            continue
        if len(data) == byte_size and hashlib.sha256(data).hexdigest() == sha256:
            return True
    return False


def build_archive_inventory(
    expectations: dict[str, Any], store: EvidenceStore, *, max_workers: int = 4,
) -> dict[str, Any]:
    """Verify an explicit set of expected captures against durable and recovery storage.

    ``expectations`` is intentionally separate from object-store discovery. This makes
    the denominator auditable and prevents one incomplete directory/bucket listing from
    being converted into false ``missing`` claims.
    """
    if not isinstance(expectations, dict) or expectations.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported archive inventory expectations")
    if set(expectations) != {"schema_version", "generated_at", "recovery_search_complete", "captures"}:
        raise ValueError("Unapproved archive inventory expectations envelope")
    if not isinstance(expectations["generated_at"], str) or not expectations["generated_at"].strip():
        raise ValueError("Inventory generation timestamp is required")
    if type(expectations["recovery_search_complete"]) is not bool:
        raise ValueError("recovery_search_complete must be boolean")
    if not isinstance(expectations["captures"], list):
        raise ValueError("Inventory captures must be a list")

    if type(max_workers) is not int or not 1 <= max_workers <= 4:
        raise ValueError("Inventory workers must be between one and four")

    validated = []
    identities: set[tuple[str, str]] = set()
    authorities: set[str] = set()
    # Immutable original bytes may support many separately verified captures.
    # Cache only successful reads, keyed by validated content identity; never
    # cache catalogue results or carry verification between invocations.
    original_checks = {}

    for expected in expectations["captures"]:
        if not isinstance(expected, dict) or set(expected) != {
            "authority_key",
            "capture",
            "catalogue",
            "recovery_paths",
            "durable_absence_confirmed",
        }:
            raise ValueError("Unapproved archive inventory capture expectation")
        authority_key = expected["authority_key"]
        if not isinstance(authority_key, str) or not authority_key.strip():
            raise ValueError("Capture authority_key is required")
        authorities.add(authority_key)

        capture = freeze_capture_manifest(expected["capture"])
        capture_id = capture.get("capture_id")
        source_key = capture.get("source_key")
        if not isinstance(capture_id, str) or not capture_id.strip():
            raise ValueError("Inventory requires a stable capture_id")
        if not isinstance(source_key, str) or not source_key.strip():
            raise ValueError("Inventory requires source_key")
        identity = (source_key, capture_id)
        if identity in identities:
            raise ValueError("Duplicate capture expectation")
        identities.add(identity)

        if type(expected["durable_absence_confirmed"]) is not bool:
            raise ValueError("durable_absence_confirmed must be boolean")
        recovery_paths = expected["recovery_paths"]
        if not isinstance(recovery_paths, list) or any(not isinstance(path, str) for path in recovery_paths):
            raise ValueError("recovery_paths must be a list of paths")

        catalogue = expected["catalogue"]
        if catalogue is not None and not isinstance(catalogue, dict):
            raise ValueError("catalogue receipt must be a mapping or null")
        validated.append({**deepcopy(expected), "capture": capture})
        byte_identity = (capture["sha256"], capture["byte_size"])
        original_checks.setdefault(byte_identity, {"lock": Lock(), "verified": False})

    def verify_capture(expected):
        capture = expected["capture"]
        authority_key = expected["authority_key"]
        source_key, capture_id = capture["source_key"], capture["capture_id"]
        recovery_paths = expected["recovery_paths"]
        durable_original_verified = False
        provider_error = None
        try:
            byte_identity = (capture["sha256"], capture["byte_size"])
            check = original_checks[byte_identity]
            # Per-content lock deduplicates concurrent successful reads without
            # sharing a capture provenance verdict or retaining failed results.
            with check["lock"]:
                if not check["verified"]:
                    store.read_verified(capture)
                    check["verified"] = True
            durable_original_verified = True
        except Exception as exc:  # provider failures are evidence of uncertainty, not absence
            provider_error = type(exc).__name__

        capture_provenance_verified = False
        catalogue = expected["catalogue"]
        if catalogue is not None:
            try:
                CaptureCatalogue(store).verify_receipt(capture, catalogue)
                capture_provenance_verified = True
            except Exception:
                capture_provenance_verified = False

        recoverable = False
        if not durable_original_verified:
            recoverable = _verified_recovery_copy(
                recovery_paths,
                sha256=capture["sha256"],
                byte_size=capture["byte_size"],
            )

        # Archive completeness is a conjunction: recoverable bytes without the
        # immutable temporal capture/check are not a verified archived acquisition.
        # Keep the durable ContentObject metric separate so byte preservation remains
        # visible without overstating temporally referenced capture coverage.
        if durable_original_verified and capture_provenance_verified:
            status = "verified"
        elif recoverable:
            status = "recoverable_pending"
        elif expected["durable_absence_confirmed"] and expectations["recovery_search_complete"]:
            status = "missing"
        else:
            status = "not_verified"

        return {
            "authority_key": authority_key,
            "source_key": source_key,
            "capture_id": capture_id,
            "sha256": capture["sha256"],
            "byte_size": capture["byte_size"],
            "status": status,
            "durable_original_verified": durable_original_verified,
            "capture_provenance_verified": capture_provenance_verified,
            "provider_check_error_class": provider_error,
        }

    # Keep at most max_workers tasks outstanding, preserving input/report order.
    # An unexpected exception cancels queued work instead of submitting the whole
    # national denominator; provider failures retain the existing per-item status.
    rows = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        pending = deque()
        selected = iter(validated)
        for _ in range(min(max_workers, len(validated))):
            pending.append(pool.submit(verify_capture, next(selected)))
        try:
            while pending:
                rows.append(pending.popleft().result())
                expected = next(selected, None)
                if expected is not None:
                    pending.append(pool.submit(verify_capture, expected))
        except BaseException:
            for future in pending:
                future.cancel()
            raise

    verified_content = {row["sha256"] for row in rows if row["durable_original_verified"]}
    provenance_verified = sum(row["capture_provenance_verified"] for row in rows)

    counts = Counter(row["status"] for row in rows)
    if set(counts) - STATUSES:
        raise AssertionError("Unexpected inventory status")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": expectations["generated_at"],
        "recovery_search_complete": expectations["recovery_search_complete"],
        "metrics": {
            "source_authorities_covered": len(authorities),
            "captures_expected": len(rows),
            "distinct_content_objects_expected": len({row["sha256"] for row in rows}),
            "durably_retrievable_content_objects": len(verified_content),
            "captures_with_verified_provenance": provenance_verified,
            "verified": counts["verified"],
            "recoverable_pending": counts["recoverable_pending"],
            "missing": counts["missing"],
            "not_verified": counts["not_verified"],
        },
        "captures": rows,
    }
