from __future__ import annotations

from pathlib import Path

PARSER = Path("src/white_list_archive/parsers/brescia_openxml.py")
TESTS = Path("tests/test_brescia_parser_semantics.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_parser() -> None:
    text = PARSER.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import re\n",
        "import hashlib\nimport json\nimport re\n",
        "parser imports",
    )
    text = replace_once(
        text,
        "_EXPECTED_LISTED_SECTOR_ROWS = 3308\n",
        "_EXPECTED_LISTED_SECTOR_ROWS = 3308\n"
        "_EXPECTED_LISTED_NAME_SHIFT_ROWS = 72\n"
        "_EXPECTED_LISTED_NAME_SHIFT_SHA256 = \"f6d55887c3f4e45e46217447100e5e896e509c5daa50f603a9ab48a53c5a41c2\"\n",
        "name-shift constants",
    )
    text = replace_once(
        text,
        "_REVIEWED_APPLICANT_MALFORMED_DATES = frozenset({\"25/092025\"})\n\n\n"
        "def _validate_cfg",
        "_REVIEWED_APPLICANT_MALFORMED_DATES = frozenset({\"25/092025\"})\n\n\n"
        "def _name_shift_sha256(signatures: list[list[Any]]) -> str:\n"
        "    payload = json.dumps(signatures, ensure_ascii=False, separators=(\",\", \":\")).encode(\"utf-8\")\n"
        "    return hashlib.sha256(payload).hexdigest()\n\n\n"
        "def _validate_cfg",
        "name-shift digest helper",
    )
    text = replace_once(
        text,
        "    rows: list[dict[str, Any]] = []\n    structural_shift_rows = 0\n",
        "    rows: list[dict[str, Any]] = []\n"
        "    structural_shift_rows = 0\n"
        "    name_shift_signatures: list[list[Any]] = []\n",
        "name-shift accumulator",
    )
    text = replace_once(
        text,
        "        if not name:\n"
        "            raise RuntimeError(f\"Brescia nonempty listed row without company name at row {source_row}: {values!r}\")\n",
        "        if not name:\n"
        "            fallback_name = values[0] if values else \"\"\n"
        "            signature = [\n"
        "                source_row,\n"
        "                section,\n"
        "                fallback_name,\n"
        "                office,\n"
        "                identifier_raw,\n"
        "                _clean(listing_value),\n"
        "                _clean(expiry_value),\n"
        "                update_raw,\n"
        "            ]\n"
        "            # The byte-pinned 10 September workbook contains a finite audited\n"
        "            # class of rows where the company name is in column A while the\n"
        "            # labelled name column C is blank. Accept only that exact source\n"
        "            # fingerprint; any added, removed or changed row fails below.\n"
        "            if not fallback_name or name_i != 2 or (len(values) > 1 and values[1]):\n"
        "                raise RuntimeError(\n"
        "                    f\"Brescia unreviewed listed-name layout at row {source_row}: {values!r}\"\n"
        "                )\n"
        "            name_shift_signatures.append(signature)\n"
        "            name = fallback_name\n",
        "name-shift row handling",
    )
    text = replace_once(
        text,
        "            and _clean(listing_value) == \"2026-09-17\"\n",
        "            and _clean(listing_value) in {\"2026-09-17\", \"2026-09-17 00:00:00\"}\n",
        "ADMG exact XLSX date representation",
    )
    text = replace_once(
        text,
        "    if section_headers != Counter({section: 1 for section in _EXPECTED_SECTIONS}):\n",
        "    name_shift_sha256 = _name_shift_sha256(name_shift_signatures)\n"
        "    if len(name_shift_signatures) != _EXPECTED_LISTED_NAME_SHIFT_ROWS:\n"
        "        raise RuntimeError(\n"
        "            f\"Brescia reviewed listed-name shift count drift: {len(name_shift_signatures)} \"\n"
        "            f\"!= {_EXPECTED_LISTED_NAME_SHIFT_ROWS}\"\n"
        "        )\n"
        "    if name_shift_sha256 != _EXPECTED_LISTED_NAME_SHIFT_SHA256:\n"
        "        raise RuntimeError(\n"
        "            f\"Brescia reviewed listed-name shift fingerprint drift: {name_shift_sha256} \"\n"
        "            f\"!= {_EXPECTED_LISTED_NAME_SHIFT_SHA256}\"\n"
        "        )\n"
        "    if section_headers != Counter({section: 1 for section in _EXPECTED_SECTIONS}):\n",
        "name-shift fail-closed validation",
    )
    PARSER.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    for roman, rows in by_section.items():\n"
        "        _append_section(ws, roman, rows)\n"
        "    workbook.save(path)\n\n"
        "    section_counts = {roman: len(rows) for roman, rows in by_section.items()}\n",
        "    for roman, rows in by_section.items():\n"
        "        _append_section(ws, roman, rows)\n"
        "    # Reproduce one audited source layout anomaly: the company name moves\n"
        "    # from labelled column C to column A while the other semantic columns stay put.\n"
        "    ws.cell(row=4, column=1).value = \"UNICA I SRL\"\n"
        "    ws.cell(row=4, column=3).value = None\n"
        "    workbook.save(path)\n\n"
        "    section_counts = {roman: len(rows) for roman, rows in by_section.items()}\n",
        "fixture name shift",
    )
    text = replace_once(
        text,
        "    monkeypatch.setattr(bs, \"_EXPECTED_LISTED_SECTOR_ROWS\", sum(section_counts.values()))\n"
        "    monkeypatch.setattr(bs, \"_EXPECTED_PEER_RESOLVED_DATE_ROWS\", 0)\n",
        "    monkeypatch.setattr(bs, \"_EXPECTED_LISTED_SECTOR_ROWS\", sum(section_counts.values()))\n"
        "    expected_shift = [[4, \"I\", \"UNICA I SRL\", \"Brescia via I\", \"00000000001\", \"2026-01-01 00:00:00\", \"2027-01-01 00:00:00\", \"\"]]\n"
        "    monkeypatch.setattr(bs, \"_EXPECTED_LISTED_NAME_SHIFT_ROWS\", 1)\n"
        "    monkeypatch.setattr(bs, \"_EXPECTED_LISTED_NAME_SHIFT_SHA256\", bs._name_shift_sha256(expected_shift))\n"
        "    monkeypatch.setattr(bs, \"_EXPECTED_PEER_RESOLVED_DATE_ROWS\", 0)\n",
        "fixture expected shift fingerprint",
    )
    text = replace_once(
        text,
        "    monkeypatch.setattr(bs, \"_EXPECTED_LISTED_SECTOR_ROWS\", sum(len(rows) for rows in by_section.values()))\n\n"
        "    try:\n",
        "    monkeypatch.setattr(bs, \"_EXPECTED_LISTED_SECTOR_ROWS\", sum(len(rows) for rows in by_section.values()))\n"
        "    monkeypatch.setattr(bs, \"_EXPECTED_LISTED_NAME_SHIFT_ROWS\", 0)\n"
        "    monkeypatch.setattr(bs, \"_EXPECTED_LISTED_NAME_SHIFT_SHA256\", bs._name_shift_sha256([]))\n\n"
        "    try:\n",
        "no-shift fail-closed fixture",
    )
    TESTS.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    patch_parser()
    patch_tests()
