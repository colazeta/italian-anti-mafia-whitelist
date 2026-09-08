"""Validate the complete allow-listed Pages artifact before upload."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from white_list_archive.publishing.public_contract import validate_registry
from white_list_archive.publishing.public_national_registry import write_registry_csv, write_prefecture_csv

PUBLIC_FILES = {"index.html", "styles.css", "app.js", "summary.js", "data/site.json", "data/registry.json", "data/registry.csv", "data/prefectures.json", "data/prefectures.csv"}


def validate_artifact(root: Path) -> None:
    files = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    if files != PUBLIC_FILES or any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError(f"Public artifact file allow-list mismatch: {files ^ PUBLIC_FILES}")
    site = json.loads((root / "data/site.json").read_text())
    if set(site) != {"meta", "publication", "history", "audit"}:
        raise ValueError("Unapproved site metadata")
    allowed_site = {
        "meta": {"title", "classification", "public_contract_version", "disclaimer"},
        "publication": {"principle", "registry_default_status", "geography_policy", "registry_fields", "interpretation"},
        "audit": {"repository_url", "explorer_source_url", "parser_url", "validation_url", "architecture_url", "issues_url"},
    }
    for key, allowed in allowed_site.items():
        if site[key].keys() - allowed:
            raise ValueError(f"Unapproved site {key}")
    for row in site["history"]:
        if set(row) != {"date", "page_url", "origin"}:
            raise ValueError("Unapproved history fields")
    registry = json.loads((root / "data/registry.json").read_text())
    validate_registry(registry)
    prefectures = json.loads((root / "data/prefectures.json").read_text())
    if set(prefectures) != {"meta", "prefectures"}:
        raise ValueError("Unapproved directory payload")
    allowed_directory = {"authority_key", "jurisdiction_name", "official_white_list_urls", "national_index_title", "mapping_status", "mapped", "published", "series_count", "publication_models", "published_registers", "last_project_check", "last_source_update", "last_source_update_basis", "verified_primary_page"}
    rows = prefectures["prefectures"]
    if any(set(row) != allowed_directory for row in rows):
        raise ValueError("Unapproved directory fields")
    if len(rows) != len({r["authority_key"] for r in rows}) or len(rows) != prefectures["meta"]["authority_count"]:
        raise ValueError("Prefecture denominator mismatch")
    if {r["authority_key"] for r in rows if r["published"]} != set(registry["meta"]["authority_counts"]):
        raise ValueError("Published coverage and registry disagree")
    with TemporaryDirectory() as temp:
        for name, writer, payload in (("registry", write_registry_csv, registry), ("prefectures", write_prefecture_csv, prefectures)):
            expected = Path(temp) / f"{name}.csv"
            writer(payload, expected)
            if expected.read_bytes() != (root / "data" / f"{name}.csv").read_bytes():
                raise ValueError(f"Public {name} CSV does not match the approved JSON fields")
    forbidden = ("legal_entity_id", "address_id", "review_notes", "reviewed_at", "source_occurrences", "table_catalog", "manual_validation", "curation_annotations")
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".csv", ".html"}:
            content = path.read_text().casefold()
            if any(token in content for token in forbidden):
                raise ValueError(f"Internal material in {path.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    validate_artifact(args.root)
    print("Complete public artifact allow-list and aggregates verified.")


if __name__ == "__main__":
    main()
