from pathlib import Path

import pytest

from white_list_archive.parsers.biella_html import parse_biella_applicants, parse_biella_listed


BASE = {
    "authority_key": "biella",
    "authority_name": "Prefettura di Biella",
    "reference_date": "2026-08-26",
    "source_page_url": "https://example.test/biella",
    "resource_url": "https://example.test/biella",
    "sha256": "0" * 64,
}


def _cfg(scope: str) -> dict[str, str]:
    return {
        **BASE,
        "source_key": f"biella-{scope}",
        "register_key": "biella-ordinary",
        "register_name": "White List ordinaria",
        "population_scope": scope,
    }


def _listed_section(number: str, activity: str, name: str, ident: str, listing: str, expiry: str, update: str = "") -> str:
    return f"""
      <tr><td>Sezione {number}</td></tr>
      <tr><td>{activity}</td></tr>
      <tr><th>Ragione Sociale</th><th>Sede Legale</th><th>Sede secondaria con rappresentanza stabile in Italia</th><th>Codice fiscale/Partita IVA</th><th>Data di iscrizione</th><th>Data scadenza iscrizione</th><th>Aggiornamento in corso</th></tr>
      <tr><td>{name}</td><td>Biella</td><td></td><td>{ident}</td><td>{listing}</td><td>{expiry}</td><td>{update}</td></tr>
    """


def _source_html() -> str:
    applicants = """
    <table>
      <tr><td>ELENCO DELLE IMPRESE RICHIEDENTI L'ISCRIZIONE</td><td></td></tr>
      <tr><td>Prefettura di Biella</td><td></td></tr>
      <tr><th>Ragione Sociale</th><th>Sede Legale</th><th>Sede secondaria con rappresentanza stabile in Italia</th><th>Codice fiscale/Partita IVA</th><th>Attività per cui è richiesta l'iscrizione</th><th>Data di presentazione dell'istanza</th><th>Esito</th><th></th></tr>
      <tr><td>Alpha SRL</td><td>Biella</td><td></td><td>01234567890</td><td>Noli a caldo</td><td>12/12/2017 (comunicazione interesse a permanere)</td><td>Iscritto</td><td></td></tr>
      <tr><td>Beta SRL</td><td>Biella</td><td></td><td>1234567890</td><td>Noli a freddo</td><td></td><td></td><td></td></tr>
      <tr><td>Gamma SRL</td><td>Biella</td><td></td><td>09876543210</td><td>Autotrasporto</td><td>20/09/2024</td><td>in aggiorn.to</td><td></td></tr>
    </table>
    """
    listed = '<table><tr><td>ELENCO DEI FORNITORI, PRESTATORI DI SERVIZI ED ESECUTORI DI LAVORI</td></tr>'
    rows = [
        ("I", "Attività I", "Same SRL", "'02611910031", "23-nov-20", "04-ago-27", ""),
        ("II", "Attività II", "Same SRL", "02611910031", "23/11/2020", "04-ago-27", ""),
        ("III", "Attività III", "Same SRL", "02611910031", "24-nov-20", "04-ago-27", ""),
        ("IV", "Attività IV", "D SRL", "11111111111", "20-giu-23", "28-mag-27", "Aggiornamento"),
        ("V", "Attività V", "E SRL", "22222222222", "23-01-25", "", ""),
        ("VI", "Attività VI", "F SRL", "33333333333", "16/09/24", "20-feb-27", ""),
        ("VII", "Attività VII", "G SRL", "44444444444", "07-sett-24", "20-feb-27", ""),
        ("VIII", "Attività VIII", "H SRL", "55555555555", "08-ago-19", "20-feb-27", ""),
        ("IX", "Attività IX", "I SRL", "66666666666", "09-ott-15", "20-feb-27", ""),
        ("X", "Attività X", "L SRL", "77777777777", "10-gen-25", "20-feb-27", "In aggiorn.to"),
    ]
    for row in rows:
        listed += _listed_section(*row)
    listed += "</table>"
    return "<html><body>" + applicants + listed + "</body></html>"


def test_biella_applicant_semantics(tmp_path: Path) -> None:
    path = tmp_path / "biella.html"
    path.write_text(_source_html(), encoding="utf-8")
    batch = parse_biella_applicants(path, _cfg("applicant"))
    assert batch.diagnostics["public_records"] == 3
    assert [record["source_status"] for record in batch.records] == [
        "listed", "pending", "renewal_update_in_progress"
    ]
    assert batch.records[0]["application_date"] == "2017-12-12"
    assert batch.records[0]["source_fields"]["application_date_raw"].endswith("permanere)")
    assert batch.records[1]["identifier_field_raw"] == "1234567890"
    assert batch.records[1]["identifiers"] == []
    assert batch.records[1]["application_date"] == ""


def test_biella_listed_groups_only_semantic_sector_repetition(tmp_path: Path) -> None:
    path = tmp_path / "biella.html"
    path.write_text(_source_html(), encoding="utf-8")
    batch = parse_biella_listed(path, _cfg("listed"))
    assert batch.diagnostics["sector_rows"] == 10
    assert batch.diagnostics["public_records"] == 9
    same = [record for record in batch.records if record["name"] == "Same SRL"]
    assert len(same) == 2
    grouped = next(record for record in same if record["observed_listing_date"] == "2020-11-23")
    assert grouped["requested_activities"] == ["Attività I", "Attività II"]
    assert grouped["source_fields"]["identifier_raw_variants"] == ["'02611910031", "02611910031"]
    assert grouped["identifiers"] == ["02611910031"]
    assert next(record for record in batch.records if record["name"] == "E SRL")["observed_expiry_date"] == ""
    assert next(record for record in batch.records if record["name"] == "F SRL")["observed_listing_date"] == "2024-09-16"
    assert next(record for record in batch.records if record["name"] == "D SRL")["source_status"] == "renewal_update_in_progress"


def test_biella_rejects_unrecognised_date(tmp_path: Path) -> None:
    html = _source_html().replace("20-giu-23", "20-xyz-23")
    path = tmp_path / "biella.html"
    path.write_text(html, encoding="utf-8")
    with pytest.raises(ValueError, match="month abbreviation"):
        parse_biella_listed(path, _cfg("listed"))
