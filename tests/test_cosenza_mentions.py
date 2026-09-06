from white_list_archive.parsers.cosenza_combined_mentions import diff_mentions, parse_mentions


def _row(name: str, address: str, identifier: str, status: str) -> str:
    return f"{name:<42}   {address:<35}   {identifier}   attività   01/01/2026   {status}"


def test_parser_preserves_ambiguous_identifiers_as_distinct_mentions():
    text = "\n".join(
        [
            _row("ALFA SRL", "COSENZA VIA A 1", "01234567890", "IN ISTRUTTORIA"),
            _row("BETA DI MARIO ROSSI", "RENDE VIA B 2", "01234567890", "IN ISTRUTTORIA"),
        ]
    )
    records = parse_mentions(text)
    assert len(records) == 2
    assert records[0].identifier_raw == records[1].identifier_raw
    assert records[0].mention_key != records[1].mention_key


def test_parser_understands_multiline_published_outcomes():
    text = "\n".join(
        [
            _row("ALFA SRL", "COSENZA VIA A 1", "01234567890", "INSERITO NELLE"),
            " " * 150 + "LISTE IN DATA",
            " " * 150 + "03/07/2026",
            _row("BETA SRL", "RENDE VIA B 2", "01234567891", "RICHIESTA DI"),
            " " * 150 + "RINNOVO -",
            " " * 150 + "AGGIORNAMENTO IN CORSO",
        ]
    )
    records = parse_mentions(text)
    assert [record.source_status for record in records] == [
        "listed",
        "renewal_update_in_progress",
    ]


def test_diff_is_observational_and_separates_name_change_from_new_identifier():
    before = parse_mentions(
        "\n".join(
            [
                _row("ALFA SRLS", "COSENZA VIA A 1", "01234567890", "IN ISTRUTTORIA"),
                _row("BETA SRL", "RENDE VIA B 2", "01234567891", "IN ISTRUTTORIA"),
            ]
        )
    )
    after = parse_mentions(
        "\n".join(
            [
                _row("ALFA SRL", "COSENZA VIA A 1", "01234567890", "INSERITO NELLE") + "\n" + " " * 150 + "LISTE IN DATA",
                _row("GAMMA SRL", "MONTALTO VIA C 3", "01234567892", "IN ISTRUTTORIA"),
            ]
        )
    )
    diff = diff_mentions(before, after)
    assert diff["records"] == {"before": 2, "after": 2, "net": 0}
    assert diff["identifier_observations"]["new_identifiers"] == 1
    assert diff["identifier_observations"]["disappeared_identifiers"] == 1
    assert diff["identifier_observations"]["stable_identifier_name_changes"] == 1
    assert "not administrative registration/removal" in diff["interpretation_guardrails"][0]
