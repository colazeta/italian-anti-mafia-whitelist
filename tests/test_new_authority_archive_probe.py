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


def test_undimensioned_sheet_is_physically_scanned_not_silently_trusted():
    """Real XLSX producers may omit the dimension hint; enforce actual caps."""
    import re
    from zipfile import ZipFile
    original = sample_workbook()
    out = BytesIO()
    with ZipFile(BytesIO(original)) as source, ZipFile(out, "w") as target:
        for item in source.infolist():
            payload = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                payload, count = re.subn(rb'<dimension\s+ref="[^"]+"\s*/>', b'', payload)
                assert count == 1
            target.writestr(item, payload)
    shape = workbook_structure(out.getvalue())
    assert shape["worksheets"][0]["physical_rows"] == 3
    assert shape["worksheets"][0]["physical_columns"] == 3
    assert shape["worksheets"][0]["declared_dimensions_present"] is False


def test_excessive_dimensions_and_sensitive_library_errors_fail_closed(monkeypatch):
    from white_list_archive.acquisition import new_authority_archive_probe as mod
    book = Workbook()
    ws = book.active
    ws.cell(1, 121).value = "too wide"
    out = BytesIO()
    book.save(out)
    book.close()
    try:
        workbook_structure(out.getvalue())
    except ValueError as exc:
        assert str(exc) == "Declared worksheet dimensions exceed safe limits"
    else:
        raise AssertionError("Overwide worksheet accepted")

    raw = sample_workbook()
    digest = sha256(raw).hexdigest()

    class Store:
        def read_digest_verified(self, _):
            return raw

    def sensitive_failure(_):
        raise ValueError("SECRET COMPANY AND PRIVATE IDENTIFIER")
    monkeypatch.setattr(mod, "workbook_structure", sensitive_failure)
    data = mod.audit(Store(), {"rieti": (
        ("listed", digest, len(raw)), ("applicant", digest, len(raw)),
    )})
    assert data["originals_verified"] == 0
    assert all(x["review_code"] == "unclassified_library_or_archive_failure"
               for x in data["results"])
    assert "SECRET COMPANY" not in json.dumps(data)



def test_oversized_declared_dimension_gets_metadata_only_coordinate_evidence():
    """A format-only far cell is diagnosed without approving its semantics."""
    from white_list_archive.acquisition.new_authority_archive_probe import (
        workbook_coordinate_diagnostic,
    )
    book = Workbook()
    ws = book.active
    ws.title = "PRIVATE PERSON DO NOT OUTPUT"
    ws.cell(1, 1).value = "PRIVATE BUSINESS NAME"
    ws.cell(1, 121).value = "RSSMRA85M01H501Z"
    raw_io = BytesIO()
    book.save(raw_io)
    book.close()
    raw = raw_io.getvalue()
    result = workbook_coordinate_diagnostic(raw)
    assert result["diagnostic_only"] is True
    assert result["record_census"] is False
    assert result["source_edition_approved"] is False
    assert result["privacy_approved"] is False
    part = result["xml_parts"][0]
    assert part["declared_columns"] == 121
    assert part["greatest_encoded_column"] == 121
    assert part["encoded_cell_elements"] == 2
    assert part["greatest_encoded_row"] == 1
    for private in ("PRIVATE PERSON", "PRIVATE BUSINESS NAME", "RSSMRA85M01H501Z"):
        assert private not in json.dumps(result)

    digest = sha256(raw).hexdigest()

    class Store:
        def read_digest_verified(self, _digest):
            assert _digest == digest
            return raw

    response = audit(Store(), {"novara": (
        ("listed", digest, len(raw)), ("applicant", digest, len(raw)),
    )})
    assert response["source_bytes_verified"] == 2
    assert response["originals_verified"] == 0
    for item in response["results"]:
        assert item["review_code"] == "declared_dimensions_out_of_bounds"
        assert item["redacted_coordinate_diagnostic"]["diagnostic_only"]
    assert not response["public_release_eligible"]
    assert "PRIVATE BUSINESS NAME" not in json.dumps(response)


def test_coordinate_diagnostic_rejects_malicious_xml_and_zip_expansion():
    from white_list_archive.acquisition.new_authority_archive_probe import (
        workbook_coordinate_diagnostic,
    )
    from zipfile import ZipFile
    original = sample_workbook()

    def replace_sheet(new_xml):
        dst = BytesIO()
        with ZipFile(BytesIO(original)) as source, ZipFile(dst, "w") as output:
            for info in source.infolist():
                payload = new_xml if info.filename == "xl/worksheets/sheet1.xml" \
                    else source.read(info.filename)
                output.writestr(info, payload)
        return dst.getvalue()

    for xml in (
        b'<!DOCTYPE worksheet [<!ENTITY secret SYSTEM "file:///etc/passwd">]>'
        b'<worksheet><row><c r="A1"/></row></worksheet>',
        b'<worksheet><row><c r="ZZZZ99999999"/></row></worksheet>',
    ):
        try:
            workbook_coordinate_diagnostic(replace_sheet(xml))
        except ValueError:
            pass
        else:
            raise AssertionError("Unreviewed XML accepted")

    # Before parsing, reject an inflated worksheet whose declared size
    # exceeds the finite read-only diagnostic maximum.
    huge_xml = b'<worksheet>' + b' ' * 24000001 + b'</worksheet>'
    try:
        workbook_coordinate_diagnostic(replace_sheet(huge_xml))
    except ValueError as exc:
        assert str(exc) == "Worksheet XML exceeds diagnostic limits"
    else:
        raise AssertionError("Oversized worksheet XML accepted")



def test_coordinate_diagnostic_includes_explicit_rows_without_cell_refs():
    """Redacted extent must not silently omit row-only coordinates."""
    from zipfile import ZipFile
    from white_list_archive.acquisition.new_authority_archive_probe import (
        workbook_coordinate_diagnostic,
    )
    original = sample_workbook()

    def with_sheet(xml):
        out = BytesIO()
        with ZipFile(BytesIO(original)) as src, ZipFile(out, "w") as dst:
            for info in src.infolist():
                dst.writestr(info, xml if info.filename ==
                             "xl/worksheets/sheet1.xml" else src.read(info.filename))
        return out.getvalue()

    template = (b'<worksheet xmlns="http://schemas.openxmlformats.org/'
                b'spreadsheetml/2006/main"><sheetData><row r="%s">'
                b'<c t="inlineStr"><is><t>PRIVATE VALUE</t></is></c>'
                b'</row></sheetData></worksheet>')
    parsed = workbook_coordinate_diagnostic(with_sheet(template % b"70000"))
    assert parsed["xml_parts"][0]["greatest_encoded_row"] == 70000
    assert parsed["xml_parts"][0]["cells_without_coordinates"] == 1
    assert "PRIVATE VALUE" not in json.dumps(parsed)
    try:
        workbook_coordinate_diagnostic(with_sheet(template % b"INVALID"))
    except ValueError as exc:
        assert str(exc) == "Invalid worksheet coordinate metadata"
    else:
        raise AssertionError("Malformed row coordinate was accepted")
