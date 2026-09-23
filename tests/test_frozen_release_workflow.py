from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "replay-frozen-release.yml"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_replay_is_manual_main_only_and_uses_protected_private_archive() -> None:
    text = _workflow()
    assert "workflow_dispatch:" in text
    assert "if: github.ref == 'refs/heads/main'" in text
    assert "environment: evidence-archive" in text
    assert "EVIDENCE_BUCKET: ${{ vars.EVIDENCE_BUCKET }}" in text
    assert "EVIDENCE_ENDPOINT: ${{ vars.EVIDENCE_ENDPOINT }}" in text
    assert "AWS_ACCESS_KEY_ID: ${{ secrets.EVIDENCE_ACCESS_KEY_ID }}" in text
    assert "AWS_SECRET_ACCESS_KEY: ${{ secrets.EVIDENCE_SECRET_ACCESS_KEY }}" in text


def test_replay_freezes_manifest_then_checks_out_exact_pinned_main_history() -> None:
    text = _workflow()
    assert "release_manifest must resolve under data/releases/" in text
    assert "git ls-files --error-unmatch \"$RELEASE_MANIFEST_INPUT\"" in text
    assert "fetch-depth: 0" in text
    assert "['git', 'merge-base', '--is-ancestor', revision, 'HEAD']" in text
    assert "Frozen release code_revision must be an ancestor of current main" in text
    assert "shutil.copyfile(candidate, '/tmp/frozen-release.json')" in text
    assert "code_revision={revision}" in text
    assert "ref: ${{ steps.release.outputs.code_revision }}" in text
    assert "clean: true" in text


def test_replay_invokes_archive_only_release_path_and_keeps_products_private() -> None:
    text = _workflow()
    assert "white-list-public-national-build" in text
    assert "--release-manifest /tmp/frozen-release.json" in text
    assert "--runtime-code-revision \"$PINNED_CODE_REVISION\"" in text
    assert "--registry-json /tmp/frozen-replay/output/registry.json" in text
    assert "source_mode': 'archived_frozen_release'" in text
    assert "actions/upload-artifact" not in text
    assert "actions/deploy-pages" not in text
    assert "upload-pages-artifact" not in text
    assert "public-site/data/registry.json" not in text


def test_replay_workflow_does_not_acquire_official_source_urls() -> None:
    text = _workflow()
    lowered = text.lower()
    assert "resource_url" not in lowered
    assert "curl " not in lowered
    assert "wget " not in lowered
    assert "--release-manifest" in text
