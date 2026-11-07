"""Execute the real dispatch preflights against a temporary Git catalogue."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ("replay-frozen-release.yml", "promote-frozen-release.yml")


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


@pytest.fixture
def catalogue(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "commit", "--allow-empty", "-qm", "base")
    revision = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "data/releases").mkdir(parents=True)
    return tmp_path, revision


def _run_preflight(workflow, catalogue, version, *, revision_override=None):
    root, revision = catalogue
    manifest = {"schema_version": version, "release_id": "test-candidate",
                "code_revision": revision_override or revision,
                "sources": [{"source_key": "fixture"}]}
    (root / "data/releases/candidate.json").write_text(json.dumps(manifest))
    _git(root, "add", "data/releases/candidate.json")
    workflow_text = (ROOT / ".github/workflows" / workflow).read_text()
    preflight = textwrap.dedent(workflow_text.split("python - <<'PY'\n", 1)[1].split("          PY", 1)[0])
    # Freeze outside the shared /tmp path used by production Actions.
    frozen = root / "frozen.json"
    preflight = preflight.replace("/tmp/frozen-release.json", str(frozen))
    result = subprocess.run([sys.executable, "-c", preflight], cwd=root, capture_output=True,
                            text=True, env={**os.environ,
                            "RELEASE_MANIFEST_INPUT": "data/releases/candidate.json",
                            "GITHUB_OUTPUT": str(root / "output")})
    return result, frozen


@pytest.mark.parametrize("workflow", WORKFLOWS)
@pytest.mark.parametrize("version", (1, 2))
def test_dispatch_preflight_accepts_supported_versions_without_changing_manifest(workflow, catalogue, version):
    result, frozen = _run_preflight(workflow, catalogue, version)
    assert result.returncode == 0, result.stderr
    root, revision = catalogue
    assert frozen.read_bytes() == (root / "data/releases/candidate.json").read_bytes()
    assert f"code_revision={revision}\n" in (root / "output").read_text()


@pytest.mark.parametrize("workflow", WORKFLOWS)
@pytest.mark.parametrize("version", (0, 3, True, "2", None, []))
def test_dispatch_preflight_rejects_unknown_or_non_integer_versions(workflow, catalogue, version):
    result, frozen = _run_preflight(workflow, catalogue, version)
    assert result.returncode != 0
    assert "Unsupported frozen release schema_version" in result.stderr
    assert not frozen.exists()


@pytest.mark.parametrize("workflow", WORKFLOWS)
def test_v2_dispatch_still_rejects_revision_outside_main_history(workflow, catalogue):
    result, frozen = _run_preflight(workflow, catalogue, 2, revision_override="f" * 40)
    assert result.returncode != 0
    assert "must be an ancestor of current main" in result.stderr
    assert not frozen.exists()
