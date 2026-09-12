from __future__ import annotations

from pathlib import Path

PARSER = Path("src/white_list_archive/parsers/brescia_openxml.py")

OLD_COUNTS = '''_EXPECTED_SECTION_ROW_COUNTS = {
    "I": 416,
    "II": 218,
    "III": 567,
    "IV": 436,
    "V": 582,
    "VI": 457,
    "VII": 68,
    "VIII": 35,
    "IX": 79,
    "X": 450,
}
'''
NEW_COUNTS = '''_EXPECTED_SECTION_ROW_COUNTS = {
    "I": 426,
    "II": 222,
    "III": 576,
    "IV": 448,
    "V": 598,
    "VI": 467,
    "VII": 70,
    "VIII": 35,
    "IX": 81,
    "X": 457,
}
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PARSER.read_text(encoding="utf-8")
    text = replace_once(text, OLD_COUNTS, NEW_COUNTS, "section row counts")
    text = replace_once(
        text,
        "_EXPECTED_LISTED_SECTOR_ROWS = 3308\n",
        "_EXPECTED_LISTED_SECTOR_ROWS = 3380\n",
        "listed sector-row total",
    )
    PARSER.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
