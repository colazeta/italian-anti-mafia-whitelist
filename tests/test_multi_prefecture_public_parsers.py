from pathlib import Path

import white_list_archive.parsers.multi_prefecture_tables as tables


class FakePage:
    def __init__(self, table_rows, words=None):
        self._table_rows = table_rows
        self._words = words or []

    def extract_tables(self):
        return [self._table_rows]

    def extract_words(self, **_kwargs):
        return self._words


class FakePDF:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def cfg(parser="test"):
    return {
        "source_key": parser,
        "authority_key": "test-authority",
        "authority_name": "Prefettura Test",
        "register_key": "test-register",
        "register_name": "Registro Test",
        "population_scope": "test",
        "reference_date": "2026-09-08",
        "source_page_url": "https://example.test/page",
        "resource_url": "https://example.test/file.pdf",
        "sha256": "abc",
    }


def test_parma_groups_sector_repetition_without_losing_activities(monkeypatch):
    rows = [
        ["Sezione I - Estrazione", "IMPRESA ALFA SRL", "PARMA VIA ROMA 1", "01234567890", "05/09/2026", "accolta"],
        ["Sezione II - Trasporto", "IMPRESA ALFA SRL", "PARMA VIA ROMA 1", "01234567890", "05/09/2026", "accolta"],
    ]
    monkeypatch.setattr(tables.pdfplumber, "open", lambda _path: FakePDF([FakePage(rows)]))
    batch = tables.parse_parma(Path("dummy.pdf"), cfg("parma"))
    assert batch.diagnostics["sector_rows"] == 2
    assert batch.diagnostics["public_records"] == 1
    record = batch.records[0]
    assert record["source_status"] == "listed"
    assert record["identifiers"] == ["01234567890"]
    assert record["application_date"] == "2026-09-05"
    assert record["requested_activities"] == ["Estrazione", "Trasporto"]


def test_pistoia_listed_groups_sector_rows_and_preserves_section_variants(monkeypatch):
    rows = [
        ["Sezione I - Estrazione", "", "", "", "", "", ""],
        ["IMPRESA BETA SRL", "PISTOIA VIA UNO 1", "", "12345678901", "21.08.2026", "20.08.2027", ""],
        ["Sezione II - Trasporto", "", "", "", "", "", ""],
        ["IMPRESA BETA SRL", "PISTOIA VIA UNO 1", "", "12345678901", "21.08.2026", "20.08.2027", ""],
    ]
    monkeypatch.setattr(tables.pdfplumber, "open", lambda _path: FakePDF([FakePage(rows)]))
    batch = tables.parse_pistoia_listed(Path("dummy.pdf"), cfg("pistoia-listed"))
    assert batch.diagnostics["sector_rows"] == 2
    assert batch.diagnostics["public_records"] == 1
    record = batch.records[0]
    assert record["source_status"] == "listed"
    assert record["observed_listing_date"] == "2026-08-21"
    assert record["observed_expiry_date"] == "2027-08-20"
    assert record["requested_activities"] == ["Estrazione", "Trasporto"]
    assert len(record["source_fields"]["sections"]) == 2


def test_pistoia_applicant_recovers_page_boundary_name(monkeypatch):
    rows = [["", "PISTOIA VIA DUE 2", "", "23456789012", "Attività richiesta", "21.08.2026", "in istruttoria"]]
    words = [
        {"text": "IMPRESA", "x0": 20, "top": 90, "bottom": 100},
        {"text": "GAMMA", "x0": 70, "top": 90, "bottom": 100},
        {"text": "21.08.2026", "x0": 300, "top": 90, "bottom": 100},
    ]
    monkeypatch.setattr(tables.pdfplumber, "open", lambda _path: FakePDF([FakePage(rows, words)]))
    batch = tables.parse_pistoia_applicants(Path("dummy.pdf"), cfg("pistoia-applicants"))
    assert batch.diagnostics["date_rows"] == 1
    assert batch.diagnostics["public_records"] == 1
    assert batch.diagnostics["recovered_names"] == 1
    assert batch.diagnostics["dropped_date_rows"] == 0
    assert batch.records[0]["name"] == "IMPRESA GAMMA"
    assert batch.records[0]["source_status"] == "pending"


