import hashlib
import json
from pathlib import Path
import stat
import zipfile

import pytest

from white_list_archive.storage.recovery_bundle import export_bundle, verify_bundle


def package(tmp_path):
    root = tmp_path / "private"
    root.mkdir()
    (root / "document.pdf").write_bytes(b"exact original bytes")
    (root / "database.dump").write_bytes(b"private postgres dump")
    target = tmp_path / "private.zip"
    receipt = export_bundle(root, [{"path": "document.pdf", "role": "original"},
                                  {"path": "database.dump", "role": "postgres_dump"}], target)
    return root, target, receipt


def verify(target, receipt, restore=None):
    return verify_bundle(target, receipt["archive_sha256"], receipt["manifest_sha256"], restore)


def test_downloaded_package_verifies_external_pins_and_clean_copy(tmp_path):
    root, target, receipt = package(tmp_path)
    restored = tmp_path / "clean"
    result = verify(target, receipt, restored)
    assert result["files_verified"] == 2
    assert result["role_counts"] == {"original": 1, "postgres_dump": 1}
    assert result["bundle_integrity_verified"] is True
    for claim in ("database_restore_verified", "independent_backup_verified", "national_completeness_verified"):
        assert result[claim] is False
    assert (restored / "document.pdf").read_bytes() == (root / "document.pdf").read_bytes()
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert stat.S_IMODE(restored.stat().st_mode) == 0o700


def test_damaged_download_is_rejected_before_extraction(tmp_path):
    _, target, receipt = package(tmp_path)
    with target.open("ab") as handle:
        handle.write(b"changed")
    restore = tmp_path / "clean"
    with pytest.raises(ValueError, match="archive digest"):
        verify(target, receipt, restore)
    assert not restore.exists()


def test_manifest_requires_independent_external_pin(tmp_path):
    _, target, receipt = package(tmp_path)
    with pytest.raises(ValueError, match="manifest digest"):
        verify_bundle(target, receipt["archive_sha256"], "0" * 64)


def test_existing_restore_and_archive_are_never_overwritten(tmp_path):
    root, target, receipt = package(tmp_path)
    with pytest.raises(ValueError, match="new output"):
        export_bundle(root, [{"path": "document.pdf", "role": "original"}], target)
    clean = tmp_path / "exists"
    clean.mkdir()
    with pytest.raises(ValueError, match="must not exist"):
        verify(target, receipt, clean)


@pytest.mark.parametrize("path", ["../outside", "/outside", "a/../../outside", "a//b", "a\\b", "./document.pdf"])
def test_noncanonical_export_paths_are_rejected(tmp_path, path):
    root = tmp_path / "private"
    root.mkdir()
    with pytest.raises(ValueError):
        export_bundle(root, [{"path": path, "role": "original"}], tmp_path / "result.zip")


def test_symlink_input_is_rejected(tmp_path):
    root = tmp_path / "private"
    root.mkdir()
    (tmp_path / "outside").write_bytes(b"private")
    (root / "link").symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError, match="Symlinks"):
        export_bundle(root, [{"path": "link", "role": "original"}], tmp_path / "result.zip")


def rewrite(tmp_path, transform):
    _, original, receipt = package(tmp_path)
    changed = tmp_path / "tampered.zip"
    with zipfile.ZipFile(original) as source, zipfile.ZipFile(changed, "w") as dest:
        for info in source.infolist():
            transform(info, source.read(info), dest)
    receipt["archive_sha256"] = hashlib.sha256(changed.read_bytes()).hexdigest()
    return changed, receipt


def test_content_mismatch_detected_even_when_container_pin_matches(tmp_path):
    def change(info, body, dest):
        dest.writestr(info, b"X" * len(body) if info.filename.endswith("document.pdf") else body)
    target, receipt = rewrite(tmp_path, change)
    with pytest.raises(ValueError, match="content digest"):
        verify(target, receipt)


def test_duplicate_zip_members_rejected(tmp_path):
    def duplicate(info, body, dest):
        dest.writestr(info, body)
        if info.filename == "manifest.json":
            with pytest.warns(UserWarning):
                dest.writestr(info, body)
    target, receipt = rewrite(tmp_path, duplicate)
    with pytest.raises(ValueError, match="Duplicate ZIP"):
        verify(target, receipt)


def test_symlink_zip_member_rejected(tmp_path):
    def symlink(info, body, dest):
        if info.filename.endswith("document.pdf"):
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
        dest.writestr(info, body)
    target, receipt = rewrite(tmp_path, symlink)
    with pytest.raises(ValueError, match="member type"):
        verify(target, receipt)


def test_unlisted_zip_payload_rejected(tmp_path):
    def extra(info, body, dest):
        dest.writestr(info, body)
        if info.filename == "manifest.json":
            dest.writestr("files/unlisted", b"never declared")
    target, receipt = rewrite(tmp_path, extra)
    with pytest.raises(ValueError, match="denominator"):
        verify(target, receipt)


def test_zip_traversal_rejected_before_clean_directory_creation(tmp_path):
    def traversal(info, body, dest):
        if info.filename.endswith("document.pdf"):
            info.filename = "../outside"
        dest.writestr(info, body)
    target, receipt = rewrite(tmp_path, traversal)
    clean = tmp_path / "clean"
    with pytest.raises(ValueError, match="path"):
        verify(target, receipt, clean)
    assert not clean.exists()


def test_total_uncompressed_size_limit_is_enforced(tmp_path, monkeypatch):
    _, target, receipt = package(tmp_path)
    monkeypatch.setattr("white_list_archive.storage.recovery_bundle.MAX_TOTAL_BYTES", 1)
    with pytest.raises(ValueError, match="total byte limit"):
        verify(target, receipt)


def test_export_never_silently_discovers_extra_files(tmp_path):
    root = tmp_path / "private"
    root.mkdir()
    (root / "included").write_bytes(b"exact")
    (root / "credential-must-not-be-packed").write_bytes(b"secret")
    target = tmp_path / "selected.zip"
    receipt = export_bundle(root, [{"path": "included", "role": "original"}], target)
    assert receipt["files_verified"] == 1
    with zipfile.ZipFile(target) as archive:
        assert archive.namelist() == ["manifest.json", "files/included"]
