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


def test_out_of_policy_payload_markers_distinguish_metadata_from_possible_values():
    """Far XLSX cells are NOT automatically harmless formatting."""
    from zipfile import ZipFile
    from white_list_archive.acquisition.new_authority_archive_probe import (
        workbook_coordinate_diagnostic,
    )

    source = sample_workbook()
    out = BytesIO()
    xml = (
        b'<worksheet xmlns="http://schemas.openxmlformats.org/'
        b'spreadsheetml/2006/main"><dimension ref="A1:J1048576"/>'
        b'<sheetData><row r="1"><c r="A1"><v>PRIVATE DATA</v></c></row>'
        b'<row r="1048576"><c r="A1048576" s="1"/>'
        b'<c r="B1048576"><v>0</v></c>'
        b'<c r="C1048576"><f>PRIVATE FORMULA</f></c>'
        b'<c r="D1048576" t="inlineStr"><is><t>PRIVATE PERSON</t></is></c>'
        b'</row></sheetData></worksheet>'
    )
    with ZipFile(BytesIO(source)) as archive, ZipFile(out, "w") as target:
        for info in archive.infolist():
            target.writestr(info, xml if info.filename ==
                            "xl/worksheets/sheet1.xml" else archive.read(info.filename))
    report = workbook_coordinate_diagnostic(out.getvalue())
    part = report["xml_parts"][0]
    assert part["out_of_policy_explicit_row_elements"] == 1
    assert part["out_of_policy_cell_elements"] == 4
    assert part["out_of_policy_cell_with_payload_marker"] == 3
    assert part["out_of_policy_cell_without_payload_marker"] == 1
    assert part["out_of_policy_formula_cell_elements"] == 1
    assert part["greatest_payload_marker_row"] == 1048576
    assert part["greatest_payload_marker_column"] == 4
    assert not report["source_edition_approved"]
    assert not report["privacy_approved"]
    assert not report["record_census"]
    for secret in ("PRIVATE DATA", "PRIVATE FORMULA", "PRIVATE PERSON"):
        assert secret not in json.dumps(report)


def test_declared_1024_columns_not_confused_with_physical_encoded_cells():
    """Pure dimensions remain an unapproved clue, not a changed row contract."""
    from zipfile import ZipFile
    from openpyxl.utils.cell import get_column_letter
    from white_list_archive.acquisition.new_authority_archive_probe import (
        workbook_coordinate_diagnostic,
    )
    width = get_column_letter(1024).encode("ascii")
    xml = (b'<worksheet><dimension ref="A1:' + width + b'385"/>'
           b'<sheetData><row r="385"><c r="G385"><v>PRIVATE</v></c>'
           b'</row></sheetData></worksheet>')
    original = sample_workbook()
    out = BytesIO()
    with ZipFile(BytesIO(original)) as archive, ZipFile(out, "w") as target:
        for info in archive.infolist():
            target.writestr(info, xml if info.filename ==
                            "xl/worksheets/sheet1.xml" else archive.read(info.filename))
    report = workbook_coordinate_diagnostic(out.getvalue())
    part = report["xml_parts"][0]
    assert part["declared_columns"] == 1024
    assert part["greatest_encoded_column"] == 7
    assert part["out_of_policy_cell_elements"] == 0
    assert part["greatest_payload_marker_row"] == 385
    assert part["greatest_payload_marker_column"] == 7
    assert "PRIVATE" not in json.dumps(report)
    assert report["diagnostic_only"] and not report["source_edition_approved"]


def test_unlocated_possible_payload_never_silently_classified_in_range():
    from zipfile import ZipFile
    from white_list_archive.acquisition.new_authority_archive_probe import (
        workbook_coordinate_diagnostic,
    )
    xml = b'<worksheet><sheetData><row r="1"><c><v>SECRET</v></c></row></sheetData></worksheet>'
    original = sample_workbook()
    out = BytesIO()
    with ZipFile(BytesIO(original)) as archive, ZipFile(out, "w") as target:
        for info in archive.infolist():
            target.writestr(info, xml if info.filename ==
                            "xl/worksheets/sheet1.xml" else archive.read(info.filename))
    part = workbook_coordinate_diagnostic(out.getvalue())["xml_parts"][0]
    assert part["cells_without_coordinates"] == 1
    assert part["unlocated_cell_with_payload_marker"] == 1
    assert part["out_of_policy_cell_elements"] == 0
    assert "SECRET" not in json.dumps(part)


