"""Persist private parser observations while replaying immutable archived captures.

This module is an archive/recovery execution boundary, not a publication shortcut.
The existing frozen-release builder already verifies every selected ContentObject and
immutable capture-catalogue receipt before parsers can access bytes. This wrapper adds
one invariant: once a parser returns successfully, its complete records/diagnostics are
committed to the private relational evidence database before downstream source/release
validation can fail.

A parser result persisted here is an interpretation observation. It does not create a
SourceEdition, does not approve the parse for publication and does not promote public
or canonical facts.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Iterator

try:
    import psycopg
except ImportError as exc:  # pragma: no cover - exercised only without database extra
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from white_list_archive.persistence.parse_snapshot import persist_parse_snapshot
from white_list_archive.publishing import public_national_build as national_build
from white_list_archive.publishing import public_national_registry as registry
from white_list_archive.publishing.frozen_release import validate_release_manifest

_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


PersistOne = Callable[
    [str, dict[str, Any], list[dict[str, str]], Any, datetime, datetime],
    dict[str, Any],
]


def _binding_capture_inputs(binding: dict[str, Any]) -> list[dict[str, str]]:
    """Return the exact labelled capture/check set pinned for one source."""
    result: list[dict[str, str]] = []
    for resource in binding["resources"]:
        label = resource["label"]
        capture_id = resource["capture"].get("capture_id")
        if not isinstance(label, str) or not label:
            raise ValueError("Frozen release resource lacks an input label")
        if not isinstance(capture_id, str) or not capture_id:
            raise ValueError(f"Frozen release resource {label!r} lacks capture identity")
        result.append({"label": label, "capture_id": capture_id})
    result.sort(key=lambda row: row["label"])
    return result


def _database_persist_one(
    dsn: str,
    binding: dict[str, Any],
    capture_inputs: list[dict[str, str]],
    batch: Any,
    started_at: datetime,
    completed_at: datetime,
    *,
    code_revision: str,
) -> dict[str, Any]:
    """Commit one parser interpretation independently of the global release."""
    if psycopg is None:
        raise RuntimeError("psycopg is required; install the 'database' extra") from _IMPORT_ERROR
    with psycopg.connect(dsn) as conn:
        result = persist_parse_snapshot(
            conn,
            capture_inputs=capture_inputs,
            parser_name=binding["parser"],
            parser_revision=binding["parser_revision"],
            code_revision=code_revision,
            configuration_hash=binding["configuration_sha256"],
            started_at=started_at,
            completed_at=completed_at,
            records=batch.records,
            diagnostics=batch.diagnostics,
        )
        # Commit at the per-source boundary. A later parser, source validation or
        # national release failure must not erase an already-produced interpretation.
        conn.commit()
        return result


@contextmanager
def persist_replay_parse_observations(
    release_manifest: dict[str, Any],
    config: dict[str, Any],
    dsn: str,
    *,
    persist_one: PersistOne | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """Persist each successful parser return before downstream release acceptance.

    ``validate_release_manifest`` binds exact source/resource captures before this
    hook is installed. The surrounding frozen-release builder separately performs
    catalogue and byte readback for *all* selected inputs before parser access.

    The hook runs immediately after ``_parse_source`` returns and therefore before
    ``_validate_batch``, semantic approval, aggregation and global registry validation.
    A parser execution may consequently be preserved even if it is later rejected for
    publication. That is intentional: parse execution success and release acceptance
    are distinct states.
    """
    if not isinstance(dsn, str) or not dsn.strip():
        raise ValueError("EVIDENCE_DATABASE_URL is required for observation-persisting replay")
    validate_release_manifest(release_manifest, config)
    code_revision = release_manifest.get("code_revision")
    if not isinstance(code_revision, str) or _GIT_SHA_RE.fullmatch(code_revision) is None:
        raise ValueError("Frozen release code_revision must be an exact lowercase Git SHA")

    bindings = {item["source_key"]: item for item in release_manifest["sources"]}
    original_parse = registry._parse_source
    persisted: list[dict[str, Any]] = []
    seen: set[str] = set()

    def database_writer(
        source_key: str,
        binding: dict[str, Any],
        capture_inputs: list[dict[str, str]],
        batch: Any,
        started_at: datetime,
        completed_at: datetime,
    ) -> dict[str, Any]:
        return _database_persist_one(
            dsn,
            binding,
            capture_inputs,
            batch,
            started_at,
            completed_at,
            code_revision=code_revision,
        )

    writer = persist_one or database_writer

    def parse_and_persist(source_input: Any, parse_cfg: dict[str, Any]):
        source_key = parse_cfg.get("source_key")
        if not isinstance(source_key, str) or source_key not in bindings:
            raise RuntimeError("Frozen replay parser received an unpinned source_key")
        if source_key in seen:
            raise RuntimeError(f"Frozen replay attempted to parse source twice: {source_key}")
        binding = bindings[source_key]
        if parse_cfg.get("parser") != binding["parser"]:
            raise RuntimeError(f"{source_key}: parser identity differs from frozen release pin")

        started_at = datetime.now(timezone.utc)
        batch = original_parse(source_input, parse_cfg)
        completed_at = datetime.now(timezone.utc)
        capture_inputs = _binding_capture_inputs(binding)
        outcome = writer(
            source_key,
            binding,
            capture_inputs,
            batch,
            started_at,
            completed_at,
        )
        persisted.append(
            {
                "source_key": source_key,
                "parse_run_id": outcome.get("parse_run_id"),
                "snapshot_sha256": outcome.get("snapshot_sha256"),
                "record_count": outcome.get("record_count"),
            }
        )
        seen.add(source_key)
        return batch

    registry._parse_source = parse_and_persist
    try:
        yield persisted
    finally:
        registry._parse_source = original_parse


def _preflight_args(argv: list[str] | None) -> tuple[Path, Path, str]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source-config", type=Path, required=True)
    parser.add_argument("--release-manifest", type=Path, required=True)
    parser.add_argument("--runtime-code-revision")
    args, _ = parser.parse_known_args(argv)
    runtime_revision = args.runtime_code_revision or os.environ.get("GITHUB_SHA", "")
    if _GIT_SHA_RE.fullmatch(runtime_revision or "") is None:
        raise ValueError("Observation-persisting replay requires an exact runtime code revision")
    return args.source_config, args.release_manifest, runtime_revision


def main(argv: list[str] | None = None) -> int:
    """Run the existing national frozen replay with mandatory parse persistence."""
    source_config_path, release_manifest_path, runtime_revision = _preflight_args(argv)
    dsn = os.environ.get("EVIDENCE_DATABASE_URL", "")
    if not dsn:
        raise SystemExit(
            "EVIDENCE_DATABASE_URL is not configured; archived inputs remain recoverable, "
            "but observation-persisting replay cannot advance"
        )

    config = json.loads(source_config_path.read_text(encoding="utf-8"))
    release_manifest = json.loads(release_manifest_path.read_text(encoding="utf-8"))
    validate_release_manifest(release_manifest, config)
    if release_manifest.get("code_revision") != runtime_revision:
        raise SystemExit("Frozen release code revision differs from replay runtime")

    original_builder = national_build.build_registry_from_release
    completed_sources: list[dict[str, Any]] = []

    def replay_with_persistence(
        runtime_config: dict[str, Any],
        work_dir: Path,
        runtime_manifest: dict[str, Any],
        store: Any,
    ) -> dict[str, Any]:
        nonlocal completed_sources
        with persist_replay_parse_observations(
            runtime_manifest,
            runtime_config,
            dsn,
        ) as persisted:
            built = original_builder(runtime_config, work_dir, runtime_manifest, store)
            completed_sources = list(persisted)
        if len(completed_sources) != len(runtime_config["sources"]):
            raise RuntimeError(
                "Frozen replay completed without a persisted parser observation for every source"
            )
        return built

    national_build.build_registry_from_release = replay_with_persistence
    try:
        result = national_build.main(argv)
    finally:
        national_build.build_registry_from_release = original_builder

    # Redacted operational evidence only: no records, source bytes, database locator
    # or private provider coordinates are written to the public workflow log.
    print(
        json.dumps(
            {
                "observation_persistence": "persisted",
                "source_parse_snapshots_committed": len(completed_sources),
                "release_id": release_manifest["release_id"],
                "code_revision": runtime_revision,
            },
            sort_keys=True,
        )
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
