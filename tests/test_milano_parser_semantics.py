from __future__ import annotations

from pathlib import Path

import pytest

import white_list_archive.parsers.milano_webapp as milano


SECTIONS = (
    "ESTRAZIONE, FORNITURA E TRASPORTO DI TERRA E MATERIALI INERTI",
    "CONFENZIONAMENTO, FORNITURA E TRASPORTO CALCESTRUZZO E DI BITUME",
    "NOLI A FREDDO DI MACCHINARI",
    "FORNITURA DI FERRO LAVORATO",
    "NOLI A CALDO",
    "AUTOTRASPORTI PER CONTO TERZI",
    "GUARDIANIA AI CANTIERI",
    "SERVIZI FUNERARI E CIMITERIALI",
    "RISTORAZIONE, GESTIONE DELLE MENSE E CATERING",
    "SERVIZI AMBIENTALI, COMPRESE LE ATTIVITA’ DI RACCOLTA, DI TRASPORTO NAZIONALE E TRANSFRONTALIERO, ANCHE PER CONTO DI TERZI, DI TRATTAMENTO E DI SMALTIMENTO DEI RIFIUTI, NONCHE’ LE ATTIVITA’ DI RISANAMENTO E DI BONIFICA E GLI ALTRI SERVIZI CONNESSI ALLA GESTIONE DEI RIFIUTI",
)


def _cfg() -> dict[str, str]:
    return {
        "source_key": "milano-combined",
        "authority_key": "milano",
        "authority_name": "Prefettura di Milano",
        "register_key": "milano-ordinary",
        "register_name": "White List ordinaria",
        "population_scope": "listed_and_applicant",
        "reference_date": "2026-09-22",
        "source_page_url": "https://prefettura.interno.gov.it/it/prefetture/milano/evidenza/white-list",
        "resource_url": "https://whitelist.prefmi.it/elenco/elenco.php",
        "sha256": "fixture-sha",
    }


def _row(name: str, office: str, identifier: str, first: str, second: str = "", note: str = "") -> str:
    if first.startswith("RICHIESTA") or first == "IN AGGIORNAMENTO":
        status_cells = f'<td colspan="2">{first}</td>'
    else:
        status_cells = f"<td>{first}</td><td>{second}</td>"
    return f"<tr><td>{name}</td><td>{office}</td><td>{identifier}</td>{status_cells}<td>{note}</td></tr>"


def _write_fixture(tmp_path: Path, *, bad_status: bool = False) -> Path:
    rows_by_section = {
        1: _row("ALFA SRL", "Via Alfa 1 Milano (MI)", "01234567890", "01/02/2026", "01/02/2027"),
        2: _row("ALFA SRL", "Via Alfa 1 Milano (MI)", "01234567890", "01/02/2026", "01/02/2027"),
        3: _row("BETA SRL", "Via Beta 2 Milano (MI)", "12345678901", "RICHIESTA ISCRIZIONE (03/04/2026)"),
        4: _row("BETA SRL", "Via Beta 2 Milano (MI)", "12345678901", "RICHIESTA ISCRIZIONE (03/04/2026)"),
        5: _row("BETA SRL", "Via Beta 2 Milano (MI)", "12345678901", "RICHIESTA ISCRIZIONE (03/04/2026)"),
        6: _row("GAMMA SRL", "Via Gamma 3 Milano (MI)", "23456789012", "STATO NUOVO" if bad_status else "IN AGGIORNAMENTO", note="nota fonte"),
        7: _row("GAMMA SRL", "Via Gamma 3 Milano (MI)", "23456789012", "IN AGGIORNAMENTO", note="nota fonte"),
        8: _row("GAMMA SRL", "Via Gamma 3 Milano (MI)", "23456789012", "IN AGGIORNAMENTO", note="nota fonte"),
        9: _row("GAMMA SRL", "Via Gamma 3 Milano (MI)", "23456789012", "IN AGGIORNAMENTO", note="nota fonte"),
        10: _row("GAMMA SRL", "Via Gamma 3 Milano (MI)", "23456789012", "IN AGGIORNAMENTO", note="nota fonte"),
    }
    body = ["<html><body>"]
    for number, label in enumerate(SECTIONS, 1):
        body.append(
            "<table><thead>"
            f'<tr><th colspan="9">Sezione {number}<br>{label}</th></tr>'
            "<tr><th>RAGIONE SOCIALE</th><th>SEDE LEGALE</th><th>PARTITA IVA</th>"
            "<th>DATA DI ISCRIZIONE</th><th>DATA SCADENZA ISCRIZIONE</th><th>NOTE</th></tr>"
            "</thead><tbody>"
            + rows_by_section[number]
            + "</tbody></table>"
        )
    body.append("</body></html>")
    path = tmp_path / "milano.html"
    path.write_bytes("".join(body).encode("cp1252"))
    return path


def _patch_fixture_denominators(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(milano, "_EXPECTED_SECTOR_ROWS", 10)
    monkeypatch.setattr(milano, "_EXPECTED_RECORDS", 3)
    monkeypatch.setattr(
        milano,
        "_EXPECTED_STATUS_COUNTS",
        {"listed": 1, "renewal_update_in_progress": 1, "pending": 1},
    )
    monkeypatch.setattr(milano, "_EXPECTED_IDENTIFIER_COVERAGE", 3)
    monkeypatch.setattr(milano, "_EXPECTED_NONBLANK_NOTES", 1)


def test_milano_combined_statuses_colspans_and_grouping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fixture_denominators(monkeypatch)
    batch = milano.parse_milano_combined(_write_fixture(tmp_path), _cfg())

    assert len(batch.records) == 3
    by_id = {record["identifier_field_raw"]: record for record in batch.records}
    listed = by_id["01234567890"]
    pending = by_id["12345678901"]
    update = by_id["23456789012"]

    assert listed["source_status"] == "listed"
    assert listed["observed_listing_date"] == "2026-02-01"
    assert listed["observed_expiry_date"] == "2027-02-01"
    assert listed["source_fields"]["sections"] == ["Sezione 1", "Sezione 2"]
    assert len(listed["requested_activities"]) == 2

    assert pending["source_status"] == "pending"
    assert pending["application_date"] == "2026-04-03"
    assert pending["observed_listing_date"] == ""
    assert pending["record_locator"].endswith(":id-12345678901")

    assert update["source_status"] == "renewal_update_in_progress"
    assert update["source_fields"]["note"] == "nota fonte"
    assert update["source_fields"]["sections"] == [
        "Sezione 6",
        "Sezione 7",
        "Sezione 8",
        "Sezione 9",
        "Sezione 10",
    ]
    assert batch.diagnostics["sector_rows"] == 10
    assert batch.diagnostics["identifier_coverage"] == 3


def test_milano_unreviewed_status_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fixture_denominators(monkeypatch)
    with pytest.raises(RuntimeError, match="unreviewed status/date pair"):
        milano.parse_milano_combined(_write_fixture(tmp_path, bad_status=True), _cfg())


def test_milano_configuration_drift_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fixture_denominators(monkeypatch)
    cfg = _cfg()
    cfg["population_scope"] = "listed"
    with pytest.raises(RuntimeError, match="configuration drift"):
        milano.parse_milano_combined(_write_fixture(tmp_path), cfg)