def test_source_only_row_signals_do_not_infer_firms_or_disclose_values():
    """Rieti-type workbook signal counts are aggregate only, never approval."""
    from white_list_archive.acquisition.new_authority_archive_probe import workbook_structure
    book = Workbook()
    ws = book.active
    ws.title = "PRIVATE RIETI WORKSHEET"
    ws.append(["header", "columns"])
    ws.append(["01234567890", "PRIVATE COMPANY"])
    ws.append(["RSSMRA85M01H501Z", "PRIVATE PERSON"])
    ws.append(["01234567890", "RSSMRA85M01H501Z"])
    ws.append(["=SUM(1,2)", "other"])
    ws.append(["summary"])
    buff = BytesIO()
    book.save(buff)
    book.close()
    report = workbook_structure(buff.getvalue())
    rows = report["worksheets"][0]
    assert rows["row_shapes"] == {"multi_cell": 5, "single_cell": 1}
    assert rows["row_signals"] == {
        "multi_cell_with_11_digit_text": 2,
        "multi_cell_with_16_char_text": 2,
        "multi_cell_with_both_text_shapes": 1,
        "multi_cell_with_neither_text_shape": 2,
        "multi_cell_with_formula": 1,
    }
    redacted = json.dumps(report)
    for secret in ("PRIVATE", "01234567890", "RSSMRA85M01H501Z"):
        assert secret not in redacted
    assert "source_edition_approved" not in redacted


def test_rieti_formula_cache_audit_only_counts_presence_not_results():
    """Cached values need independent review: formula strings are not outcomes."""
    import re
    from zipfile import ZipFile
    book = Workbook()
    ws = book.active
    ws.title = "PRIVATE RIETI FORMULAE"
    ws.append(["heading", "heading"])
    ws.append(["=1+1", "PRIVATE BUSINESS"])
    ws.append(["=1+2", "PRIVATE PERSON"])
    out = BytesIO()
    book.save(out)
    book.close()
    patched = BytesIO()
    with ZipFile(BytesIO(out.getvalue())) as source, ZipFile(patched, "w") as target:
        for item in source.infolist():
            payload = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                payload, changed = re.subn(
                    rb"(<f>1\+1</f><v>)[^<]*(</v>)",
                    rb"\g<1>12345678901\g<2>", payload)
                assert changed == 1
            target.writestr(item, payload)
    result = workbook_structure(patched.getvalue())
    counts = result["worksheets"][0]["formula_cache_counts"]
    assert counts["formula_cells"] == 2
    assert counts["formula_cells_with_cache"] == 1
    assert counts["formula_cells_without_cache"] == 1
    assert counts["rows_with_cached_formula"] == 1
    assert counts["rows_with_uncached_formula"] == 1
    assert counts["formula_cells_with_cache"] + counts["formula_cells_without_cache"] == counts["formula_cells"]
    # The old physical row-census signals are unchanged by the cache view.
    assert result["worksheets"][0]["row_shapes"] == {"multi_cell": 3}
    redacted = json.dumps(result)
    for value in ("PRIVATE BUSINESS", "PRIVATE PERSON", "PRIVATE RIETI FORMULAE",
                  "12345678901", "=1+1", "=1+2"):
        assert value not in redacted


def test_no_cached_formula_is_explicit_and_no_public_approval_is_inferred():
    source = sample_workbook()
    report = workbook_structure(source)
    formula = report["worksheets"][0]["formula_cache_counts"]
    assert formula["formula_cells"] == 1
    assert formula["formula_cells_with_cache"] == 0
    assert formula["formula_cells_without_cache"] == 1
    assert "source_edition_approved" not in json.dumps(report)


def test_latest_rieti_vicenza_candidate_pins_remain_population_specific():
    assert PINS["rieti"] == (
        ("listed", "9ca5fcf9be4e7447c197f3dd94ba5b7f4a8b7656853aca0a7f2837159a4892f7", 50306),
        ("applicant", "8eed8bfc3b094c3750a5410063e9142365945e1a56a939177849e07f51c55b03", 46364),
    )
    assert PINS["vicenza"] == (
        ("listed", "f1af1fe0a99c8fafcf05537721b39a80c2072a4ea524f2c61b4b9f5466c43f50", 68748),
        ("applicant", "624d3b2214b3afae309d1f12787dc4957093d96e7bf0ccf3ff5c952ceb7385f4", 14695),
    )


