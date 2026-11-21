"""Synthetic-only regression of redacted printed provenance clues for Reggio."""
import json
from types import SimpleNamespace

from white_list_archive.acquisition.reggio_archive_census import printed_provenance_flags


class Page:
    width = 600
    height = 800

    def __init__(self, header, footer):
        self.header = header
        self.footer = footer

    def crop(self, bbox):
        return SimpleNamespace(extract_text=lambda: self.header if bbox[1] == 0 else self.footer)


def test_exact_page_and_date_are_corroborration_only():
    page = Page("PREFETTURA DI REGGIO CALABRIA\nSECRET PERSONAL ROW",
                "pag. 3 di 72\n16/11/2026\nPRIVATE NAME")
    evidence = printed_provenance_flags(page, 3, 72)
    assert evidence == {
        "authority_in_header": True,
        "exact_footer_pagination": True,
        "16_nov_2026_in_footer": True,
        "joint_footer_date_and_pagination": True,
    }
    assert "SECRET" not in json.dumps(evidence)
    assert "PRIVATE" not in json.dumps(evidence)


def test_row_date_does_not_count_as_printed_footer_date():
    page = Page("PREFETTURA DI REGGIO CALABRIA 16/11/2026",
                "pag. 3 di 72\nPRIVATE SOURCE CELL")
    evidence = printed_provenance_flags(page, 3, 72)
    assert evidence["authority_in_header"]
    assert evidence["exact_footer_pagination"]
    assert not evidence["16_nov_2026_in_footer"]
    assert not evidence["joint_footer_date_and_pagination"]


def test_wrong_pagination_or_wrong_source_date_never_proves_a_match():
    page = Page("PREFETTURA DI REGGIO CALABRIA", "pag. 4 di 72\n16/11/2026")
    evidence = printed_provenance_flags(page, 3, 72)
    assert evidence["16_nov_2026_in_footer"]
    assert not evidence["joint_footer_date_and_pagination"]
    unrelated = printed_provenance_flags(Page("PREFETTURA DI ALTRA CITTÀ", "pag. 3 di 72\n15/11/2026"), 3, 72)
    assert not unrelated["authority_in_header"]
    assert not unrelated["16_nov_2026_in_footer"]
    assert not unrelated["joint_footer_date_and_pagination"]


def test_missing_or_undecodable_headings_are_unknown_not_success():
    evidence = printed_provenance_flags(Page(None, None), 1, 1)
    assert not any(evidence.values())
