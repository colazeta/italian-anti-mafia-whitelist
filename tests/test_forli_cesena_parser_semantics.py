from __future__ import annotations

import pytest

from white_list_archive.parsers.forli_cesena_combined import _parse_record_block
from white_list_archive.publishing.public_contract import public_record


def _cfg() -> dict[str, str]:
    return {
        "source_key": "forli-cesena-combined",
        "authority_key": "forli-cesena",
        "authority_name": "Prefettura di Forlì-Cesena",
        "register_key": "forli-cesena-white-list",
        "register_name": "White list",
        "population_scope": "combined",
        "reference_date": "2026-09-11",
        "source_page_url": "https://prefettura.interno.gov.it/it/prefetture/forli-cesena/evidenza/white-list",
        "resource_url": "https://prefettura.interno.gov.it/sites/default/files/44/2026-09/wlp-al-11-09-2026.pdf",
        "sha256": "f18e1980e6f7f5bc2ac55a55926ab7a221f290fc7a40f5d0781eef4885455468",
    }


def _parse(identifier: str, name: str, id_kind: str, lines: list[str]):
    record = _parse_record_block(1, 1, identifier, name, id_kind, lines, _cfg(), 1)[0]
    public_record(record)
    return record


def test_listed_row_preserves_provvedimento_and_address() -> None:
    record = _parse(
        "03275390403",
        "3 B AUTOTRASPORTI DI BUCCI EZIO & FIGLI S.N.C.",
        "strict_11_digit",
        [
            "  03275390403 3 B AUTOTRASPORTI DI BUCCI EZIO & FIGLI S.N.C.",
            "          VIA P. NENNI, 35                       Provv. n. 23508/2026 del 20/03/2026 Scadenza 19/03/2027",
            "          MERCATO SARACENO (FC)",
            "                                                 Sezioni.: I II III IV V VI VII VIII IX X",
        ],
    )
    assert record["source_status"] == "listed"
    assert record["identifiers"] == ["03275390403"]
    assert record["decision_date"] == "2026-03-20"
    assert record["observed_expiry_date"] == "2027-03-19"
    assert record["registered_office"] == "VIA P. NENNI, 35 MERCATO SARACENO (FC)"
    assert "Provv. n. 23508/2026" in record["source_fields"]["provvedimento"]
    assert record["source_fields"]["sections"] == [
        "Sezione I", "Sezione II", "Sezione III", "Sezione IV", "Sezione V",
        "Sezione VI", "Sezione VII", "Sezione VIII", "Sezione IX", "Sezione X",
    ]


def test_renewal_row_follows_explicit_current_status() -> None:
    record = _parse(
        "03784080404",
        "A.S.S.O. S.R.L.",
        "strict_11_digit",
        [
            "  03784080404 A.S.S.O. S.R.L.",
            "          VIA ANTICO ACQUEDOTTO, 36              Provv. n. 49342/2025 del 18/06/2025 Scadenza 17/06/2026 IN AGGIORNAMENTO",
            "                                                                                        DAL 13/05/2026",
            "          FORLI' (FC)",
            "                                                 Sezioni.: I II III IV V VI VII VIII IX X",
        ],
    )
    assert record["source_status"] == "renewal_update_in_progress"
    assert record["outcome_raw"] == "IN AGGIORNAMENTO"
    assert record["decision_date"] == "2025-06-18"
    assert record["source_fields"]["in_aggiornamento"] == "DAL 13/05/2026"
    assert record["source_fields"]["outcome"]["dates"] == [
        {"raw_value": "DAL 13/05/2026", "date": "2026-05-13", "parenthesized": False}
    ]


def test_del_status_date_is_preserved_and_normalised() -> None:
    record = _parse(
        "01234567890",
        "DEL DATE TEST SRL",
        "strict_11_digit",
        [
            "  01234567890 DEL DATE TEST SRL",
            "          VIA TEST 9                           Provv. n.   del        Scadenza       IN AGGIORNAMENTO",
            "                                                                                     DEL 09/07/2026",
            "          GATTEO (FC)",
            "                                                 Sezioni.: I II III IV V VI VII VIII IX X",
        ],
    )
    assert record["source_status"] == "renewal_update_in_progress"
    assert record["source_fields"]["in_aggiornamento"] == "DEL 09/07/2026"
    assert record["source_fields"]["outcome"]["dates"] == [
        {"raw_value": "DEL 09/07/2026", "date": "2026-07-09", "parenthesized": False}
    ]


def test_il_status_date_is_preserved_and_normalised() -> None:
    record = _parse(
        "01234567890",
        "IL DATE TEST SRL",
        "strict_11_digit",
        [
            "  01234567890 IL DATE TEST SRL",
            "          VIA TEST 10                          Provv. n.   del        Scadenza       IN AGGIORNAMENTO",
            "                                                                                     IL 29/04/2026",
            "          MODIGLIANA (FC) 47015",
            "                                                 Sezioni.: I II III IV V VI VII VIII IX X",
        ],
    )
    assert record["source_status"] == "renewal_update_in_progress"
    assert record["registered_office"] == "VIA TEST 10 MODIGLIANA (FC) 47015"
    assert record["source_fields"]["in_aggiornamento"] == "IL 29/04/2026"
    assert record["source_fields"]["outcome"]["dates"] == [
        {"raw_value": "IL 29/04/2026", "date": "2026-04-29", "parenthesized": False}
    ]