def test_finite_header_row_roles_reconcile_without_assuming_records():
    from white_list_archive.acquisition.new_authority_archive_probe import workbook_structure
    book = Workbook()
    ws = book.active
    ws.append(["PRIVATE TITLE"])
    ws.append(["Ragione sociale", "Codice fiscale", "Sede legale", "Data iscrizione"])
    ws.append(["PRIVATE BUSINESS", 12345678901, "PRIVATE ADDRESS", date(2026, 11, 1)])
    ws.append(["PRIVATE PERSON", "RSSMRA85M01H501Z", "PRIVATE ADDRESS"])
    ws.append(["PRIVATE NOTE", "other"])
    ws.append(["PRIVATE FOOTER"])
    buff = BytesIO()
    book.save(buff)
    book.close()
    sheet = workbook_structure(buff.getvalue())["worksheets"][0]
    assert sheet["row_role_clues_not_record_census"] == {
        "before_recognised_header": 1, "header_clue": 1,
        "post_header_multicell_with_identifier_clue": 2,
        "post_header_multicell_without_identifier_clue": 1,
        "post_header_single_cell": 1,
    }
    assert sum(sheet["row_role_clues_not_record_census"].values()) == sheet["physical_rows"]
    assert sheet["recognised_header_role_counts"]["listing_date"] == 1
    for value in ("PRIVATE", "12345678901", "RSSMRA85M01H501Z"):
        assert value not in json.dumps(sheet)


def test_partial_header_and_unresolved_row_clues_are_finite_and_redacted():
    book = Workbook()
    ws = book.active
    ws.append(["Ragione sociale", "PRIVATE HEADING"])
    ws.append(["PRIVATE BUSINESS", 12345678901])
    ws.append(["PRIVATE NOTE", "other"])
    ws.append(["Denominazione / ragione sociale", "Codice fiscale/partita iva", "Sede legale"])
    ws.append(["PRIVATE RESIDUAL", "other"])
    out = BytesIO()
    book.save(out)
    book.close()
    sheet = workbook_structure(out.getvalue())["worksheets"][0]
    assert sheet["partial_header_role_combinations"] == {"name": 1}
    assert sheet["unresolved_multicell_shape_counts"] == {
        "before_header_without_identifier_clue": 2,
        "before_header_with_identifier_clue": 1,
        "after_header_without_identifier_clue": 1,
    }
    assert sheet["row_role_clues_not_record_census"]["header_clue"] == 1
    assert "PRIVATE" not in json.dumps(sheet)
    assert "12345678901" not in json.dumps(sheet)


def test_strong_partial_header_alignment_does_not_approve_or_disclose():
    book = Workbook()
    ws = book.active
    ws.append(["PRIVATE TITLE"])
    ws.append(["PRIVATE NAME LABEL", "Codice fiscale", "Sede legale",
               "Data iscrizione", "Data scadenza", "Note"])
    ws.append(["PRIVATE BUSINESS", "01234567890", "PRIVATE ADDRESS",
               date(2026, 11, 1), date(2027, 11, 1), "PRIVATE NOTE"])
    ws.append(["PRIVATE RESIDUAL", None, None, None, None, None])
    out = BytesIO()
    book.save(out)
    book.close()
    sheet = workbook_structure(out.getvalue())["worksheets"][0]
    assert sheet["aligned_rows_not_record_census"] == {
        "before_anchor": 1, "header_anchor": 1, "after_anchor": 2,
    }
    assert sheet["aligned_field_shapes_not_values"]["identifier:eleven_digit_shape"] == 1
    assert sheet["aligned_field_shapes_not_values"]["identifier:blank"] == 1
    assert sheet["aligned_field_shapes_not_values"]["listing_date:date_typed_cell"] == 1
    assert not sheet["recognised_header_role_counts"]
    assert "PRIVATE" not in json.dumps(sheet)
    assert "01234567890" not in json.dumps(sheet)


