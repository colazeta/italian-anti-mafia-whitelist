"""Prepare a reviewed selector proposal; never approve, merge or deploy it.

Runs inside the existing main-only candidate preserver. Its existing contents
permission may write one deterministic branch, while the authorised orchestrator
opens/reviews its PR and the sole Public retro portal remains the publisher.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from white_list_archive.acquisition.published_monitoring import synchronise
from .public_contract import validate_registry
from .public_snapshot import FILES, restore, validate_manifest, verify

SELECTOR = "data/publication/public_snapshot.json"
MONITORING = "data/monitoring/national_coverage.json"
INTENT = "data/publication/incremental_release_intent.json"
PROPOSAL_PATHS = (SELECTOR, MONITORING)
APPROVAL_PATHS = (
    "src/white_list_archive/publishing", "src/white_list_archive/parsers",
    "src/white_list_archive/acquisition/published_monitoring.py",
    "src/white_list_archive/acquisition/national_index.py", "data/source_registry",
    "data/publication", "public-site", "pyproject.toml",
    ".github/workflows/public-registry-review.yml", ".github/workflows/public-pages.yml",
    "tests/public_portal_browser.cjs", "tests/public_snapshot_browser.cjs",
)


def _digest(value):
    # Same canonical contract as frozen_release.configuration_sha256, without
    # importing every physical parser into a metadata-only preservation job.
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _groups(registry):
    records = defaultdict(list)
    for row in registry["records"]:
        records[row["source_key"]].append(row)
    reports = {row["source_key"]: row for row in registry["meta"]["sources"]}
    if len(reports) != len(registry["meta"]["sources"]) or set(reports) != set(records):
        raise ValueError("Missing or duplicate public source scope")
    return records, reports


def records_digest(records):
    """Pin every approved public value, including parser and original identity."""
    return _digest(sorted(records, key=lambda row: row["record_locator"]))


def _without_check_time(report):
    return {key: value for key, value in report.items() if key != "document_checked_at"}


def prepare_proposal(*, selected_manifest, candidate_manifest, selected_bytes, candidate_bytes,
                     config, monitoring, intent=None):
    """Pure, fail-closed selection gate after independent five-file verification."""
    validate_manifest(selected_manifest)
    validate_manifest(candidate_manifest)
    verify(selected_bytes, selected_manifest["files"]["registry.json"], "selected registry.json")
    verify(candidate_bytes, candidate_manifest["files"]["registry.json"], "candidate registry.json")
    selected, candidate = json.loads(selected_bytes), json.loads(candidate_bytes)
    validate_registry(selected)
    validate_registry(candidate)
    before, old_reports = _groups(selected)
    after, reports = _groups(candidate)
    for report in reports.values():
        checked = datetime.fromisoformat(report.get("document_checked_at", "").replace("Z", "+00:00"))
        if checked.tzinfo is None:
            raise ValueError("Candidate source has no unambiguous verification time")
    if set(before) != set(after):
        raise ValueError("Incremental handoff cannot change source coverage")
    for field in ("authority_count", "register_count", "source_count"):
        if selected["meta"][field] != candidate["meta"][field]:
            raise ValueError("Incremental handoff changed public coverage")
    changed = {key for key in before if records_digest(before[key]) != records_digest(after[key])
               or _without_check_time(old_reports[key]) != _without_check_time(reports[key])}
    receipt = {"schema_version": 1, "state": "no_release_delta" if not changed else "review_intent_required",
               "candidate_release_tag": candidate_manifest["release_tag"],
               "selected_release_tag": selected_manifest["release_tag"],
               "selected_manifest_sha256": _digest(selected_manifest),
               "candidate_manifest_sha256": _digest(candidate_manifest),
               "source_config_sha256": _digest(config), "changed_sources": sorted(changed),
               "publications": 0, "approval_granted": False}
    if not changed or intent is None:
        return receipt, {}
    if (set(intent) != {"schema_version", "baseline_manifest_sha256", "source_config_sha256", "review_document", "changes"}
            or type(intent["schema_version"]) is not int or intent["schema_version"] != 1
            or intent["baseline_manifest_sha256"] != _digest(selected_manifest)
            or intent["source_config_sha256"] != _digest(config)):
        raise ValueError("Stale or unreviewed publication intent")
    document = intent["review_document"]
    if (not isinstance(document, str) or not re.fullmatch(r"docs/sources/[A-Za-z0-9_-]+\.md", document)):
        raise ValueError("Publication intent lacks a source review document")
    changes = intent["changes"]
    if not isinstance(changes, dict) or set(changes) != changed:
        raise ValueError("Candidate differs from the explicitly reviewed source scope")
    configured = {row["source_key"]: row for row in config["sources"]}
    if len(configured) != len(config["sources"]) or set(configured) != set(after):
        raise ValueError("Public candidate does not cover the reviewed configuration")
    # Both populations are required per register, even if only one has changed.
    populations = defaultdict(set)
    for cfg in configured.values():
        scope = cfg["population_scope"]
        populations[(cfg["authority_key"], cfg["register_key"])].update(
            {"listed", "applicant"} if scope == "listed_and_applicant" else {scope})
    for key, spec in changes.items():
        cfg = configured[key]
        if populations[(cfg["authority_key"], cfg["register_key"])] != {"listed", "applicant"}:
            raise ValueError("Incomplete listed/applicant register scope")
        if (not isinstance(spec, dict) or set(spec) != {"count", "statuses", "reference_date", "sha256", "parser", "records_sha256"}
                or type(spec["count"]) is not int or spec["count"] <= 0
                or not isinstance(spec["statuses"], dict)
                or any(type(n) is not int or n <= 0 for n in spec["statuses"].values())
                or not re.fullmatch(r"[0-9a-f]{64}", spec["records_sha256"])):
            raise ValueError("Unreviewed public source profile")
        if (not isinstance(spec["reference_date"], str)
                or date.fromisoformat(spec["reference_date"]).isoformat() != spec["reference_date"]
                or not re.fullmatch(r"(?:[0-9a-f]{64}|bundle:[0-9a-f]{64})", spec["sha256"])):
            raise ValueError("Malformed reviewed date/original identity")
        if len(after[key]) != spec["count"] or dict(Counter(r["source_status"] for r in after[key])) != spec["statuses"]:
            raise ValueError("Reviewed source observation/status count mismatch")
        for field in ("reference_date", "sha256", "parser"):
            if reports[key].get(field) != spec[field] or cfg.get(field) != spec[field]:
                raise ValueError("Reviewed source provenance mismatch")
        for field in ("authority_key", "register_key", "population_scope"):
            if reports[key].get(field) != cfg[field]:
                raise ValueError("Reviewed source scope mismatch")
        if not spec["reference_date"] or spec["reference_date"] < old_reports[key]["reference_date"]:
            raise ValueError("Incremental handoff cannot backdate a selected source")
        if records_digest(after[key]) != spec["records_sha256"]:
            raise ValueError("Reviewed full public observation digest mismatch")
    for key in set(before) - changed:
        if old_reports[key] != reports[key]:
            raise ValueError("Unrelated source verification report changed")
    identity = _digest({"baseline": _digest(selected_manifest), "config": _digest(config), "intent": intent})
    receipt.update(state="selector_proposal_ready", review_document=document,
                   proposal_identity=identity, branch="release/select-validated-" + identity[:24])
    updated = synchronise(monitoring, candidate_manifest, candidate_bytes)
    return receipt, {SELECTOR: json.dumps(candidate_manifest, indent=2) + "\n",
                     MONITORING: json.dumps(updated, ensure_ascii=False, indent=2) + "\n"}


def _git(*args, data=None, env=None):
    return subprocess.check_output(["git", *args], input=data, env=env).decode().strip()


def assert_current_base(build_revision, base_revision):
    if not all(re.fullmatch(r"[0-9a-f]{40}", r or "") for r in (build_revision, base_revision)):
        raise ValueError("Exact trusted revisions required")
    subprocess.run(["git", "merge-base", "--is-ancestor", build_revision, base_revision], check=True)
    if _git("diff", "--name-only", build_revision, base_revision, "--", *APPROVAL_PATHS):
        raise ValueError("Candidate approval inputs changed on main")


def choose_build_artifact(artifacts):
    """A rerun of preserve can reuse its successful build's earlier artifact."""
    eligible = []
    for item in artifacts:
        match = re.fullmatch(r"public-portal-review-attempt-([1-9][0-9]*)", item.get("name", ""))
        if match and item.get("expired") is False:
            eligible.append((int(match[1]), item["name"]))
    if not eligible or len({n for n, _ in eligible}) != len(eligible):
        raise ValueError("Missing or ambiguous trusted public build artifact")
    return max(eligible)[1]


