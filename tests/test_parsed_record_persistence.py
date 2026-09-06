from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from white_list_archive.persistence.parsed_records import IDENTIFIER_FIELD, NAME_FIELD

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/cosenza_parser"


def test_parse_operational_schema_patch_is_applied_and_immutable():
    apply_sql = (ROOT / "db/apply.sql").read_text(encoding="utf-8")
    assert "046_parse_operational_metadata.sql" in apply_sql
    ddl = (ROOT / "db/schema/046_parse_operational_metadata.sql").read_text(encoding="utf-8")
    for required in [
        "parse_run_code",
        "raw_record_text",
        "source_field_definition_locator_unique",
        "source_field_value_locator_unique",
        "entity_mention_record_role_unique",
        "parsed_record_immutable",
        "create a new parse run instead",
    ]:
        assert required in ddl


def test_parser_fixture_capture_hashes_are_exact():
    for stem in ["before", "after"]:
        text = (FIXTURES / f"{stem}.txt").read_text(encoding="utf-8")
        manifest = json.loads((FIXTURES / f"{stem}_capture.json").read_text(encoding="utf-8"))
        assert hashlib.sha256(text.encode("utf-8")).hexdigest() == manifest["text_sha256"]


def test_parser_emits_reproducible_parse_manifest(tmp_path: Path):
    env = os.environ.copy()
    env["GITHUB_SHA"] = "0123456789abcdef0123456789abcdef01234567"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "white_list_archive.parsers.cosenza_combined_mentions",
            str(FIXTURES / "before.txt"),
            str(FIXTURES / "after.txt"),
            "--output-dir",
            str(tmp_path),
        ],
        check=True,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    manifest = json.loads((tmp_path / "parse_manifest.json").read_text(encoding="utf-8"))
    assert manifest["parser_version"] == "1"
    assert manifest["processing_revision"] == env["GITHUB_SHA"]
    assert len(manifest["configuration_hash"]) == 64
    inputs = {item["label"]: item for item in manifest["inputs"]}
    assert inputs["before"]["record_count"] == 2
    assert inputs["after"]["record_count"] == 3
    assert inputs["before"]["text_sha256"] == json.loads(
        (FIXTURES / "before_capture.json").read_text(encoding="utf-8")
    )["text_sha256"]
    assert inputs["after"]["text_sha256"] == json.loads(
        (FIXTURES / "after_capture.json").read_text(encoding="utf-8")
    )["text_sha256"]


def test_parser_v1_persists_only_structurally_isolated_source_fields():
    definitions = [NAME_FIELD, IDENTIFIER_FIELD]
    assert {field["source_label"] for field in definitions} == {
        "Ragione sociale",
        "Codice fiscale/Partita IVA",
    }
    assert all("source_status" not in field["structural_locator"] for field in definitions)


def test_readable_cosenza_mart_is_explicitly_source_observation_only():
    ddl = (ROOT / "db/schema/070_views.sql").read_text(encoding="utf-8")
    assert "mart.cosenza_source_mentions" in ddl
    assert "not canonical entities" in ddl
    assert "identifier_scheme_parsed" in ddl
