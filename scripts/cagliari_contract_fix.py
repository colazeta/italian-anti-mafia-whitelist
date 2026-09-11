from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "src/white_list_archive/parsers/cagliari_tables.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one replacement target, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''            source_fields={
                "sections_raw": [f"sez.{section:02d}" for section in sections],
                "source_row_locators": group["locators"],
                "listing_date_raw_variants": [row["listing_raw"]],
                "expiry_date_raw_variants": [row["expiry_raw"]],
                "status_note_raw": row["note"],
            },
''',
        '''            source_fields={
                "sections": [f"Sezione {section}" for section in sections],
                "listing_date_raw_variants": [row["listing_raw"]],
                "expiry_date_raw_variants": [row["expiry_raw"]],
                "in_aggiornamento": row["note"] if row["status"] == "renewal_update_in_progress" else "",
            },
''',
        "listed public source_fields contract",
    )
    text = replace_once(
        text,
        '''            source_fields={
                "requested_sections_raw": row["requested_raw"],
                "application_date_raw": row["application_raw"],
                "outcome_raw": row["outcome"],
                "source_row_locator": f"p{row['page']}:t{row['table']}:r{row['row']}",
            },
''',
        '''            source_fields={
                "application_date_raw_variants": [row["application_raw"]],
                "requested_activities_source": row["requested_raw"],
            },
''',
        "applicant public source_fields contract",
    )
    PATH.write_text(text, encoding="utf-8")
    print("Cagliari parser source_fields aligned with the closed public contract")


if __name__ == "__main__":
    main()
