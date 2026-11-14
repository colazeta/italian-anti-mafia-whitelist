"""Public robot directory: configuration and selected release metadata, no company rows."""
import json
import re
from pathlib import Path

from white_list_archive.acquisition.prefecture_robots import CATALOG

ROOT = Path(__file__).resolve().parents[3]
MONITORING = ROOT / "data/monitoring/national_coverage.json"
PUBLIC_SNAPSHOT = ROOT / "data/publication/public_snapshot.json"


def _selected_public_sources():
    """Only the exact SHA-pinned selected release may define the publication baseline."""
    ledger = json.loads(MONITORING.read_text())
    manifest = json.loads(PUBLIC_SNAPSHOT.read_text())
    selected = ledger.get("selected_publication", {})
    selected_registry = manifest.get("files", {}).get("registry.json", {})
    if (selected.get("release_tag") != manifest.get("release_tag")
            or selected.get("registry_sha256") != selected_registry.get("sha256")):
        raise ValueError("Robot publication comparison lacks a matching selected release ledger")
    sources_by_authority = {}
    seen_keys = set()
    for row in ledger["prefectures"]:
        authority = row["authority_key"]
        if authority in sources_by_authority:
            raise ValueError("Duplicate authority in selected release ledger")
        sources = row.get("selected_public_sources") or []
        projected = []
        for source in sources:
            fields = ("source_key", "register_key", "population_scope", "reference_date", "sha256")
            item = {key: source[key] for key in fields}
            if item["source_key"] in seen_keys or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
                raise ValueError("Unusable selected source identity")
            if not re.fullmatch(r"20\d\d-\d\d-\d\d", item["reference_date"]):
                raise ValueError("Unusable selected source date")
            seen_keys.add(item["source_key"])
            projected.append(item)
        if (max((item["reference_date"] for item in projected), default=None)
                != row.get("latest_selected_public_reference_date")):
            raise ValueError("Selected source date and authority summary disagree")
        sources_by_authority[authority] = sorted(projected, key=lambda item: item["source_key"])
    if (len(seen_keys) != selected.get("source_count")
            or sum(bool(rows) for rows in sources_by_authority.values()) != selected.get("authority_count")):
        raise ValueError("Selected source counts do not reconcile")
    return sources_by_authority


def public_directory(catalog):
    selected = _selected_public_sources()
    if {r["authority_key"] for r in catalog["robots"]} != set(selected):
        raise ValueError("Selected release ledger does not match 106 robot authorities")
    return {"schema_version": 1, "schedule": "daily", "robots": [
        {"authority_key": r["authority_key"], "name": r["name"], "region": r["region"],
         "landing_pages": r["landing_pages"], "reviewed_resources": len(r["sources"]),
         "population_mapping_reviewed": r["population_mapping_reviewed"],
         "selected_public_sources": selected[r["authority_key"]]}
        for r in catalog["robots"]]}


def validate_public_robots(data):
    expected = public_directory(json.loads(CATALOG.read_text()))
    if data != expected:
        raise ValueError("Public robot directory differs from reviewed robot and release configuration")


if __name__ == "__main__":
    Path("public-site/data/robots.json").write_text(
        json.dumps(public_directory(json.loads(CATALOG.read_text())), ensure_ascii=False, separators=(",", ":")) + "\n"
    )
