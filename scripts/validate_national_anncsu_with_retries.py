from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, TypeVar
from urllib.error import HTTPError, URLError

import validate_national_anncsu as validator

_ORIGINAL_DOWNLOAD = validator._download
_ORIGINAL_PROBE_DATASET = validator._probe_dataset
_RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}
_T = TypeVar("_T")


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, HTTPError):
        return exc.code in _RETRYABLE_HTTP
    return isinstance(exc, (URLError, TimeoutError, ConnectionError, OSError))


def _with_retry(operation: Callable[[], _T], *, attempts: int = 4) -> _T:
    """Run one official-source network operation with bounded exponential retries.

    Retry policy is deliberately limited to transport failures and explicitly
    transient HTTP statuses. Provider/content validation errors are never retried
    or converted into success.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except BaseException as exc:
            if not _is_retryable(exc) or attempt == attempts:
                raise
            time.sleep(2 ** (attempt - 1))
    raise AssertionError("unreachable")


def _download_with_retry(url: str, destination: Path, *, attempts: int = 4) -> str:
    """Retry transient approved-source downloads while preserving frozen SHA gates.

    The normal validator still checks successful bytes against the approved SHA-256.
    Any partial destination is deleted before retry so a failed transfer can never be
    mistaken for an approved capture.
    """
    def operation() -> str:
        try:
            return _ORIGINAL_DOWNLOAD(url, destination)
        except BaseException:
            if destination.exists():
                destination.unlink()
            raise

    return _with_retry(operation, attempts=attempts)


def _probe_dataset_with_retry(item: dict[str, str | None], *, attempts: int = 4):
    """Retry transient ANNCSU catalogue transport failures without weakening the probe.

    Each successful attempt still has to return the ZIP magic bytes required by the
    original validator. Wrong dataset codes, non-ZIP responses and permanent HTTP
    failures therefore remain hard failures.
    """
    return _with_retry(lambda: _ORIGINAL_PROBE_DATASET(item), attempts=attempts)


validator._download = _download_with_retry
validator._probe_dataset = _probe_dataset_with_retry


if __name__ == "__main__":
    validator.main()
