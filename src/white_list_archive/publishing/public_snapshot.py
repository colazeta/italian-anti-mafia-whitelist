"""Restore approved *public derivatives*, independently of live official sources.

Release assets are durable distribution copies, not the private evidence archive.
Every decoded byte is bound to a reviewed manifest in git. No 'latest' fallback.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPOSITORY = "colazeta/italian-anti-mafia-whitelist"
PAGES_URL = "https://colazeta.github.io/italian-anti-mafia-whitelist/"
FILES = {"registry.json", "registry.csv", "prefectures.json", "prefectures.csv", "history.json"}


def validate_manifest(manifest: dict) -> None:
    if (set(manifest) != {"schema_version", "repository", "release_tag", "files"}
            or manifest["schema_version"] != 1 or manifest["repository"] != REPOSITORY
            or not re.fullmatch(r"public-data-[A-Za-z0-9.-]+", manifest["release_tag"])
            or set(manifest["files"]) != FILES):
        raise ValueError("Unapproved public snapshot manifest")
    for name, item in manifest["files"].items():
        if (set(item) != {"sha256", "bytes"}
                or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"])
                or type(item["bytes"]) is not int or not 0 < item["bytes"] <= 300_000_000):
            raise ValueError(f"Invalid public snapshot entry: {name}")


def verify(body: bytes, item: dict, name: str) -> None:
    if len(body) != item["bytes"] or hashlib.sha256(body).hexdigest() != item["sha256"]:
        raise ValueError(f"Public snapshot integrity mismatch: {name}")


def download(url: str, limit: int) -> bytes:
    request = Request(url, headers={"User-Agent": "white-list-public-snapshot/2"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=120) as response:
                body = response.read(limit + 1)
            break
        except HTTPError as error:
            if error.code not in (408, 429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (URLError, TimeoutError, ConnectionError):
            if attempt == 2:
                raise
        time.sleep(attempt + 1)
    if len(body) > limit:
        raise ValueError("Public snapshot exceeds reviewed size")
    return body


def restore(manifest: dict, destination: Path) -> None:
    validate_manifest(manifest)
    destination.mkdir(parents=True, exist_ok=True)
    # Stage the entire set before replacing any existing public data.
    with tempfile.TemporaryDirectory(prefix="snapshot-", dir=destination.parent) as directory:
        staging = Path(directory)
        for name, item in manifest["files"].items():
            url = f"https://github.com/{REPOSITORY}/releases/download/{manifest['release_tag']}/{name}.gz"
            compressed = download(url, item["bytes"] + 65536)
            import io
            with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as handle:
                body = handle.read(item["bytes"] + 1)
            verify(body, item, name)
            (staging / name).write_bytes(body)
        for name in FILES:
            (staging / name).replace(destination / name)


def verify_live(manifest: dict, base_url: str = PAGES_URL, *, attempts: int = 4, sleep=time.sleep) -> dict:
    """Verify the actual deployed bytes, allowing bounded CDN propagation time.

    Only the existing public Pages origin and the closed five-file derivative
    surface are read. Never substitute a release download for a failed live check.
    """
    validate_manifest(manifest)
    if base_url.rstrip("/") + "/" != PAGES_URL or attempts < 1:
        raise ValueError("Unapproved live publication origin or retry bound")
    checked = {}
    for name, item in sorted(manifest["files"].items()):
        for attempt in range(1, attempts + 1):
            url = (f"{PAGES_URL}data/{name}?snapshot={manifest['release_tag']}"
                   f"&verification_attempt={attempt}")
            try:
                body = download(url, item["bytes"])
                verify(body, item, name)
            except (ValueError, HTTPError, URLError, TimeoutError, ConnectionError):
                if attempt == attempts:
                    raise
                sleep(5 * attempt)
            else:
                checked[name] = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
                break
    return {"release_tag": manifest["release_tag"], "live_files_verified": checked}


def pack(source: Path, destination: Path, tag: str) -> dict:
    manifest = {"schema_version": 1, "repository": REPOSITORY, "release_tag": tag, "files": {}}
    destination.mkdir(parents=True, exist_ok=True)
    for name in sorted(FILES):
        body = (source / name).read_bytes()
        manifest["files"][name] = {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
        with (destination / (name + ".gz")).open("wb") as output:
            with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as handle:
                handle.write(body)
    validate_manifest(manifest)
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["restore", "pack", "verify-live"])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--data", type=Path, default=Path("public-site/data"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--tag")
    parser.add_argument("--base-url", default=PAGES_URL)
    args = parser.parse_args()
    if args.mode == "restore":
        if not args.manifest:
            parser.error("restore requires --manifest")
        restore(json.loads(args.manifest.read_text()), args.data)
    elif args.mode == "verify-live":
        if not args.manifest:
            parser.error("verify-live requires --manifest")
        print(json.dumps(verify_live(json.loads(args.manifest.read_text()), args.base_url), sort_keys=True))
    else:
        if not args.output or not args.tag:
            parser.error("pack requires --output and --tag")
        pack(args.data, args.output, args.tag)


if __name__ == "__main__":
    main()