def test_da_status_date_is_preserved_and_normalised() -> None:
    record = _parse(
        "01234567890",
        "DA DATE TEST SRL",
        "strict_11_digit",
        [
            "  01234567890 DA DATE TEST SRL",
            "          VIA TEST 12                          Provv. n.   del        Scadenza       IN AGGIORNAMENTO",
            "                                                                                     DA 24/06/2026",
            "          FORLI' (FC)",
            "                                                 Sezioni.: I II III IV V VI VII VIII IX X",
        ],
    )
    assert record["source_status"] == "renewal_update_in_progress"
    assert record["source_fields"]["in_aggiornamento"] == "DA 24/06/2026"
    assert record["source_fields"]["outcome"]["dates"] == [
        {"raw_value": "DA 24/06/2026", "date": "2026-06-24", "parenthesized": False}
    ]


def test_malformed_status_date_is_preserved_without_repair() -> None:
    record = _parse(
        "01234567890",
        "MALFORMED DATE TEST SRL",
        "strict_11_digit",
        [
            "  01234567890 MALFORMED DATE TEST SRL",
            "          VIA TEST 11                          Provv. n.   del        Scadenza       IN AGGIORNAMENTO",
            "                                                                                     DAL 11/04/20226",
            "          CESENATICO (FC)",
            "                                                 Sezioni.: I II III IV V VI VII VIII IX X",
        ],
    )
    assert record["source_status"] == "renewal_update_in_progress"
    assert record["source_fields"]["in_aggiornamento"] == "DAL 11/04/20226"
    assert record["source_fields"]["outcome"]["dates"] == [
        {"raw_value": "DAL 11/04/20226", "date": "", "parenthesized": False}
    ]


def test_pending_row_does_not_fabricate_provvedimento_dates() -> None:
    record = _parse(
        "04597520404",
        "A.G. TRASPORTI DI ALESSI GIACOMO - IMPRESA INDIVIDUALE",
        "strict_11_digit",
        [
            "  04597520404 A.G. TRASPORTI DI ALESSI GIACOMO - IMPRESA INDIVIDUALE",
            "          VIA T. TASSO 20                        Provv. n.   del        Scadenza       AVVIO ISTRUTTORIA",
            "                                                                                          08/01/2026",
            "          GAMBETTOLA - FC",
            "                                                 Sezioni.: I II III IV V VI VII VIII IX X",
        ],
    )
    assert record["source_status"] == "pending"
    assert record["decision_date"] == ""
    assert record["observed_expiry_date"] == ""
    assert record["source_fields"]["outcome"]["status"] == "pending"
    assert record["source_fields"]["outcome"]["dates"][0]["raw_value"] == "08/01/2026"


def test_reviewed_irregular_identifiers_are_not_repaired() -> None:
    ten_digit = _parse(
        "0543034730",
        "V8 TRASPORTI & LOGISTICA SRL",
        "reviewed_10_digit_source_exception",
        [
            "  0543034730 V8 TRASPORTI & LOGISTICA SRL",
            "          VIA N. COPERNICO 83/85                 Provv. n.   del        Scadenza       AVVIO ISTRUTTORIA",
            "                                                                                        DAL 30/07/2026",
            "          47122 FORLI' (FC)",
            "                                                 Sezioni.: I II III IV V VI VII VIII IX X",
        ],
    )
    assert ten_digit["identifier_field_raw"] == "0543034730"
    assert ten_digit["identifiers"] == []

    foreign = _parse(
        "",
        "GRUPPO IDRODEMOLIZIONI SRL - SOCIETA' ESTERA",
        "reviewed_blank_identifier_foreign_exception",
        [
            "          GRUPPO IDRODEMOLIZIONI SRL - SOCIETA' ESTERA",
            "                                                 Provv. n.   del        Scadenza       AVVIO ISTRUTTORIA",
            "                                                                                        DAL 06/07/2026",
            "          SAN MARINO",
            "                                                 Sezioni.: I II III IV V VI VII VIII IX X",
        ],
    )
    assert foreign["identifier_field_raw"] == ""
    assert foreign["identifiers"] == []
    assert foreign["registered_office"] == "SAN MARINO"


def test_unreviewed_layout_or_status_drift_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="multiple current-status markers"):
        _parse(
            "01234567890",
            "TEST SRL",
            "strict_11_digit",
            [
                "  01234567890 TEST SRL",
                "          VIA TEST 1 Provv. n. 1/2026 del 01/01/2026 Scadenza 01/01/2027 IN AGGIORNAMENTO AVVIO ISTRUTTORIA",
                "          FORLI' (FC)",
                "          Sezioni.: I II III IV V VI VII VIII IX X",
            ],
        )
