from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from white_list_archive.publishing import archive_replay_observations as observations
from white_list_archive.publishing import public_national_registry as registry


def _manifest() -> dict:
    return {
        "code_revision": "a" * 40,
        "sources": [
            {
                "source_key": "alpha",
                "parser": "example_parser",
                "parser_revision": "example_parser@7",
                "configuration_sha256": "b" * 64,
                "resources": [
                    {
                        "label": "listed",
                        "capture": {"capture_id": "22222222-2222-4222-8222-222222222222"},
                    },
                    {
                        "label": "applicants",
                        "capture": {"capture_id": "11111111-1111-4111-8111-111111111111"},
                    },
                ],
            }
        ],
    }


def test_capture_inputs_preserve_labels_and_capture_identity() -> None:
    binding = _manifest()["sources"][0]
    assert observations._binding_capture_inputs(binding) == [
        {
            "label": "applicants",
            "capture_id": "11111111-1111-4111-8111-111111111111",
        },
        {
            "label": "listed",
            "capture_id": "22222222-2222-4222-8222-222222222222",
        },
    ]


def test_parse_snapshot_is_persisted_before_downstream_release_failure(monkeypatch) -> None:
    manifest = _manifest()
    config = {"sources": [{"source_key": "alpha", "parser": "example_parser"}]}
    monkeypatch.setattr(observations, "validate_release_manifest", lambda manifest, config: {})

    calls: list[dict] = []

    def parser(source_input, parse_cfg):
        return SimpleNamespace(
            records=[{"name": "ACME", "source_key": parse_cfg["source_key"]}],
            diagnostics={"parser": "example_parser", "parser_version": "7"},
        )

    def persist_one(source_key, binding, capture_inputs, batch, started_at, completed_at):
        calls.append(
            {
                "source_key": source_key,
                "capture_inputs": capture_inputs,
                "records": batch.records,
                "started_at": started_at,
                "completed_at": completed_at,
            }
        )
        return {
            "parse_run_id": "33333333-3333-4333-8333-333333333333",
            "snapshot_sha256": "c" * 64,
            "record_count": len(batch.records),
        }

    monkeypatch.setattr(registry, "_parse_source", parser)
    with pytest.raises(RuntimeError, match="later national gate failed"):
        with observations.persist_replay_parse_observations(
            manifest,
            config,
            "postgresql://private/evidence",
            persist_one=persist_one,
        ) as persisted:
            batch = registry._parse_source(
                Path("/tmp/archived-input"),
                {"source_key": "alpha", "parser": "example_parser"},
            )
            assert batch.records[0]["name"] == "ACME"
            assert len(persisted) == 1
            # Simulate any later source-level/global publication rejection. The
            # parser snapshot has already crossed its independent commit boundary.
            raise RuntimeError("later national gate failed")

    assert len(calls) == 1
    assert calls[0]["source_key"] == "alpha"
    assert [row["label"] for row in calls[0]["capture_inputs"]] == [
        "applicants",
        "listed",
    ]
    assert calls[0]["started_at"].tzinfo is not None
    assert calls[0]["completed_at"] >= calls[0]["started_at"]
    # The context manager must never leave the global parser hook installed.
    assert registry._parse_source is parser


def test_one_source_cannot_be_interpreted_twice_in_one_replay(monkeypatch) -> None:
    manifest = _manifest()
    config = {"sources": [{"source_key": "alpha", "parser": "example_parser"}]}
    monkeypatch.setattr(observations, "validate_release_manifest", lambda manifest, config: {})
    monkeypatch.setattr(
        registry,
        "_parse_source",
        lambda source_input, parse_cfg: SimpleNamespace(records=[], diagnostics={}),
    )

    def persist_one(source_key, binding, capture_inputs, batch, started_at, completed_at):
        return {
            "parse_run_id": "33333333-3333-4333-8333-333333333333",
            "snapshot_sha256": "c" * 64,
            "record_count": 0,
        }

    with observations.persist_replay_parse_observations(
        manifest,
        config,
        "postgresql://private/evidence",
        persist_one=persist_one,
    ):
        cfg = {"source_key": "alpha", "parser": "example_parser"}
        registry._parse_source(Path("/tmp/one"), cfg)
        with pytest.raises(RuntimeError, match="attempted to parse source twice"):
            registry._parse_source(Path("/tmp/two"), cfg)


def test_observation_replay_fails_closed_without_database_writer(monkeypatch) -> None:
    monkeypatch.delenv("EVIDENCE_DATABASE_URL", raising=False)
    with pytest.raises(SystemExit, match="observation-persisting replay cannot advance"):
        observations.main(
            [
                "--source-config",
                "/tmp/not-read-config.json",
                "--release-manifest",
                "/tmp/not-read-release.json",
                "--runtime-code-revision",
                "a" * 40,
            ]
        )
