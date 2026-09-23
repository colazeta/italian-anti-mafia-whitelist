from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "promote-frozen-release.yml"
LEGACY_WORKFLOW = ROOT / ".github" / "workflows" / "public-pages.yml"


def test_frozen_staging_is_manual_main_only_and_uses_protected_archive() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "release_manifest:" in text
    assert "if: github.ref == 'refs/heads/main'" in text
    assert "environment: evidence-archive" in text
    assert "git', 'ls-files', '--error-unmatch'" in text
    assert "git', 'merge-base', '--is-ancestor'" in text
    assert "ref: ${{ steps.release.outputs.code_revision }}" in text


def test_frozen_staging_has_no_live_source_build_or_fallback() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "archive_replay_observations" in text
    assert "--release-manifest /tmp/frozen-release.json" in text
    assert "--runtime-code-revision \"$PINNED_CODE_REVISION\"" in text
    assert "white-list-public-national-build" not in text
    assert "legacy_live_migration_mode" not in text
    assert "curl " not in text
    assert "wget " not in text


def test_frozen_staging_requires_observation_database_and_public_gates() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "EVIDENCE_DATABASE_URL" in text
    assert (
        "Private evidence database writer is not configured; frozen candidate staging cannot proceed"
        in text
    )
    assert "python -m white_list_archive.publishing.public_artifact public-site" in text
    assert "node tests/public_portal_browser.cjs" in text
    assert "python -m white_list_archive.publishing.public_links public-site" in text


def test_frozen_staging_does_not_create_a_second_pages_publisher() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    legacy = LEGACY_WORKFLOW.read_text(encoding="utf-8")
    assert "actions/upload-pages-artifact@v4" not in text
    assert "actions/deploy-pages@v4" not in text
    assert "environment:\n      name: github-pages" not in text
    assert "actions/upload-pages-artifact@v4" in legacy
    assert "actions/deploy-pages@v4" in legacy


def test_frozen_staging_never_uploads_private_source_workspace() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "path: /tmp/frozen-publication" not in text
    assert "path: /tmp/frozen-release.json" not in text
    assert "path: public-site/" in text
    assert "path: public-site\n" not in text


def test_legacy_publication_remains_separate_during_migration() -> None:
    legacy = LEGACY_WORKFLOW.read_text(encoding="utf-8")
    assert "white-list-public-national-build" in legacy
    assert "--release-manifest" not in legacy
