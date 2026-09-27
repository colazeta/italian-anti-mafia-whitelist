"""Validate the complete allow-listed Pages artifact before upload."""
from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from white_list_archive.publishing.public_history import validate_history_registry
from white_list_archive.publishing.public_contract import validate_registry
from white_list_archive.publishing.public_national_registry import write_registry_csv, write_prefecture_csv

PUBLIC_FILES = {"index.html", "styles.css", "app.js", "summary.js", "history.js", "electoral.js", "data/electoral.json", "data/history.json", "data/site.json", "data/registry.json", "data/registry.csv", "data/prefectures.json", "data/prefectures.csv"}


def validate_electoral(data: dict) -> None:
    if set(data) != {"schema_version", "method", "events", "overall"} or data["schema_version"] != 2:
        raise ValueError("Unapproved electoral payload")
    expected = {"eu-2024", "politiche-2022", "referendum-2022", "referendum-2020", "referendum-2026"}
    if {e.get("id") for e in data["events"]} != expected or len(data["events"]) != len(expected):
        raise ValueError("Electoral event coverage mismatch")
    for event in data["events"]:
        if set(event) != {"id", "label", "kind", "poll_close_local", "provenance", "note", "provinces"}:
            raise ValueError("Unapproved electoral event fields")
        if set(event["provenance"]) != {"repository", "sha256"} or not event["provenance"]["repository"].startswith("https://github.com/ondata/"):
            raise ValueError("Unapproved electoral provenance")
        if not event["provenance"]["sha256"] or any(not re.fullmatch(r"[a-f0-9]{64}", digest) for digest in event["provenance"]["sha256"].values()):
            raise ValueError("Invalid electoral source hash")
        rows = event["provinces"]
        if not rows or len({r["province_code"] for r in rows}) != len(rows):
            raise ValueError("Electoral province duplication or missing rows")
        base = {"province_code", "province", "rows", "municipalities", "sections_expected", "sections_reported", "status"}
        metrics = {"last_update_local", "last_hours", "weighted_mean_hours", "weighted_p90_hours"}
        for row in rows:
            if any(type(row[key]) is not int or row[key] <= 0 for key in ("rows", "municipalities", "sections_expected")) or row["municipalities"] > row["rows"]:
                raise ValueError("Invalid electoral population counts")
            reported = row["sections_reported"]
            if reported is not None and (type(reported) is not int or not 0 <= reported <= row["sections_expected"]):
                raise ValueError("Invalid electoral section count")
            if row["status"] == "complete_in_extract":
                if set(row) != base | metrics or row["sections_reported"] != row["sections_expected"]:
                    raise ValueError("Invalid complete electoral row")
                if not all(type(row[k]) in (int, float) and math.isfinite(row[k]) for k in metrics - {"last_update_local"}):
                    raise ValueError("Non-finite electoral time")
                if not (0 <= row["weighted_mean_hours"] <= row["last_hours"] and
                        0 <= row["weighted_p90_hours"] <= row["last_hours"]):
                    raise ValueError("Invalid electoral time ordering")
                elapsed = (datetime.fromisoformat(row["last_update_local"]) - datetime.fromisoformat(event["poll_close_local"])).total_seconds() / 3600
                if abs(elapsed - row["last_hours"]) > .000501:
                    raise ValueError("Electoral timestamp and hours disagree")
            elif row["status"] == "incomplete_or_invalid":
                if set(row) != base:
                    raise ValueError("Unapproved incomplete electoral row")
            else:
                raise ValueError("Unknown electoral row status")
    overall = data["overall"]
    if set(overall) != {"method", "elections_required", "provinces"} or overall["elections_required"] != len(expected):
        raise ValueError("Unapproved overall ranking")
    names = {row["province"] for row in overall["provinces"]}
    if len(names) != len(overall["provinces"]) or len(names) != 111:
        raise ValueError("Overall province coverage mismatch")
    metrics = {"weighted_mean_hours", "weighted_p90_hours", "last_hours"}
    for row in overall["provinces"]:
        if row["status"] == "complete_in_all":
            if set(row) != {"province", "events_complete", "status", "scores", "event_hours"} or row["events_complete"] != len(expected):
                raise ValueError("Invalid overall ranked row")
            if set(row["scores"]) != metrics or set(row["event_hours"]) != expected:
                raise ValueError("Invalid overall score dimensions")
            if any(not (0 <= score <= 100) for score in row["scores"].values()) or any(set(hours) != metrics for hours in row["event_hours"].values()):
                raise ValueError("Invalid overall scores")
        elif row["status"] == "incomplete_coverage":
            if set(row) != {"province", "events_complete", "status"} or not (0 <= row["events_complete"] < len(expected)):
                raise ValueError("Invalid overall incomplete row")
        else:
            raise ValueError("Unknown overall row status")
    # Reconcile every score and exclusion with the election rows. Do not trust
    # the precomputed overall table merely because its values fall in [0, 100].
    def key(name):
        return re.sub('[^A-Z]', '', unicodedata.normalize('NFKD', name.upper()))
    by_event = {e['id']: {key(r['province']): r for r in e['provinces']} for e in data['events']}
    if any(len(by_event[e['id']]) != len(e['provinces']) for e in data['events']):
        raise ValueError("Ambiguous electoral province name")
    expected_names = set().union(*(set(rows) for rows in by_event.values()))
    if {key(r['province']) for r in overall['provinces']} != expected_names:
        raise ValueError("Overall provinces do not match elections")
    for row in overall['provinces']:
        name = key(row['province'])
        available = [rows[name] for rows in by_event.values() if name in rows and rows[name]['status'] == 'complete_in_extract']
        if row['events_complete'] != len(available):
            raise ValueError("Overall completion count mismatch")
        if len(available) != len(expected):
            continue
        for metric in metrics:
            percentiles = []
            for event_id, rows in by_event.items():
                value = rows[name][metric]
                if row['event_hours'][event_id][metric] != value:
                    raise ValueError("Overall event hours mismatch")
                values = [r[metric] for r in rows.values() if r['status'] == 'complete_in_extract']
                if len(values) < 2:
                    raise ValueError("Insufficient provinces for electoral ranking")
                percentile = 100 * (sum(v < value for v in values) + (sum(v == value for v in values) - 1) / 2) / (len(values) - 1)
                percentiles.append(round(percentile, 6))
            score = round(sum(percentiles) / len(percentiles), 3)
            if row['scores'][metric] != score:
                raise ValueError("Overall score mismatch")


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
    history = json.loads((root / "data/history.json").read_text(encoding="utf-8"))
    validate_history_registry(history, registry)
    validate_electoral(json.loads((root / "data/electoral.json").read_text(encoding="utf-8")))
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