def verify_candidate_files(manifest, directory):
    validate_manifest(manifest)
    for name in FILES:
        verify((directory / name).read_bytes(), manifest["files"][name], name)
    return (directory / "registry.json").read_bytes()


def write_proposal_branch(files, receipt, base_revision, *, remote="origin", existing_validator=None):
    """Append one two-file proposal branch; never force-push or mutate main."""
    if set(files) != set(PROPOSAL_PATHS) or receipt.get("state") != "selector_proposal_ready":
        raise ValueError("Unapproved proposal write surface")
    branch = receipt["branch"]
    if not re.fullmatch(r"release/select-validated-[0-9a-f]{24}", branch):
        raise ValueError("Invalid proposal branch")
    existing = _git("ls-remote", "--heads", remote, "refs/heads/" + branch)
    if existing:
        sha = existing.split()[0]
        subprocess.run(["git", "fetch", "--no-tags", remote, "refs/heads/" + branch], check=True)
        ancestor = _git("merge-base", sha, base_revision)
        if set(_git("diff", "--name-only", ancestor, sha).splitlines()) != set(files):
            raise ValueError("Existing proposal branch has an unexpected change surface")
        old_files = {path: _git("show", sha + ":" + path) + "\n" for path in files}
        if existing_validator is not None:
            existing_validator(old_files)
        elif old_files != files:
            raise ValueError("Existing proposal branch has conflicting selector bytes")
        return sha, False
    with tempfile.TemporaryDirectory(prefix="publication-proposal-index-") as td:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(td) / "index"),
               "GIT_AUTHOR_NAME": "github-actions[bot]", "GIT_COMMITTER_NAME": "github-actions[bot]",
               "GIT_AUTHOR_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
               "GIT_COMMITTER_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com"}
        _git("read-tree", base_revision, env=env)
        for path, body in files.items():
            blob = _git("hash-object", "-w", "--stdin", data=body.encode(), env=env)
            _git("update-index", "--add", "--cacheinfo", "100644," + blob + "," + path, env=env)
        tree = _git("write-tree", env=env)
        commit = _git("commit-tree", tree, "-p", base_revision, env=env,
                      data=("Select validated public candidate " + receipt["candidate_release_tag"] + "\n").encode())
        subprocess.run(["git", "push", remote, commit + ":refs/heads/" + branch], check=True, env=env)
    return commit, True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--candidate-data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--write-branch", action="store_true")
    args = parser.parse_args(argv)
    root = Path.cwd()
    subprocess.run(["git", "fetch", "--no-tags", "origin", "main"], check=True)
    build = _git("rev-parse", "HEAD")
    base = _git("rev-parse", "FETCH_HEAD")
    assert_current_base(build, base)
    selected_manifest = json.loads(_git("show", base + ":" + SELECTOR))
    monitoring = json.loads(_git("show", base + ":" + MONITORING))
    config = json.loads((root / "data/publication/multi_prefecture_pilot.json").read_text())
    candidate_manifest = json.loads(args.candidate_manifest.read_text())
    candidate_bytes = verify_candidate_files(candidate_manifest, args.candidate_data)
    intent_path = root / INTENT
    intent = json.loads(intent_path.read_text()) if intent_path.exists() else None
    if intent and not (root / intent.get("review_document", "")).is_file():
        raise ValueError("Reviewed source document is unavailable")
    with tempfile.TemporaryDirectory(prefix="publication-handoff-baseline-") as td:
        restore(selected_manifest, Path(td))
        selected_bytes = (Path(td) / "registry.json").read_bytes()
    receipt, files = prepare_proposal(selected_manifest=selected_manifest, candidate_manifest=candidate_manifest,
        selected_bytes=selected_bytes, candidate_bytes=candidate_bytes, config=config, monitoring=monitoring, intent=intent)
    receipt.update(build_revision=build, base_revision=base)
    if files and args.write_branch:
        # Release byte readback may take time. Recheck main immediately before
        # staging the branch and preserve independently newer monitoring facts.
        subprocess.run(["git", "fetch", "--no-tags", "origin", "main"], check=True)
        base = _git("rev-parse", "FETCH_HEAD")
        assert_current_base(build, base)
        monitoring = json.loads(_git("show", base + ":" + MONITORING))
        files[MONITORING] = json.dumps(synchronise(monitoring, candidate_manifest, candidate_bytes),
                                       ensure_ascii=False, indent=2) + "\n"
        receipt["base_revision"] = base
        def verify_existing(old_files):
            old_manifest = json.loads(old_files[SELECTOR])
            validate_manifest(old_manifest)
            with tempfile.TemporaryDirectory(prefix="publication-existing-proposal-") as td:
                restore(old_manifest, Path(td))
                raw = (Path(td) / "registry.json").read_bytes()
                old_receipt, _ = prepare_proposal(selected_manifest=selected_manifest,
                    candidate_manifest=old_manifest, selected_bytes=selected_bytes, candidate_bytes=raw,
                    config=config, monitoring=monitoring, intent=intent)
            if (old_receipt["state"] != "selector_proposal_ready"
                    or old_receipt["proposal_identity"] != receipt["proposal_identity"]
                    or json.loads(old_files[MONITORING]) != synchronise(monitoring, old_manifest, raw)):
                raise ValueError("Existing proposal requires renewed source/monitoring review")
            receipt.update(old_receipt)
            files.clear()
            files.update(old_files)
        receipt["commit"], _ = write_proposal_branch(files, receipt, base, existing_validator=verify_existing)
        receipt["branch_state"] = "verified"
    args.output.mkdir(parents=True, exist_ok=True)
    for path, body in files.items():
        target = args.output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
    (args.output / "proposal.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
