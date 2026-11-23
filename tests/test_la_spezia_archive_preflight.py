"""Source-only tests for the two exact archived La Spezia HTML pages."""
from hashlib import sha256
import json

import pytest

from white_list_archive.acquisition import la_spezia_archive_preflight as qa


def sample(title: str, *, malformed=False) -> bytes:
    end = "" if malformed else "</table>"
    return ("""<!DOCTYPE html><html><body><h1>""" + title + """</h1>
    <h2>Sezione 1 Estrazione e trasporto</h2>
    <table><thead><tr>
    <th>Ragione Sociale</th><th>Partita Iva</th><th>Data iscrizione</th>
    </tr></thead><tbody><tr>
    <td>RISERVATO ROSSI MARIO</td><td>12345678901</td><td>11/11/2026</td>
    </tr><tr><td>RISERVATO ALTRO</td><td>01234567890</td><td>12/11/2026</td></tr>
    </tbody>""" + end + """</body></html>""").encode()


def test_structural_count_and_redaction_with_repeated_sector_rows():
    source = sample("Elenco ditte iscritte")
    report = qa.profile_html(source, "listed")
    serial = json.dumps(report)
    assert report["html_tables"] == 1
    assert report["physical_table_rows"] == 3
    assert report["header_shaped_rows"] == 1
    assert report["possible_data_shaped_rows_not_records"] == 2
    assert report["section_heading_cues"] == 1
    assert report["population_h1_cue"] is True
    assert report["date_authenticated"] is False
    assert report["logical_record_census"] is False
    assert "RISERVATO" not in serial
    assert "12345678901" not in serial
    assert "11/11/2026" not in serial


def test_applicant_h1_and_header_variant():
    content = b"""<html><h1>Elenco ditte che hanno richiesto iscrizione</h1>
      <table><tr><th>Ragione Sociale</th><th>Codice Fiscale / Partita IVA</th>
      <th>Attivita</th><th>Esito</th></tr>
      <tr><td>PRIVATE TEST</td><td>12345678901</td><td>Sez 1</td><td></td></tr></table></html>"""
    p = qa.profile_html(content, "applicant")
    assert p["population_h1_cue"] is True
    assert p["header_cues_in_header_shaped_rows"]["outcome"] == 1
    assert p["possible_data_shaped_rows_not_records"] == 1
    assert p["status_or_sector_validated"] is False


def test_invalid_html_structure_is_fail_closed():
    with pytest.raises(ValueError, match="Unclosed"):
        qa.profile_html(sample("Elenco ditte iscritte", malformed=True), "listed")
    with pytest.raises(ValueError, match="not begin as HTML"):
        qa.profile_html(b"PRIVATE ROW VALUES", "listed")
    with pytest.raises(ValueError, match="bounded"):
        qa.profile_html(b"<html>" + b"x" * qa.MAX_HTML_BYTES, "listed")
    with pytest.raises(ValueError, match="No physical"):
        qa.profile_html(b"<html><h1>Elenco ditte iscritte</h1></html>", "listed")


def test_nested_tables_and_oversized_cells_require_review():
    with pytest.raises(ValueError, match="Nested HTML tables"):
        qa.profile_html(b"<html><table><tr><td><table></table></td></tr></table></html>", "listed")
    with pytest.raises(ValueError, match="Oversized HTML table cell"):
        qa.profile_html(("<html><table><tr><td>" + "a" * (qa.MAX_CELL_CHARS + 1) +
                         "</td></tr></table></html>").encode(), "listed")


def test_archive_pair_readback_and_replay_are_only_source_evidence():
    originals = (sample("Elenco ditte iscritte"),
                 sample("Elenco ditte che hanno richiesto iscrizione"))
    pins = tuple((pop, sha256(data).hexdigest(), len(data))
                 for (pop, _, _), data in zip(qa.PINS, originals))
    class Store:
        def read_digest_verified(self, digest):
            return originals[0] if digest == pins[0][1] else originals[1]
    result = qa.audit_pair(Store(), pins=pins)
    assert result["originals_sha_verified"] == 2
    assert result["physical_profiles_completed"] == 2
    assert result["public_release_eligible"] is False
    assert result["source_edition_approved"] is False
    assert result["official_edition_date_approved"] is False
    assert result["privacy_approved"] is False
    assert result["postgresql_writes"] == result["public_promotions"] == 0
    assert qa.audit_pair(Store(), pins=pins) == result


