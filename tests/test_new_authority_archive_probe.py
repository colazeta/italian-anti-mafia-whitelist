"""Synthetic QA of the read-only Novara/Rieti/Vicenza candidate workbook probe."""
from datetime import date
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

from openpyxl import Workbook

from white_list_archive.acquisition.new_authority_archive_probe import (
    PINS, audit, cell_shape, workbook_structure,
)


def sample_workbook():
    book = Workbook()
    ws = book.active
    ws.title = "PERSONAL NAME NEVER LOGGED"
    ws.append(["azienda", "codice", "data"])
    ws.append(["PRIVATE NAME", "RSSMRA85M01H501Z", date(2026, 11, 16)])
    ws.append(["PRIVATE NAME 2", "12345678901", "=A2"])
    out = BytesIO()
    book.save(out)
    book.close()
    return out.getvalue()


def test_exact_workbook_structure_is_redacted_and_not_edition_approval():
    original = sample_workbook()
    result = workbook_structure(original)
    assert result["sheet_count"] == 1
    assert result["worksheets"][0]["physical_rows"] == 3
    assert result["worksheets"][0]["row_shapes"]["multi_cell"] == 3
    shapes = result["worksheets"][0]["cell_shapes"]
    assert shapes["sixteen_character_shape_privacy_review"] == 1
    assert shapes["eleven_digit_shape"] == 1
    assert shapes["date_typed_cell"] == 1
    assert shapes["formula"] == 1
    encoded = json.dumps(result)
    for secret in ("PRIVATE NAME", "RSSMRA85M01H501Z", "12345678901",
                   "PERSONAL NAME NEVER LOGGED"):
        assert secret not in encoded


def test_bounded_non_xlsx_and_incomplete_sheets_fail_closed():
    for raw in (b"not-xlsx", b"", b"PK" + b"x" * 2500001):
        try:
            workbook_structure(raw)
        except (ValueError, Exception):
            pass
        else:
            raise AssertionError("Unreviewed input accepted")


def test_all_six_fixed_original_pins_are_distinct_and_complete():
    assert set(PINS) == {"novara", "rieti", "vicenza"}
    assert all({x[0] for x in pair} == {"listed", "applicant"} for pair in PINS.values())
    digests = [x[1] for pair in PINS.values() for x in pair]
    assert len(digests) == len(set(digests)) == 6
    assert all(len(x) == 64 for x in digests)
    assert all(n > 0 for pair in PINS.values() for _, _, n in pair)


def test_structural_probe_fails_closed_on_missing_or_wrong_remote_bytes():
    raw = sample_workbook()
    digest = sha256(raw).hexdigest()

    class Store:
        def read_digest_verified(self, value):
            if value == digest:
                return raw
            raise ValueError("Missing exact R2 object")

    outcome = audit(Store(), {"novara": (
        ("listed", digest, len(raw)),
        ("applicant", "0" * 64, 123),
    )})
    assert outcome["originals_verified"] == 1
    assert outcome["originals_expected"] == 2
    assert outcome["results"][1]["error_type"] == "ValueError"
    assert not outcome["source_edition_approved"]
    assert not outcome["privacy_approved"]
    assert not outcome["public_release_eligible"]
    assert "PRIVATE NAME" not in json.dumps(outcome)


def test_shape_classification_never_returns_raw_cells():
    for value in ("RSSMRA85M01H501Z", "12345678901", "PRIVATE COMPANY"):
        result = cell_shape(value)
        assert value not in result
        assert set(result) <= set("abcdefghijklmnopqrstuvwxyz_")
    assert cell_shape("") == "blank"


def test_probe_is_existing_protected_worker_not_an_external_writer():
    workflow = (Path(__file__).resolve().parents[1]
                / ".github/workflows/transform-reviewed-captures.yml").read_text()
    fragment = workflow.split(
        "- name: Read back three unpublished authority XLSX pairs (source-only)", 1)[1]
    fragment = fragment.split("- name:", 1)[0]
    assert "matrix.shard == 0 && !cancelled()" in fragment
    assert "continue-on-error: true" in fragment
    assert "white_list_archive.acquisition.new_authority_archive_probe" in fragment
