from __future__ import annotations

import json
from pathlib import Path

import pytest

from white_list_archive.parsers.potenza_webapp import parse_potenza_combined


def _cfg() -> dict[str, str]:
    return {
        "source_key": "potenza-combined",
        "authority_key": "potenza",
        "authority_name": "Prefettura di Potenza",
        "register_key": "potenza-ordinary",
        "register_name": "White List ordinaria",
        "population_scope": "listed_and_applicant",
        "reference_date": "2026-09-15",
        "source_page_url": "https://prefettura.interno.gov.it/it/prefetture/potenza/white-list",
        "resource_url": "https://www.utgpotenza.it/data/vis_imprese.php?action=list",
        "sha256": "fixture-sha",
    }


def _row(
    source_id: str,
    *,
    name: str,
    identifier: str,
    status: str,
    update: str,
    application: str | None,
    listing: str | None,
    expiry: str | None,
    note: str = "",
    expiry_marker: str = "G",
) -> dict[str, str | None]:
    return {
        "id": source_id,
        "ragione_sociale": name,
        "indirizzo_sede_legale": "Via Test, 1",
        "denom_comune_sede_legale": "Potenza",
        "partita_iva_cf": identifier,
        "richiedente": "ROSSI MARIO",
        "carica_sociale_rich": "Amministratore unico",
        "stato_richiesta": status,
        "note": note,
        "data_istanza": application,
        "data_iscriz": listing,
        "data_scad_iscriz": expiry,
        "iscriz_scaduta": expiry_marker,
        "agg_incorso": update,
    }


def _write(tmp_path: Path, rows: list[dict[str, object]], *, total: int | None = None) -> Path:
    path = tmp_path / "potenza.json"
    path.write_text(
        json.dumps(
            {
                "Result": "OK",
                "Records": rows,
                "TotalRecordCount": str(len(rows) if total is None else total),
                "SQL": "review evidence only",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_potenza_status_mapping_and_raw_provenance(tmp_path: Path) -> None:
    rows = [
        _row(
            "1",
            name="ALFA &amp; BETA SRL",
            identifier="01234567890",
            status="2",
            update="0",
            application="2024-01-02",
            listing="2024-02-03",
            expiry="2027-02-03",
        ),
        _row(
            "2",
            name="GAMMA SRL",
            identifier="RSSMRA80A01G942X",
            status="2",
            update="1",
            application="2023-03-04",
            listing="2023-05-06",
            expiry="2026-05-06",
            note="iscrizione sottoposta a controllo giudiziario",
            expiry_marker="R",
        ),
        _row(
            "3",
            name="DELTA SRL",
            identifier="0096200767",
            status="1",
            update="0",
            application="2026-04-20",
            listing=None,
            expiry=None,
            expiry_marker="NE",
        ),
    ]
    batch = parse_potenza_combined(_write(tmp_path, rows), _cfg())

    assert [record["source_status"] for record in batch.records] == [
        "listed",
        "renewal_update_in_progress",
        "pending",
    ]
    assert batch.records[0]["name"] == "ALFA & BETA SRL"
    assert batch.records[0]["registered_office"] == "Via Test, 1, Potenza"
    assert batch.records[0]["record_locator"].endswith(":id-1")
    assert batch.records[1]["source_status"] == "renewal_update_in_progress"
    assert batch.records[1]["source_fields"]["note"] == "iscrizione sottoposta a controllo giudiziario"
    assert batch.records[1]["source_fields"]["iscriz_scaduta"] == "R"
    assert batch.records[2]["identifier_field_raw"] == "0096200767"
    assert batch.records[2]["identifiers"] == []
    assert batch.records[2]["observed_listing_date"] == ""
    assert batch.records[2]["observed_expiry_date"] == ""
    assert batch.records[2]["primary_date"] == "2026-04-20"
    assert batch.records[2]["requested_activities"] == []
    assert batch.diagnostics["status_counts"] == {
        "listed": 1,
        "renewal_update_in_progress": 1,
        "pending": 1,
    }
    assert batch.diagnostics["raw_identifier_only"] == 1


def test_potenza_unknown_status_combination_fails_closed(tmp_path: Path) -> None:
    row = _row(
        "1",
        name="ALFA SRL",
        identifier="01234567890",
        status="1",
        update="1",
        application="2026-01-01",
        listing=None,
        expiry=None,
    )
    with pytest.raises(RuntimeError, match="unreviewed status combination"):
        parse_potenza_combined(_write(tmp_path, [row]), _cfg())


def test_potenza_schema_drift_fails_closed(tmp_path: Path) -> None:
    row = _row(
        "1",
        name="ALFA SRL",
        identifier="01234567890",
        status="2",
        update="0",
        application="2025-01-01",
        listing="2025-02-01",
        expiry="2027-02-01",
    )
    row["unexpected"] = "new field"
    with pytest.raises(RuntimeError, match="source-schema drift"):
        parse_potenza_combined(_write(tmp_path, [row]), _cfg())


def test_potenza_duplicate_ids_and_pagination_drift_fail_closed(tmp_path: Path) -> None:
    row = _row(
        "1",
        name="ALFA SRL",
        identifier="01234567890",
        status="2",
        update="0",
        application="2025-01-01",
        listing="2025-02-01",
        expiry="2027-02-01",
    )
    with pytest.raises(RuntimeError, match="pagination drift"):
        parse_potenza_combined(_write(tmp_path, [row], total=2), _cfg())
    with pytest.raises(RuntimeError, match="duplicate source id"):
        parse_potenza_combined(_write(tmp_path, [row, dict(row)]), _cfg())