def test_wrong_byte_size_and_provider_exception_never_expose_private_data():
    source = sample("Elenco ditte iscritte")
    digest = sha256(source).hexdigest()
    pins = (("listed", digest, len(source) + 1),
            ("applicant", digest, len(source)))
    class Store:
        def read_digest_verified(self, digest):
            return source
    result = qa.audit_pair(Store(), pins=pins)
    assert result["originals_sha_verified"] == 1
    assert result["physical_profiles_completed"] == 1
    assert result["results"][0]["review_code"] == "byte_identity_mismatch"
    class BrokenStore:
        def read_digest_verified(self, digest):
            raise RuntimeError("SECRET PRIVATE ACCESS LOCATION")
    failed = qa.audit_pair(BrokenStore(), pins=pins)
    assert failed["originals_sha_verified"] == 0
    assert "SECRET" not in json.dumps(failed)
    assert "PRIVATE ACCESS" not in json.dumps(failed)


def test_protected_workflow_only_and_no_untrusted_public_promotion():
    from pathlib import Path
    wf = (Path(__file__).resolve().parents[1] /
          ".github/workflows/transform-reviewed-captures.yml").read_text()
    block = wf.split(
        "- name: Audit archived La Spezia listed/applicant HTML (source only)", 1)[1].split("- name:", 1)[0]
    assert "matrix.shard == 0 && !cancelled()" in block
    assert "continue-on-error: true" in block
    assert "python -m white_list_archive.acquisition.la_spezia_archive_preflight" in block


def test_each_physical_table_is_reconciled_without_approving_headerless_rows():
    original = sample("Elenco ditte iscritte").decode()
    two_tables = original.replace("</body></html>", """
      <table><tr><td>PRIVATE HEADERLESS SOURCE ROW</td><td>12345678901</td></tr>
      </table></body></html>""").encode()
    report = qa.profile_html(two_tables, "listed")
    tables = report["table_profiles"]
    assert [p["table_ordinal"] for p in tables] == [1, 2]
    assert report["html_tables"] == 2
    assert report["physical_table_rows"] == 4
    assert [p["physical_rows"] for p in tables] == [3, 1]
    assert [p["header_shaped_rows"] for p in tables] == [1, 0]
    assert [p["th_tag_rows"] for p in tables] == [1, 0]
    assert [p["possible_data_shaped_rows_not_records"] for p in tables] == [2, 1]
    assert tables[1]["row_widths"] == {"2": 1}
    assert tables[1]["header_cues"] == {}
    assert report["logical_record_census"] is False
    assert report["privacy_approved"] is False
    assert "PRIVATE" not in json.dumps(report)
    assert "12345678901" not in json.dumps(report)
    assert "RISERVATO" not in json.dumps(report)
    assert sum(p["physical_rows"] for p in tables) == report["physical_table_rows"]
    assert sum(p["header_shaped_rows"] for p in tables) == report["header_shaped_rows"]


def test_too_many_tables_fail_closed_without_exposing_contents():
    raw = ("<html>" + "<table><tr><td>PRIVATE</td></tr></table>"
           * (qa.MAX_TABLES + 1) + "</html>").encode()
    with pytest.raises(ValueError, match="Excessive number of HTML tables"):
        qa.profile_html(raw, "listed")

def test_emphasised_section_label_is_counted_by_table_boundary_without_sector_inference():
    original = sample("Elenco ditte iscritte").decode()
    second = original.replace("</body></html>", """
       <p><strong>SEZIONE N. 3 - PRIVATE SECTOR LABEL</strong></p>
       <table><tr><td>PRIVATE PERSON</td><td>12345678901</td></tr></table>
       <p><b>Sezione IV - PRIVATE TRAILING LABEL</b></p>
       </body></html>""").encode()
    report = qa.profile_html(second, "listed")
    assert report["structural_section_label_cues"] == 3
    assert report["section_heading_cues"] == 1
    assert [p["preceding_section_label_cues"] for p in report["table_profiles"]] == [1, 1]
    assert report["trailing_section_label_cues"] == 1
    assert report["sector_to_table_mapping_approved"] is False
    assert report["logical_record_census"] is False
    serial = json.dumps(report)
    assert "PRIVATE" not in serial and "12345678901" not in serial


def test_non_section_emphasis_is_not_treated_as_sector_header():
    original = sample("Elenco ditte iscritte").decode()
    revised = original.replace("</body></html>", """
      <p><strong>PRIVATE PERSONAL NAME</strong></p>
      <table><tr><td>PRIVATE ROW</td></tr></table></body></html>""").encode()
    report = qa.profile_html(revised, "listed")
    assert report["structural_section_label_cues"] == 1
    assert report["table_profiles"][1]["preceding_section_label_cues"] == 0
    assert report["sector_to_table_mapping_approved"] is False
