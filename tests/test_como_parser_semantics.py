from __future__ import annotations

from pathlib import Path

import pytest

from white_list_archive.parsers.como_html import parse_como_applicants, parse_como_listed
from white_list_archive.publishing.public_contract import public_record


def _cfg(source_key: str, population_scope: str) -> dict[str, str]:
    return {
        "source_key": source_key,
        "authority_key": "como",
        "authority_name": "Prefettura di Como",
        "register_key": "como-ordinary",
        "register_name": "White List ordinaria",
        "population_scope": population_scope,
        "reference_date": "2026-09-10",
        "source_page_url": f"https://prefettura.interno.gov.it/it/prefetture/como/{source_key}",
        "resource_url": f"https://prefettura.interno.gov.it/it/prefetture/como/{source_key}",
        "sha256": "0" * 64,
    }


def _write(tmp_path: Path, name: str, rows: list[list[str]]) -> Path:
    cells = []
    for row in rows:
        cells.append("<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>")
    path = tmp_path / name
    path.write_text("<html><body><table>" + "".join(cells) + "</table></body></html>", encoding="utf-8")
    return path


def test_como_listed_preserves_physical_rows_and_explicit_status(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "listed.html",
        [
            [
                "ELENCO DEI FORNITORI, PRESTATORI DI SERVIZI ED ESECUTORI DI LAVORI NON SOGGETTI A TENTATIVO DI INFILTRAZIONE MAFIOSA",
                "", "", "", "", "", "", "",
            ],
            ["NUMERO AZIENDE ISCRITTE:", "1", "", "", "", "", "", ""],
            [
                "Ragione sociale", "Sede legale", "C.F./P.I.", "Data iscrizione",
                "Scadenza iscrizione", "Settori di attività", "Note", "Mese di presentazione rinnovo",
            ],
            ["ALFA S.R.L.", "COMO", "01234567890", "03/06/2024", "3-giu-2027", "Sez. I - Sez. III", "", ""],
            ["BETA S.R.L.", "CANTU'", "CHE-114.109.939", "07 gosto 2026", "7-ago-2027", "Sez. II", "FASE DI RINNOVO", "ago-26"],
        ],
    )

    batch = parse_como_listed(path, _cfg("como-listed", "listed"))

    assert len(batch.records) == 2
    assert batch.diagnostics["declared_count"] == 1
    assert batch.diagnostics["declared_count_delta"] == 1
    assert batch.diagnostics["status_counts"] == {"listed": 1, "renewal_update_in_progress": 1}
    assert batch.diagnostics["malformed_date_rows"] == 1
    alpha, beta = batch.records
    assert alpha["observed_listing_date"] == "2024-06-03"
    assert alpha["observed_expiry_date"] == "2027-06-03"
    assert alpha["requested_activities"] == ["Sez. I", "Sez. III"]
    assert beta["source_status"] == "renewal_update_in_progress"
    assert beta["observed_listing_date"] == ""
    assert beta["observed_expiry_date"] == "2027-08-07"
    assert beta["identifiers"] == []
    assert beta["identifier_field_raw"] == "CHE-114.109.939"
    assert beta["source_fields"]["malformed_date_pairs"] == ["listing=07 gosto 2026"]
    assert "Mese di presentazione rinnovo: ago-26" in beta["source_fields"]["notes"]
    assert public_record(alpha)["name"] == "ALFA S.R.L."
    assert public_record(beta)["name"] == "BETA S.R.L."


def test_como_applicants_keep_month_only_evidence_without_invented_date(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "applicants.html",
        [
            ["ELENCO DELLE IMPRESE RICHIEDENTI L'ISCRIZIONE", "", "", "", "", "", "", ""],
            ["NUMERO AZIENDE IN FASE ISCRIZIONE:", "0", "", "", "", "", "", ""],
            [
                "Ragione sociale", "Sede legale", "C.F./P.I.", "Note", "",
                "Settori di attività", "", "Mese di presentazione della domanda",
            ],
            ["GAMMA S.R.L.", "COMO", "01234567890", "", "", "Sez. IV", "", "set-26"],
        ],
    )

    batch = parse_como_applicants(path, _cfg("como-applicants", "applicant"))

    assert len(batch.records) == 1
    assert batch.diagnostics["declared_count"] == 0
    assert batch.diagnostics["declared_count_delta"] == 1
    assert batch.diagnostics["status_counts"] == {"pending": 1}
    record = batch.records[0]
    assert record["source_status"] == "pending"
    assert record["application_date"] == ""
    assert record["primary_date"] == ""
    assert record["source_fields"]["application_date_raw"] == "set-26"
    assert public_record(record)["source_status"] == "pending"


def test_como_parser_fails_closed_on_header_drift(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "drift.html",
        [
            [
                "ELENCO DEI FORNITORI, PRESTATORI DI SERVIZI ED ESECUTORI DI LAVORI NON SOGGETTI A TENTATIVO DI INFILTRAZIONE MAFIOSA",
                "", "", "", "", "", "", "",
            ],
            ["NUMERO AZIENDE ISCRITTE:", "1", "", "", "", "", "", ""],
            ["Ragione sociale", "Sede legale", "Codice fiscale", "Data iscrizione", "Scadenza iscrizione", "Settori di attività", "Note", "Mese di presentazione rinnovo"],
            ["ALFA S.R.L.", "COMO", "01234567890", "03/06/2024", "3-giu-2027", "Sez. I", "", ""],
        ],
    )

    with pytest.raises(ValueError, match="exactly one Como listed table"):
        parse_como_listed(path, _cfg("como-listed", "listed"))
