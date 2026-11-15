"""No cross-revision reuse without exact, complete interpretation Git objects."""
from pathlib import Path
import subprocess

import pytest

from white_list_archive.acquisition import interpretation_code as code
from white_list_archive.acquisition.auto_transform import _reuse_existing_snapshot


def test_complete_git_footprint_ignores_operational_docs_but_tracks_parser_and_runtime(tmp_path):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], stderr=subprocess.DEVNULL).decode().strip()
    git("init")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "user.name", "Synthetic fixture")
    for path in code.INTERPRETATION_PATHS:
        target = tmp_path / path
        if path.endswith((".py", ".toml")):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("original\n")
        else:
            target.mkdir(parents=True, exist_ok=True)
            (target / "fixture.py").write_text("original\n")
    def commit():
        git("add", ".")
        git("commit", "-m", "synthetic")
        return git("rev-parse", "HEAD")
    first = commit()
    (tmp_path / "README.md").write_text("operational note\n")
    second = commit()
    assert code.code_objects(first, tmp_path) == code.code_objects(second, tmp_path)
    parser = tmp_path / code.INTERPRETATION_PATHS[0] / "fixture.py"
    parser.write_text("changed extraction\n")
    third = commit()
    assert code.code_objects(second, tmp_path) != code.code_objects(third, tmp_path)
    (tmp_path / "pyproject.toml").write_text("changed runtime\n")
    fourth = commit()
    assert code.code_objects(third, tmp_path) != code.code_objects(fourth, tmp_path)
    assert code.code_objects("0"*40, tmp_path) is None
    assert code.code_objects("HEAD;anything", tmp_path) is None


def test_absent_or_partial_code_never_proves_equivalence(monkeypatch):
    monkeypatch.setattr(code, "code_objects", lambda rev: None)
    assert not code.equivalent_revision("a"*40, "b"*40)
    assert not code.equivalent_revision("", "")
    assert code.equivalent_revision("a"*40, "a"*40)


@pytest.mark.parametrize("old_version,equivalent,expected", [
    ("physical@2+git." + "a"*40, True, "first"),
    ("physical@2+git." + "a"*40, False, False),
    ("unversioned", True, False),
])
def test_reuse_requires_code_and_complete_input_equivalence_and_rehashes_all_copies(monkeypatch, old_version, equivalent, expected):
    statements, reads = [], []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def execute(self, sql, args): statements.append((sql, args))
        def fetchall(self):
            return [(name, {"primary": "1"*64}, old_version) for name in ("first", "second")]
    class Conn:
        def cursor(self): return Cursor()
    monkeypatch.setattr(code, "equivalent_revision", lambda old, new: equivalent)
    def read(conn, identity):
        reads.append(identity)
        return [{"source_status": "listed"}], {"parser_version": "2"}
    monkeypatch.setattr("white_list_archive.acquisition.auto_transform.read_snapshot_verified", read)
    actual = _reuse_existing_snapshot(Conn(), parser_name="physical", code_revision="b"*40,
        configuration_hash="2"*64, input_hashes={"primary": "1"*64},
        capture_inputs=[{"label": "primary", "capture_id": "check"}])
    assert actual == expected
    assert reads == (["first", "second"] if expected else [])
    assert len(statements) == (2 if expected else 1)


def test_corrupt_historical_snapshot_never_links_a_new_capture(monkeypatch):
    monkeypatch.setattr(code, "equivalent_revision", lambda old, new: True)
    inserts = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def execute(self, sql, args):
            if "INSERT" in sql: inserts.append(args)
        def fetchall(self): return [("bad", {"primary": "1"*64}, "physical@2+git."+"a"*40)]
    class Conn:
        def cursor(self): return Cursor()
    def corrupt(*_): raise RuntimeError("integrity failed")
    monkeypatch.setattr("white_list_archive.acquisition.auto_transform.read_snapshot_verified", corrupt)
    with pytest.raises(RuntimeError, match="integrity"):
        _reuse_existing_snapshot(Conn(), parser_name="physical", code_revision="b"*40,
            configuration_hash="2"*64, input_hashes={"primary": "1"*64},
            capture_inputs=[{"label": "primary", "capture_id": "check"}])
    assert inserts == []