def test_alessandria_listed_groups_sections_and_normalises_variable_width_dates(monkeypatch):
    rows = [
        ["SEZIONE I", "", "", "", "", "", ""],
        ["IMPRESA ALFA S.R.L.", "ALESSANDRIA", "", "01234567890", "9.6.2025", "8.6.2026", "In istruttoria per rinnovo"],
        ["SEZIONE II", "", "", "", "", "", ""],
        ["IMPRESA ALFA S.R.L.", "ALESSANDRIA", "", "01234567890", "9.6.2025", "8.6.2026", "In istruttoria per rinnovo"],
    ]
    monkeypatch.setattr(tables.pdfplumber, "open", lambda _path: FakePDF([FakePage(rows)]))
    batch = tables.parse_alessandria_listed(Path("listed.pdf"), cfg("alessandria-listed"))
    assert batch.diagnostics["date_rows"] == 2
    assert batch.diagnostics["sector_rows"] == 2
    assert batch.diagnostics["public_records"] == 1
    assert batch.diagnostics["dropped_date_rows"] == 0
    record = batch.records[0]
    assert record["observed_listing_date"] == "2025-06-09"
    assert record["observed_expiry_date"] == "2026-06-08"
    assert record["source_status"] == "renewal_update_in_progress"
    assert record["requested_activities"] == ["SEZIONE I", "SEZIONE II"]


def test_alessandria_listed_preserves_ambiguous_bare_in_istruttoria(monkeypatch):
    rows = [["IMPRESA BETA S.R.L.", "ALESSANDRIA", "", "12345678901", "2.7.2026", "1.7.2027", "In istruttoria"]]
    monkeypatch.setattr(tables.pdfplumber, "open", lambda _path: FakePDF([FakePage(rows)]))
    batch = tables.parse_alessandria_listed(Path("listed.pdf"), cfg("alessandria-listed"))
    assert batch.records[0]["source_status"] == "other_or_unknown"
    assert batch.records[0]["outcome_raw"] == "In istruttoria"


def test_alessandria_applicants_preserve_raw_unusual_ids_and_numbered_sections(monkeypatch):
    rows = [
        ["IMPRESA GAMMA S.R.L.", "OVADA", "2742900067", "SEZIONE:1-5-6", "19.6.2026", "In istruttoria"],
        ["IMPRESA DELTA S.R.L.", "TORTONA", "23456789012", "SEZIONE. 10", "21.07.2026", "In istruttoria"],
    ]
    monkeypatch.setattr(tables.pdfplumber, "open", lambda _path: FakePDF([FakePage(rows)]))
    batch = tables.parse_alessandria_applicants(Path("applicants.pdf"), cfg("alessandria-applicants"))
    assert batch.diagnostics["date_rows"] == 2
    assert batch.diagnostics["public_records"] == 2
    assert batch.diagnostics["dropped_date_rows"] == 0
    assert batch.records[0]["identifier_field_raw"] == "2742900067"
    assert batch.records[0]["identifiers"] == []
    assert batch.records[0]["requested_activities"] == ["Sezione 1", "Sezione 5", "Sezione 6"]
    assert batch.records[0]["application_date"] == "2026-06-19"
    assert batch.records[0]["source_status"] == "pending"
    assert batch.records[1]["identifiers"] == ["23456789012"]
    assert batch.records[1]["requested_activities"] == ["Sezione 10"]


def test_bologna_date_relative_parser_survives_leading_and_trailing_blank_columns(monkeypatch):
    listed = [["", "IMPRESA DELTA SRL", "34567890123", "BOLOGNA VIA TRE 3", "Prot. 1", "2026-08-14", "2027-08-13", "Sì", "I · II", ""]]
    monkeypatch.setattr(tables.pdfplumber, "open", lambda _path: FakePDF([FakePage(listed)]))
    listed_batch = tables.parse_bologna_listed(Path("listed.pdf"), cfg("bologna-listed"))
    assert listed_batch.diagnostics["dropped_date_rows"] == 0
    assert listed_batch.records[0]["source_status"] == "renewal_update_in_progress"
    assert listed_batch.records[0]["decision_date"] == "2026-08-14"

    applicants = [["", "IMPRESA EPSILON SRL", "45678901234", "BOLOGNA VIA QUATTRO 4", "2026-08-14", "III · IV", ""]]
    monkeypatch.setattr(tables.pdfplumber, "open", lambda _path: FakePDF([FakePage(applicants)]))
    applicant_batch = tables.parse_bologna_applicants(Path("applicants.pdf"), cfg("bologna-applicants"))
    assert applicant_batch.diagnostics["dropped_date_rows"] == 0
    assert applicant_batch.records[0]["source_status"] == "pending"
    assert applicant_batch.records[0]["registration_date"] == "2026-08-14"
