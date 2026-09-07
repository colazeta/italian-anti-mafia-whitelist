import json
from pathlib import Path

from white_list_archive.publishing.explorer_audit_patch import patch_explorer
from white_list_archive.publishing.table_bundle import _json_safe


def test_explorer_audit_patch_embeds_table_and_source_evidence(tmp_path: Path):
    index = tmp_path / "index.html"
    index.write_text(
        """<!doctype html><html><body>
        <div id="view-structure"><table class="tree"><thead><tr><th>Oggetto</th></tr></thead><tbody><tr><td>LegalEntity</td></tr></tbody></table></div>
        <div id="view-provenance"></div>
        <aside id="detail"><span id="detail-title"></span><div id="detail-body"></div></aside>
        <script>const D={model_population:{objects:[{object_code:'legal_entity'}]}};function openDetail(r){};function E(s){return String(s)}</script>
        </body></html>""",
        encoding="utf-8",
    )
    table_catalog = tmp_path / "table_catalog.json"
    table_catalog.write_text(
        json.dumps(
            {
                "preview_limit": 50,
                "objects": {
                    "legal_entity": {
                        "object_code": "legal_entity",
                        "label": "LegalEntity",
                        "table": "core.legal_entity",
                        "layer": "canonical",
                        "meaning": "entity",
                        "count": 1,
                        "columns": [{"name": "entity_code", "data_type": "text", "udt_name": "text"}],
                        "preview_limit": 50,
                        "preview_rows": [{"entity_code": "WLENT-1"}],
                        "csv_path": "tables/legal_entity.csv",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    source_evidence = tmp_path / "source_evidence.json"
    source_evidence.write_text(
        json.dumps(
            {
                "editions": {
                    "2026-08-03": {
                        "pdf_path": "source-documents/cosenza/2026-08-03.pdf",
                        "sha256": "abc123",
                        "page_count": 69,
                        "resource_url": "https://example.invalid/source.pdf",
                        "rows": {"1": {"page_start": 1}},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    patch_explorer(index, table_catalog, source_evidence)
    html = index.read_text(encoding="utf-8")

    assert "__AUDIT_DRILLDOWN_V1__" in html
    assert "core.legal_entity" in html
    assert "tables/legal_entity.csv" in html
    assert "source-documents/cosenza/2026-08-03.pdf" in html
    assert "Apri CSV completo" in html
    assert "Verifica indipendente:" in html


def test_json_safe_preserves_scalar_and_stringifies_other_objects():
    class Value:
        def __str__(self):
            return "range-like"

    assert _json_safe({"a": [1, Value()]}) == {"a": [1, "range-like"]}
