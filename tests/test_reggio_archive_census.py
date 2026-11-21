"""Synthetic-only regression of redacted printed provenance clues for Reggio."""
import json
from types import SimpleNamespace
from pathlib import Path

from white_list_archive.acquisition.reggio_archive_census import (
    printed_provenance_flags, printed_title_date_flags, source_identifier_shape)


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


def test_read_only_reggio_probe_not_skipped_by_independent_ascoli_failure():
    workflow = (Path(__file__).resolve().parents[1]
                / ".github/workflows/transform-reviewed-captures.yml").read_text()
    reggio = workflow.split(
        "- name: Census exact Reggio Calabria 16 November candidate originals (read-only)", 1)[1]
    block = reggio.split("- name:", 1)[0]
    assert "if: ${{ matrix.shard == 0 && !cancelled() }}" in block
    assert "continue-on-error: true" in block
    ascoli = workflow.split("- name: Materialise exact reviewed Ascoli source snapshot (private only)", 1)[1]
    assert "continue-on-error: true" not in ascoli.split("- name:", 1)[0]


def test_applicant_title_date_is_redacted_and_not_an_approved_edition():
    p = Page("PREFETTURA DI REGGIO CALABRIA\n"
             "Elenco imprese richiedenti iscrizione White List 16/11/2026\n"
             "PRIVATE COMPANY CF 12345678901", None)
    flags = printed_title_date_flags(p, "applicant")
    assert flags == {
        "population_title_in_upper_margin": True,
        "16_nov_2026_attached_to_title": True,
    }
    assert "PRIVATE" not in json.dumps(flags)
    assert "12345678901" not in json.dumps(flags)


def test_row_date_unlabelled_adjacent_date_is_not_title_date():
    p = Page("PREFETTURA DI REGGIO CALABRIA\n"
             "Elenco imprese richiedenti iscrizione\n"
             "16/11/2026 PRIVATE COMPANY 12345678901", None)
    flags = printed_title_date_flags(p, "applicant")
    assert flags["population_title_in_upper_margin"]
    assert not flags["16_nov_2026_attached_to_title"]
    explicitly_labelled = Page("Elenco imprese richiedenti iscrizione\n"
                               "Aggiornato al 16 novembre 2026", None)
    assert printed_title_date_flags(explicitly_labelled, "applicant")[
        "16_nov_2026_attached_to_title"]


def test_missing_title_cannot_turn_record_date_into_printed_edition():
    p = Page("PREFETTURA DI REGGIO CALABRIA\n"
             "Ragione sociale 16/11/2026", None)
    for population in ("listed", "applicant"):
        assert not any(printed_title_date_flags(p, population).values())


def test_redacted_identifier_shape_privacy_prescreen_never_emits_values():
    examples = {
        "12345678901": "eleven_digit_shape",
        "RSSMRA85M01H501Z": "sixteen_character_shape_privacy_review",
        "12345678901 / RSSMRA85M01H501Z": "other_raw_shape_privacy_review",
        "": "blank",
        "  ": "blank",
    }
    for source_cell, expected in examples.items():
        result = source_identifier_shape(source_cell)
        assert result == expected
        assert source_cell.strip() not in result if source_cell.strip() else True
        assert set(result) <= set("abcdefghijklmnopqrstuvwxyz_")


def test_sixteen_character_shape_does_not_imply_legal_identity():
    # Only an aggregate physical-shape clue: not a personal-data approval,
    # nor evidence of a legal person, sole trader, or canonical identifier.
    assert source_identifier_shape("ABCDEFGHIJKLMNOP") == (
        "sixteen_character_shape_privacy_review")
    assert source_identifier_shape("1234567890123456") == (
        "sixteen_character_shape_privacy_review")
    assert source_identifier_shape("1234567890") == "other_raw_shape_privacy_review"
