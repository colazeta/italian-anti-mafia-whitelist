"""No cross-revision reuse without exact, complete interpretation Git objects."""
from pathlib import Path
import ast
import subprocess

import pytest

from white_list_archive.acquisition import interpretation_code as code
from white_list_archive.acquisition.auto_transform import _reuse_existing_snapshot


def _code_repository(tmp_path):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(tmp_path), *args], stderr=subprocess.DEVNULL).decode().strip()
    git('init')
    git('config', 'user.email', 'fixture@example.invalid')
    git('config', 'user.name', 'Synthetic fixture')
    for path in code.INTERPRETATION_PATHS:
        target = tmp_path/path
        if path.endswith(('.py', '.toml')):
            target.parent.mkdir(parents=True, exist_ok=True)
        else:
            target.mkdir(parents=True, exist_ok=True)
            target = target/'fixture.py'
        target.write_text('original\n')
    def commit():
        git('add', '.')
        git('commit', '-m', 'synthetic')
        return git('rev-parse', 'HEAD')
    return commit


@pytest.mark.parametrize('path', sorted(code.POST_INTERPRETATION_PATHS))
def test_downstream_review_tool_addition_edit_and_deletion_reuse_the_same_complete_footprint(tmp_path, path):
    commit = _code_repository(tmp_path)
    first = commit()
    target = tmp_path/path
    target.write_text('new release-only tool\n')
    second = commit()
    target.write_text('changed release-only tool\n')
    third = commit()
    target.unlink()
    fourth = commit()
    fingerprints = [code.code_objects(revision, tmp_path) for revision in (first, second, third, fourth)]
    assert fingerprints[0] is not None
    assert all(value == fingerprints[0] for value in fingerprints)


@pytest.mark.parametrize('name', ['public_contract.py', 'public_national_registry.py', 'new_unknown_helper.py', 'publication_handoff_extra.py'])
def test_contract_dispatcher_and_unknown_publishing_modules_still_invalidate_reuse(tmp_path, name):
    commit = _code_repository(tmp_path)
    first = commit()
    target = tmp_path/'src/white_list_archive/publishing'/name
    target.write_text('new potentially relevant interpretation code\n')
    second = commit()
    assert code.code_objects(first, tmp_path) != code.code_objects(second, tmp_path)
    target.write_text('changed interpretation code\n')
    third = commit()
    assert code.code_objects(second, tmp_path) != code.code_objects(third, tmp_path)


def test_publishing_tree_containing_only_excluded_metadata_tools_is_not_complete(tmp_path):
    commit = _code_repository(tmp_path)
    (tmp_path/'src/white_list_archive/publishing/fixture.py').unlink()
    (tmp_path/sorted(code.POST_INTERPRETATION_PATHS)[0]).write_text('downstream only\n')
    revision = commit()
    assert code.code_objects(revision, tmp_path) is None


def test_retained_interpretation_modules_do_not_import_the_excluded_downstream_tools():
    root = Path(__file__).resolve().parents[1]
    excluded = {path.removeprefix('src/').removesuffix('.py').replace('/', '.')
                for path in code.POST_INTERPRETATION_PATHS}
    files = [p for directory in ('parsers', 'publishing')
             for p in (root/'src/white_list_archive'/directory).rglob('*.py')
             if p.relative_to(root).as_posix() not in code.POST_INTERPRETATION_PATHS]
    files.append(root/'src/white_list_archive/acquisition/national_index.py')
    for path in files:
        current = '.'.join(path.relative_to(root/'src').with_suffix('').parts)
        package = current.rpartition('.')[0]
        for node in ast.walk(ast.parse(path.read_text())):
            targets = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ''
                if node.level:
                    base = '.'.join(package.split('.')[:len(package.split('.'))-node.level+1] + ([base] if base else []))
                targets = [base] + [base + '.' + alias.name for alias in node.names]
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                targets = [node.value]  # Include literal dynamic module imports.
            assert not excluded.intersection(targets), (path, targets)


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
