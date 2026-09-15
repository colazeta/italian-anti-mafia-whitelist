from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "src/white_list_archive/parsers/roma_positioned.py"

text = PATH.read_text(encoding="utf-8")
replacements = {
    '_LISTED_PSEUDO_IDS = {"SEZIONE", "DI LAVORI", "2013) C.F./P.I."}':
        '_LISTED_PSEUDO_IDS = {"SEZIONE", "DI LAVORI", "2013)"}',
    '_APPLICANT_PSEUDO_IDS = {"SEZIONE", "NELL’ELENCO DEI C.F./P.I."}':
        '_APPLICANT_PSEUDO_IDS = {"SEZIONE", "NELL’ELENCO DEI"}',
    'if pseudo_total != Counter({"SEZIONE": 5, "DI LAVORI": 1, "2013) C.F./P.I.": 1}):':
        'if pseudo_total != Counter({"SEZIONE": 5, "DI LAVORI": 1, "2013)": 1, "C.F./P.I.": 1}):',
    'if pseudo_total != Counter({"SEZIONE": 5, "NELL’ELENCO DEI C.F./P.I.": 1}):':
        'if pseudo_total != Counter({"SEZIONE": 5, "NELL’ELENCO DEI": 1, "C.F./P.I.": 1}):',
    'if reviewed_header_note_overlaps != 1:':
        'if reviewed_header_note_overlaps != 0:',
}
for old, new in replacements.items():
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Roma reviewed geometry replacement drift for {old!r}: found {count}")
    text = text.replace(old, new, 1)
PATH.write_text(text, encoding="utf-8")
print("Applied reviewed Roma first-page header/legend geometry correction")
