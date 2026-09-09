from __future__ import annotations

import time
from pathlib import Path
from urllib.error import HTTPError, URLError

import validate_national_anncsu as validator

_ORIGINAL_DOWNLOAD = validator._download
_RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}


def _download_with_retry(url: str, destination: Path, *, attempts: int = 4) -> str:
    """Retry transient official-source transport failures without weakening SHA gates.

    The caller still verifies the downloaded bytes against the frozen approved SHA-256.
    Permanent HTTP failures are raised immediately. A partial destination is removed
    before every retry so a failed transport can never be mistaken for a valid capture.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    for attempt in range(1, attempts + 1):
        try:
            return _ORIGINAL_DOWNLOAD(url, destination)
        except HTTPError as exc:
            if exc.code not in _RETRYABLE_HTTP or attempt == attempts:
                raise
            if destination.exists():
                destination.unlink()
        except (URLError, TimeoutError, ConnectionError, OSError):
            if attempt == attempts:
                raise
            if destination.exists():
                destination.unlink()
        time.sleep(2 ** (attempt - 1))
    raise AssertionError("unreachable")


validator._download = _download_with_retry


if __name__ == "__main__":
    validator.main()