def test_repeated_header_roles_remain_unbound_but_unique_roles_are_diagnosed():
    book = Workbook()
    ws = book.active
    ws.append(["Ragione sociale", "Codice fiscale", "Partita IVA", "Sede legale"])
    ws.append(["PRIVATE BUSINESS", "01234567890", "09876543210", "PRIVATE ADDRESS"])
    out = BytesIO()
    book.save(out)
    book.close()
    sheet = workbook_structure(out.getvalue())["worksheets"][0]
    assert sheet["aligned_rows_not_record_census"] == {"header_anchor": 1, "after_anchor": 1}
    assert sheet["ambiguous_header_rows"] == 1
    assert sheet["ambiguous_header_role_column_occurrences"] == {"identifier": 2}
    assert sheet["aligned_field_shapes_not_values"] == {"name:other_nonblank": 1, "address:other_nonblank": 1}
    assert "PRIVATE" not in json.dumps(sheet)
    assert "01234567890" not in json.dumps(sheet)
    assert "09876543210" not in json.dumps(sheet)


def test_novara_pdf_pair_is_bounded_and_redacted():
    from white_list_archive.acquisition.new_authority_archive_probe import (
        NOVARA_PDF_PINS, audit_novara_pdfs, novara_pdf_pages,
    )
    assert len(NOVARA_PDF_PINS) == 2
    assert {x[0] for x in NOVARA_PDF_PINS} == {"listed", "applicant"}

    class Table:
        def extract(self):
            return [["Ragione sociale", "Codice fiscale"], ["PRIVATE-NAME", "12345678901"],
                    ["PRIVATE-OTHER", "unknown"], ["PRIVATE-NOTE"], ["", ""]]

    class Page:
        width, height = 600, 800
        def crop(self, _):
            return self
        def extract_text(self):
            return "Prefettura di Novara\nElenco imprese iscritte\nAggiornato al 25/11/2026\nPRIVATE-NAME"
        def find_tables(self):
            return [Table()]

    profile = novara_pdf_pages([Page()], "listed")
    assert profile["counts"]["physical_rows"] == 5
    assert profile["counts"]["multicell_identifier_shape_rows"] == 1
    assert profile["counts"]["unresolved_multicell_rows"] == 1
    assert profile["labelled_header_date_clues"] == {"2026-11-25": 1}
    assert not profile["official_edition_date_approved"]
    raw = b"synthetic"
    digest = sha256(raw).hexdigest()
    class Store:
        def read_digest_verified(self, _):
            return raw
    report = audit_novara_pdfs(Store(), pins=(("listed", digest, len(raw)),
                                             ("applicant", digest, len(raw)+1)),
                               scanner=lambda *_: profile)
    assert report["originals_sha_verified"] == 1
    assert report["physical_profiles_completed"] == 1
    assert not report["public_release_eligible"]
    assert "PRIVATE" not in json.dumps(report)
    assert "12345678901" not in json.dumps(report)


def test_novara_table_local_alignment_never_inherits_or_discloses():
    from white_list_archive.acquisition.new_authority_archive_probe import novara_pdf_pages

    class Table:
        def __init__(self, rows):
            self.rows = rows
        def extract(self):
            return self.rows

    class Page:
        width, height = 600, 800
        def crop(self, _):
            return self
        def extract_text(self):
            return "Prefettura di Novara"
        def find_tables(self):
            return [
                Table([["Ragione sociale", "Codice fiscale", "Sede legale"],
                       ["PRIVATE NAME", "12345678901", "PRIVATE ADDRESS"],
                       ["PRIVATE CONTINUATION", "", ""],
                       ["", "09876543210", "PRIVATE ADDRESS"]]),
                Table([["PRIVATE UNANCHORED", "12345678901", "PRIVATE ADDRESS"]]),
            ]

    result = novara_pdf_pages([Page()], "listed")
    assert result["counts"]["physical_rows"] == 5
    assert result["table_local_header_alignment_counts"]["name_identifier_bound_headers"] == 1
    assert result["aligned_row_review_counts_not_logical_census"] == {
        "aligned_nonheader_rows": 3,
        "name_and_identifier_shape": 1,
        "name_without_standard_identifier_shape": 1,
        "missing_name_in_aligned_row": 1,
        "no_complete_table_local_anchor": 1,
    }
    assert not result["logical_record_census_approved"]
    assert "PRIVATE" not in json.dumps(result)
    assert "12345678901" not in json.dumps(result)
