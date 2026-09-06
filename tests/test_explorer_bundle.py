from pathlib import Path

from white_list_archive.publishing.explorer_bundle import mask_identifier


def test_mask_identifier():
    assert mask_identifier("01234567890") == "012••••••90"


def test_explorer_template_has_payload_marker_and_source_observation_guardrail():
    text = Path("explorer/index.html").read_text(encoding="utf-8")
    assert "__DATA_PAYLOAD__" in text
    assert "source observations" in text.lower()
    assert "INTERNAL CHECKPOINT" in text
    assert "non ancora entità" in text.lower()


def test_internal_mode_requires_explicit_acknowledgement():
    text = Path("src/white_list_archive/publishing/explorer_bundle.py").read_text(encoding="utf-8")
    assert "--acknowledge-internal-row-data" in text
    assert "INTERNAL ROW-LEVEL PREVIEW" in text
    assert "--mode internal requires --acknowledge-internal-row-data" in text
