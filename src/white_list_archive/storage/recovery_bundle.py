"""Offline private recovery packages; authenticated transfer remains external.

These operations neither access a provider nor establish administrative independence.
The caller pins both returned digests outside the package before transferring it.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import zipfile

ROLES = frozenset({"postgres_dump", "postgres_verification", "original",
                   "capture_provenance", "parser_snapshot", "scope_inventory"})
MAX_FILES = 100_000
MAX_FILE_BYTES = 200_000_000
MAX_TOTAL_BYTES = 1_000_000_000
MAX_MANIFEST_BYTES = 2_000_000
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path(value):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("Invalid private bundle path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in (".", "..") for p in path.parts) or str(path) != value:
        raise ValueError("Non-canonical private bundle path")
    return path


def _entries(entries):
    if not isinstance(entries, list) or not entries or len(entries) > MAX_FILES:
        raise ValueError("Invalid bundle denominator")
    paths = set()
    total = 0
    for item in entries:
        if not isinstance(item, dict) or set(item) != {"path", "role", "byte_size", "sha256"}:
            raise ValueError("Invalid bundle entry contract")
        path = _path(item["path"])
        if item["path"] in paths or item["role"] not in ROLES:
            raise ValueError("Duplicate path or unknown private file role")
        size = item["byte_size"]
        if (type(size) is not int or not 0 <= size <= MAX_FILE_BYTES
            or not isinstance(item["sha256"], str) or not _HASH.fullmatch(item["sha256"])):
            raise ValueError("Invalid private file size or digest")
        total += size
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Private bundle exceeds total byte limit")
        paths.add(item["path"])
    ordered = sorted(paths)
    if any(after.startswith(before + "/") for before, after in zip(ordered, ordered[1:])):
        raise ValueError("Conflicting file/directory paths")
    return total


def _summary(manifest, archive_sha256, manifest_sha256):
    return {"schema_version": 1, "archive_sha256": archive_sha256,
            "manifest_sha256": manifest_sha256, "files_verified": len(manifest["files"]),
            "bytes_verified": sum(item["byte_size"] for item in manifest["files"]),
            "role_counts": dict(sorted(Counter(item["role"] for item in manifest["files"]).items())),
            "bundle_integrity_verified": True, "independent_backup_verified": False,
            "database_restore_verified": False, "national_completeness_verified": False}


def export_bundle(private_directory: Path, files: list[dict], output: Path):
    """Package only explicit files already retrieved through authorised private access.

    No whole-directory discovery, provider credentials, upload or sharing is performed.
    The plan contains only path/role pairs; identities are computed from actual bytes.
    """
    root = private_directory.resolve(strict=True)
    if not root.is_dir() or output.exists() or output.is_symlink():
        raise ValueError("Export requires a private directory and a new output")
    entries = []
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "role"}:
            raise ValueError("Export plan requires only relative path and role")
        relative = _path(item["path"])
        source = root.joinpath(*relative.parts)
        if any(part.is_symlink() for part in [source, *source.parents] if part != root.parent):
            raise ValueError("Symlinks are not private recovery inputs")
        if not source.is_file():
            raise ValueError("Missing private recovery input")
        entries.append({**item, "byte_size": source.stat().st_size, "sha256": _hash_file(source)})
    _entries(entries)
    manifest = {"schema_version": 1, "scope": "explicit_file_selection",
                "files": sorted(entries, key=lambda entry: entry["path"])}
    body = _json(manifest)
    if len(body) > MAX_MANIFEST_BYTES:
        raise ValueError("Private manifest exceeds limit")
    with output.open("xb") as handle:
        output.chmod(0o600)
        with zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", body)
            for item in manifest["files"]:
                archive.write(root / item["path"], "files/" + item["path"])
    archive_sha = _hash_file(output)
    manifest_sha = hashlib.sha256(body).hexdigest()
    # Reread the actual ZIP, catching source changes during packaging as well.
    return verify_bundle(output, archive_sha, manifest_sha)


def verify_bundle(archive_path: Path, expected_archive_sha256: str,
                  expected_manifest_sha256: str, restore_directory: Path | None = None):
    """Read independently downloaded package against externally pinned identities.

    Full validation precedes extraction. A restore target must not exist; originals
    are never overwritten. Verification does not execute a SQL dump or any member.
    """
    if not _HASH.fullmatch(expected_archive_sha256) or not _HASH.fullmatch(expected_manifest_sha256):
        raise ValueError("External archive and manifest SHA-256 pins are required")
    if restore_directory is not None and (restore_directory.exists() or restore_directory.is_symlink()):
        raise ValueError("Clean recovery directory must not exist")
    if _hash_file(archive_path) != expected_archive_sha256:
        raise ValueError("Downloaded archive digest mismatch")
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        names = [item.filename for item in members]
        if len(members) > MAX_FILES + 1 or len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP entries or excessive member count")
        if "manifest.json" not in names:
            raise ValueError("Bundle manifest is missing")
        for member in members:
            mode = member.external_attr >> 16
            if (member.is_dir() or stat.S_ISLNK(mode) or
                (stat.S_IFMT(mode) not in (0, stat.S_IFREG)) or member.flag_bits & 1):
                raise ValueError("Unsupported ZIP member type")
            _path(member.filename)
        info = archive.getinfo("manifest.json")
        if info.file_size > MAX_MANIFEST_BYTES:
            raise ValueError("Private manifest exceeds limit")
        body = archive.read(info)
        if hashlib.sha256(body).hexdigest() != expected_manifest_sha256:
            raise ValueError("Downloaded manifest digest mismatch")
        manifest = json.loads(body)
        if (not isinstance(manifest, dict) or set(manifest) != {"schema_version", "scope", "files"}
            or manifest["schema_version"] != 1 or manifest["scope"] != "explicit_file_selection"):
            raise ValueError("Unsupported private recovery bundle")
        _entries(manifest["files"])
        if set(names) != {"manifest.json", *("files/" + item["path"] for item in manifest["files"])}:
            raise ValueError("ZIP members differ from explicit manifest denominator")
        for item in manifest["files"]:
            member = archive.getinfo("files/" + item["path"])
            if member.file_size != item["byte_size"]:
                raise ValueError("Private member byte size mismatch")
            digest = hashlib.sha256()
            total = 0
            with archive.open(member) as source:
                for chunk in iter(lambda: source.read(1_048_576), b""):
                    total += len(chunk)
                    if total > item["byte_size"]:
                        raise ValueError("Private member expands beyond its bound")
                    digest.update(chunk)
            if total != item["byte_size"] or digest.hexdigest() != item["sha256"]:
                raise ValueError("Private member content digest mismatch")
        if restore_directory is not None:
            restore_directory.mkdir(mode=0o700, parents=False, exist_ok=False)
            for item in manifest["files"]:
                destination = restore_directory / item["path"]
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with archive.open("files/" + item["path"]) as source, destination.open("xb") as target:
                    shutil.copyfileobj(source, target, length=1_048_576)
                destination.chmod(0o600)
                if _hash_file(destination) != item["sha256"]:
                    raise ValueError("Clean local copy digest mismatch")
    return _summary(manifest, expected_archive_sha256, expected_manifest_sha256)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--private-directory", type=Path, required=True)
    export.add_argument("--plan", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--archive", type=Path, required=True)
    verify.add_argument("--archive-sha256", required=True)
    verify.add_argument("--manifest-sha256", required=True)
    verify.add_argument("--restore-directory", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "export":
            result = export_bundle(args.private_directory, json.loads(args.plan.read_bytes()), args.output)
        else:
            result = verify_bundle(args.archive, args.archive_sha256, args.manifest_sha256,
                                   args.restore_directory)
        print(json.dumps(result, sort_keys=True))
    except Exception:
        # Paths, provider details, manifest contents and SQL stay off public logs.
        print('{"status":"failed","stage":"offline_recovery_bundle_failed"}')
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
