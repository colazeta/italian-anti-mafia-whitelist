from pathlib import Path

import white_list_archive.parsers.multi_prefecture_tables as tables


class FakePage:
    def __init__(self, rows):
        self._rows = rows

    def extract_tables(self):
        return [self._rows]


class FakePDF:
    def __init__(self, rows):
        self.pages = [FakePage(rows)]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def cfg():
    return {
        "source_key": "alessandria-listed",
        "authority_key": "alessandria",
        "authority_name": "Prefettura di Alessandria",
        "register_key": "alessandria-ordinary",
        "register_name": "White List ordinaria",
        "population_scope": "listed",
        "reference_date": "2026-09-04",
        "source_page_url": "https://example.test/alessandria",
        "resource_url": "https://example.test/listed.pdf",
        "sha256": "abc",
    }


def parse(monkeypatch, rows):
    monkeypatch.setattr(tables.pdfplumber, "open", lambda _path: FakePDF(rows))
    return tables.parse_alessandria_listed(Path("listed.pdf"), cfg())


def test_alessandria_normalises_explicit_ordinal_and_layout_space(monkeypatch):
    rows = [
        ["SEZIONE I", "", "", "", "", "", ""],
        ["EDILNORD S.R.L.", "CASALE MONFERRATO", "", "02244500068", "2.5.2024", "1°.5.2025", "In istruttoria per rinnovo"],
        ["SEZIONE II", "", "", "", "", "", ""],
        ["EDILFLASH S.R.L.", "TORTONA", "", "02291860068", "1°.12.202 2", "30.11.2023", "In istruttoria per rinnovo"],
    ]
    batch = parse(monkeypatch, rows)

    assert batch.diagnostics["sector_rows"] == 2
    assert batch.diagnostics["public_records"] == 2
    assert batch.diagnostics["dropped_date_rows"] == 0

    by_name = {record["name"]: record for record in batch.records}
    assert by_name["EDILNORD S.R.L."]["observed_listing_date"] == "2024-05-02"
    assert by_name["EDILNORD S.R.L."]["observed_expiry_date"] == "2025-05-01"
    assert by_name["EDILFLASH S.R.L."]["observed_listing_date"] == "2022-12-01"
    assert by_name["EDILFLASH S.R.L."]["observed_expiry_date"] == "2023-11-30"


def test_alessandria_reconciles_invalid_date_only_from_same_repeated_source_identity(monkeypatch):
    rows = [
        ["SEZIONE I", "", "", "", "", "", ""],
        ["EDIL SINA S.R.L.", "ALESSANDRIA", "", "02614330062", "6.5.2025", "5.5.2026", "In istruttoria per rinnovo"],
        ["SEZIONE II", "", "", "", "", "", ""],
        ["EDIL SINA S.R.L.", "ALESSANDRIA", "", "02614330062", "6.5.2025", "65.5.2026", "In istruttoria per rinnovo"],
    ]
    batch = parse(monkeypatch, rows)

    assert batch.diagnostics["sector_rows"] == 2
    assert batch.diagnostics["public_records"] == 1
    assert batch.diagnostics["dropped_date_rows"] == 0
    assert batch.diagnostics["reconciled_malformed_date_rows"] == 1
    record = batch.records[0]
    assert record["observed_listing_date"] == "2025-05-06"
    assert record["observed_expiry_date"] == "2026-05-05"
    assert record["source_fields"]["expiry_date_raw_variants"] == ["5.5.2026", "65.5.2026"]
    assert record["source_fields"]["normalised_expiry_date_variants"] == ["2026-05-05"]
    assert record["source_fields"]["malformed_date_pairs"] == ["6.5.2025 | 65.5.2026"]


def test_alessandria_does_not_choose_between_conflicting_source_dates(monkeypatch):
    rows = [
        ["SEZIONE III", "", "", "", "", "", ""],
        ["GESTIONE AMBIENTE S.P.A.", "ALESSANDRIA", "", "01492290067", "15.04.2025", "13.04.2026", "In istruttoria per rinnovo"],
        ["SEZIONE VI", "", "", "", "", "", ""],
        ["GESTIONE AMBIENTE S.P.A.", "ALESSANDRIA", "", "01492290067", "15.04.2025", "14.04.2026", "In istruttoria per rinnovo"],
    ]
    batch = parse(monkeypatch, rows)

    assert batch.diagnostics["public_records"] == 1
    assert batch.diagnostics["date_conflict_groups"] == 1
    assert batch.diagnostics["dropped_date_rows"] == 0
    record = batch.records[0]
    assert record["observed_listing_date"] == "2025-04-15"
    assert record["observed_expiry_date"] == ""
    assert record["source_fields"]["normalised_expiry_date_variants"] == ["2026-04-13", "2026-04-14"]
    assert record["source_fields"]["date_conflict_fields"] == ["observed_expiry_date"]
