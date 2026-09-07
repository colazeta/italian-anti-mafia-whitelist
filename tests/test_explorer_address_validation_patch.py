from pathlib import Path

import pytest

from white_list_archive.publishing.explorer_address_validation_patch import (
    REVIEW_FIELDS,
    patch_explorer,
)


def fixture_html() -> str:
    return """<!doctype html><html><head><style>.x{}</style></head><body>
<div class=\"menubar\"><button class=\"tab\" data-view=\"method\">Metodo</button></div>
<section class=\"view\" id=\"view-method\"></section>
<script>function section(t,b){return b}</script>
</body></html>"""


def payload():
    return {
        "schema_version": 1,
        "sample_fingerprint": "abc123",
        "sample_size": 1,
        "summary": {},
        "review_fields": list(REVIEW_FIELDS),
        "rows": [
            {
                "address_id": "00000000-0000-0000-0000-000000000001",
                "sample_position": 1,
                "review_stratum": "matched_civic_access",
                "source_address": "COSENZA Via Roma 1",
                "source_country_code": "IT",
                "normalised_address": "VIA ROMA 1, Cosenza, Italia",
                "street_name": "VIA ROMA",
                "house_number": "1",
                "locality": "Cosenza",
                "precision_code": "civic_access",
                "latitude": "39.3",
                "longitude": "16.2",
                "provider_name": "anncsu",
                "provider_version": "2026-08-03",
                "sampling_weight": "1",
                "source_occurrences": [],
            }
        ],
    }


def test_patch_adds_retro_validation_tab_and_embedded_review_state(tmp_path: Path):
    index = tmp_path / "index.html"
    index.write_text(fixture_html(), encoding="utf-8")
    patch_explorer(index, payload())
    html = index.read_text(encoding="utf-8")
    assert 'data-view="address-validation"' in html
    assert 'id="view-address-validation"' in html
    assert "window.__ADDRESS_VALIDATION__=" in html
    assert "matched_civic_access" in html
    assert "Esporta JSON" in html
    assert "Importa JSON" in html
    assert "localStorage" in html
    assert "Apri su OpenStreetMap" in html


def test_patch_refuses_double_application(tmp_path: Path):
    index = tmp_path / "index.html"
    index.write_text(fixture_html(), encoding="utf-8")
    patch_explorer(index, payload())
    with pytest.raises(ValueError, match="already contains"):
        patch_explorer(index, payload())
