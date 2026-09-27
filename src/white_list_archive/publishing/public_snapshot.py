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
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPOSITORY = "colazeta/italian-anti-mafia-whitelist"
FILES = {"registry.json", "registry.csv", "prefectures.json", "prefectures.csv", "history.json"}
BOOTSTRAP_TAG = "public-data-2026-09-27-verified"
BOOTSTRAP_HASHES = {
    "registry.json": "55c7e3dfa5e97115d247d846979b795844803f6c83d70e58a82ceee126d595c5",
    "registry.csv": "e0182e26ac6c96438921b738d0cac3ee749b3275808ca32670d8cbad03607375",
    "prefectures.json": "303f4a7efa97dded4daaf44b85ea9c15024a6c458ab18b8e6d6fa50cc2a5a479",
    "prefectures.csv": "8280d975a48990465c33752dc2fbe35221d0b02754e03b59dfbd01ee7c37926e",
    "history.json": "c31986cdd4f9863ffc2f9efaf0dcb79ccff7a1459599fe1c58bcb1e60cc3d270",
}


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
    with urlopen(request, timeout=120) as response:
        body = response.read(limit + 1)
    if len(body) > limit:
        raise ValueError("Public snapshot exceeds reviewed size")
    return body


def restore(manifest: dict, destination: Path, *, allow_bootstrap: bool = False) -> None:
    validate_manifest(manifest)
    destination.mkdir(parents=True, exist_ok=True)
    bootstrap = (allow_bootstrap and manifest["release_tag"] == BOOTSTRAP_TAG
                 and {name: item["sha256"] for name, item in manifest["files"].items()} == BOOTSTRAP_HASHES)
    # Stage the entire set before replacing any existing public data.
    with tempfile.TemporaryDirectory(prefix="snapshot-", dir=destination.parent) as directory:
        staging = Path(directory)
        for name, item in manifest["files"].items():
            url = f"https://github.com/{REPOSITORY}/releases/download/{manifest['release_tag']}/{name}.gz"
            try:
                compressed = download(url, item["bytes"] + 65536)
            except HTTPError as exc:
                if exc.code != 404 or not bootstrap:
                    raise
                body = download(f"https://colazeta.github.io/italian-anti-mafia-whitelist/data/{name}", item["bytes"])
                print(f"One-time bootstrap of previously approved public bytes: {name}")
            else:
                import io
                with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as handle:
                    body = handle.read(item["bytes"] + 1)
            verify(body, item, name)
            (staging / name).write_bytes(body)
        for name in FILES:
            (staging / name).replace(destination / name)


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
    parser.add_argument("mode", choices=["restore", "pack"])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--data", type=Path, default=Path("public-site/data"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--tag")
    parser.add_argument("--allow-bootstrap", action="store_true")
    args = parser.parse_args()
    if args.mode == "restore":
        if not args.manifest:
            parser.error("restore requires --manifest")
        restore(json.loads(args.manifest.read_text()), args.data, allow_bootstrap=args.allow_bootstrap)
    else:
        if not args.output or not args.tag:
            parser.error("pack requires --output and --tag")
        pack(args.data, args.output, args.tag)


if __name__ == "__main__":
    main()
