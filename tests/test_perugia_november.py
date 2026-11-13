"""November regressions use synthetic cells, never real company data."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from white_list_archive.parsers import perugia_tables as september
from white_list_archive.parsers import perugia_tables_november as november
from white_list_archive.publishing.public_national_registry import _adapt_perugia_public_fields
from white_list_archive.publishing.public_contract import public_record


def cfg(label):
    return dict(authority_key="perugia", authority_name="Prefettura di Perugia",
                register_key="perugia-ordinary", register_name="White List ordinaria",
                source_key=f"perugia-{label}", reference_date="2026-11-05",
                population_scope="listed" if label == "listed" else "applicant",
                sha256=november._PINS[label], parser=f"perugia_{label}_2026_11",
                source_page_url="https://example.test/page", resource_url="https://example.test/source")


def test_original_and_configuration_must_both_match_and_legacy_is_unchanged(tmp_path):
    source = tmp_path / "new.pdf"; source.write_bytes(b"unreviewed")
    old = (september._REFERENCE_DATE, september._LISTED_SHA256, september._APPLICANT_SHA256)
    with pytest.raises(RuntimeError, match="original SHA"):
        november._validate(source, cfg("listed"), "listed")
    for field in ("authority_key", "register_key", "source_key", "population_scope", "sha256", "reference_date", "parser"):
        changed = cfg("listed"); changed[field] = "different"
        with pytest.raises(RuntimeError, match="configuration drift"):
            november._validate(source, changed, "listed")
    assert old == (september._REFERENCE_DATE, september._LISTED_SHA256, september._APPLICANT_SHA256)
    assert not (november.PARSERS.keys() & september.PARSERS.keys())


def row(page, n, cells):
    return dict(page=page, row=n, cells=cells, fragments=[], section="")


def test_previous_and_following_fragments_never_become_extra_companies(monkeypatch):
    first = ["EXAMPLE LTD", "Town", "", "01234567890", "Road", "01/01/2025", "Iscritta in"]
    continuation = ["", "", "", "", "transport", "", "data 01/02/2025"]
    forward = ["", "", "", "", "Earth", "", "Rinnovo iscrizione in"]
    second = ["SECOND LTD", "Town", "", "12345678901", "supply", "02/01/2025", "data 03/02/2025"]
    expected = [row(1, 1, ["EXAMPLE LTD", "Town", "", "01234567890", "Road transport", "01/01/2025", "Iscritta in data 01/02/2025"]),
                row(3, 1, ["SECOND LTD", "Town", "", "12345678901", "Earth supply", "02/01/2025", "Rinnovo iscrizione in data 03/02/2025"])]
    expected[0]["fragments"] = [dict(page=2, row=1, cells=continuation)]
    expected[1]["fragments"] = [dict(page=2, row=2, cells=forward, direction="following-row")]
    class Table:
        def __init__(self, rows): self.rows = rows
        def extract(self): return self.rows
    class Page:
        def __init__(self, rows): self.rows = rows
        def find_tables(self): return [Table(self.rows)]
    class PDF:
        pages = [Page([first]), Page([continuation, forward]), Page([second])]
        def __enter__(self): return self
        def __exit__(self, *args): pass
    profile = dict(pages=3, physical=4, blanks=0, headers=[], previous=[[2, 1]],
                   no_tables=[], logical_rows=2, row_digest=november._digest(expected))
    monkeypatch.setattr(november, "_FORWARD", (2, 2))
    monkeypatch.setitem(november._PROFILE, "applicants", profile)
    monkeypatch.setattr(november.pdfplumber, "open", lambda _: PDF())
    actual = november._source_rows(Path("synthetic.pdf"), "applicants")
    assert json.loads(json.dumps(actual)) == expected
    records = november._applicants(actual, cfg("applicants"))
    assert [r["decision_date"] for r in records] == ["2025-02-01", "2025-02-03"]
    assert records[1]["requested_activities"] == ["Earth supply"]
    public = _adapt_perugia_public_fields(SimpleNamespace(records=records, diagnostics={}), "perugia_applicants")
    assert all(public_record(r) == r for r in public.records)
    assert all("continuation_fragments" not in r["source_fields"] for r in public.records)
    # A lost field/incorrect attachment cannot silently pass on identical pages/counts.
    first[4] = "changed source cell"
    with pytest.raises(RuntimeError, match="stitching contract"):
        november._source_rows(Path("synthetic.pdf"), "applicants")


def test_bare_future_outcome_is_not_a_decision_or_positive_status():
    r = row(185, 2, ["EXAMPLE LTD", "", "", "", "", "", "27/11/2026"])
    assert november._outcome(r) == ("other_or_unknown", "")
    r["page"] = 184
    with pytest.raises(RuntimeError, match="unreviewed outcome"):
        november._outcome(r)


def test_raw_malformed_calendar_dates_are_never_repaired():
    r = row(17, 4, ["EXAMPLE LTD", "", "", "", "19/11/2025", "1 8/11/2026", ""])
    assert november._date(r, 5, "listed") == ""
    r["row"] = 5
    with pytest.raises(RuntimeError, match="typography"):
        november._date(r, 5, "listed")
    r["cells"][5] = "31/02/2026"
    with pytest.raises(RuntimeError, match="invalid calendar"):
        november._date(r, 5, "listed")
