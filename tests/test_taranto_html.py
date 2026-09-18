from __future__ import annotations

from pathlib import Path

import pytest

from white_list_archive.parsers.taranto_html import parse_taranto_applicants, parse_taranto_listed


def _cfg(kind: str) -> dict[str, str]:
    return {
        "source_key": f"taranto-{kind}",
        "authority_key": "taranto",
        "authority_name": "Prefettura di Taranto",
        "register_key": "taranto-ordinary",
        "register_name": "White List ordinaria",
        "population_scope": "applicant" if kind == "applicants" else "listed",
        "reference_date": "2026-09-07",
        "source_page_url": "https://prefettura.interno.gov.it/it/prefetture/taranto/example",
        "resource_url": "https://prefettura.interno.gov.it/it/prefetture/taranto/example",
        "sha256": "a" * 64,
    }


def test_taranto_listed_nested_table_preserves_malformed_source_values(tmp_path: Path) -> None:
    html = """
    <html><body><table><tr><td>layout<table>
      <tr><th>Ragione Sociale</th><th>Sede Legale</th><th>Codice Fiscale - Partita IVA</th><th>Data iscrizione</th><th>Data scadenza iscrizione</th><th>Sezioni</th><th>Note</th></tr>
      <tr><td>ALFA SRL</td><td>TARANTO</td><td>01234567890</td><td>01/09/2026</td><td>01/09/2027</td><td>I - III - X</td><td></td></tr>
      <tr><td>BETA SRL</td><td>MASSAFRA</td><td>0342700735</td><td>0912/2025</td><td>09/12/2026</td><td>II- III - V</td><td>In fase di rinnovo</td></tr>
      <tr><td>GAMMA SRL</td><td>MANDURIA</td><td>RSSMRA80A01L049X</td><td>02/09/2026</td><td>02/09/2027</td><td>IX</td><td>In fase di aggiornamento</td></tr>
    </table></td></tr></table></body></html>
    """
    path = tmp_path / "listed.html"
    path.write_text(html, encoding="utf-8")
    batch = parse_taranto_listed(path, _cfg("listed"))
    assert len(batch.records) == 3
    assert [record["source_status"] for record in batch.records] == [
        "listed",
        "renewal_update_in_progress",
        "renewal_update_in_progress",
    ]
    assert batch.records[0]["requested_activities"] == ["Sezione I", "Sezione III", "Sezione X"]
    assert batch.records[1]["observed_listing_date"] == ""
    assert batch.records[1]["source_fields"]["listing_date_raw_variants"] == ["0912/2025"]
    assert batch.records[1]["identifier_field_raw"] == "0342700735"
    assert batch.records[1]["identifiers"] == []
    assert batch.diagnostics["malformed_date_rows"] == 1
    assert batch.diagnostics["raw_identifier_only"] == 1


def test_taranto_applicants_are_pending_and_dates_are_not_invented(tmp_path: Path) -> None:
    html = """
    <table><tr><td>layout<table>
      <tr><th>Ragione Sociale</th><th>Sede legale</th><th>Codice fiscale/partita IVA</th><th>Sezioni</th><th>Data di presentazione dell'istanza</th></tr>
      <tr><td>DELTA SRL</td><td>TARANTO</td><td>03111950733</td><td>III - V - VI - X</td><td>09/05/2017</td></tr>
      <tr><td>EPSILON SRL</td><td>GROTTAGLIE</td><td>0340290730</td><td>IV</td><td>13/01/2026</td></tr>
    </table></td></tr></table>
    """
    path = tmp_path / "applicants.html"
    path.write_text(html, encoding="utf-8")
    batch = parse_taranto_applicants(path, _cfg("applicants"))
    assert len(batch.records) == 2
    assert all(record["source_status"] == "pending" for record in batch.records)
    assert batch.records[0]["application_date"] == "2017-05-09"
    assert batch.records[1]["identifier_field_raw"] == "0340290730"
    assert batch.records[1]["identifiers"] == []
    assert batch.diagnostics["raw_identifier_only"] == 1
    assert batch.diagnostics["malformed_date_rows"] == 0


def test_taranto_unknown_listed_note_fails_closed(tmp_path: Path) -> None:
    html = """
    <table>
      <tr><th>Ragione Sociale</th><th>Sede Legale</th><th>Codice Fiscale - Partita IVA</th><th>Data iscrizione</th><th>Data scadenza iscrizione</th><th>Sezioni</th><th>Note</th></tr>
      <tr><td>ZETA SRL</td><td>TARANTO</td><td>01234567890</td><td>01/09/2026</td><td>01/09/2027</td><td>I</td><td>Nuovo stato non approvato</td></tr>
    </table>
    """
    path = tmp_path / "listed.html"
    path.write_text(html, encoding="utf-8")
    with pytest.raises(ValueError, match="Unapproved Taranto listed note/status"):
        parse_taranto_listed(path, _cfg("listed"))
