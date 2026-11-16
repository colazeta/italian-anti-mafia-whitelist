import json
from pathlib import Path

from white_list_archive.publishing.publication_handoff import _digest

ROOT = Path(__file__).resolve().parents[1]
PINNED = {
    "taranto-listed": {
        "sha256": "013cc91b1a62e353e77ab0e773299b6c0ed25c930d9d26d9bd62ec4613ed9396",
        "semantic_sha256": "80fd32841490c1c72845fb394c8fab796d95b3e6f481a51951824f0d0c29a19b",
        "records_sha256": "c7bc0802534ccfa65e9b01d46727af52362c5bf6b64d40ee15dadf114fc6d524",
        "count": 383, "statuses": {"listed": 183, "renewal_update_in_progress": 200},
        "parser": "taranto_html_listed",
    },
    "taranto-applicants": {
        "sha256": "c873e011a424e278f91a1bf80abec69282fc5ea53d310aa7118e49693c81c970",
        "semantic_sha256": "1b51bb0dda7e0e001435351e07ce60b11d982afd2cf5cdb07373034da2b2e033",
        "records_sha256": "534b016ae55363ae802d646c0c2da35cfe74e4f8b0f0695766f77bd1647c183c",
        "count": 226, "statuses": {"pending": 226}, "parser": "taranto_html_applicants",
    },
}


def test_taranto_exact_reviewed_pair_and_current_baseline_intent():
    config = json.loads((ROOT / "data/publication/multi_prefecture_pilot.json").read_text())
    selected = json.loads((ROOT / "data/publication/public_snapshot.json").read_text())
    intent = json.loads((ROOT / "data/publication/incremental_release_intent.json").read_text())
    sources = {s["source_key"]: s for s in config["sources"]}
    assert set(PINNED) <= set(sources)
    # Pin the original source-review decision independently of whichever
    # release the selector subsequently serves. Selector-only promotion must
    # not invalidate the historical Taranto evidence or manufacture a new intent.
    assert (ROOT / "docs/sources/taranto-publication-review-2026-11-06.md").is_file()
    taranto_intent_current = set(intent["changes"]) == set(PINNED)
    if taranto_intent_current:
        assert intent["baseline_manifest_sha256"] == "892a2825c45f373c2702715ca23469c0e56901166dc3dcab3fcc7c97fa4166e3"
        assert intent["source_config_sha256"] == _digest(config)
        assert intent["review_document"] == "docs/sources/taranto-publication-review-2026-11-06.md"
        assert (ROOT / intent["review_document"]).is_file()
        if selected["release_tag"] == "public-data-43736522316-1":
            assert intent["baseline_manifest_sha256"] == _digest(selected)
    for key, pin in PINNED.items():
        source = sources[key]
        assert source["sha256"] == pin["sha256"]
        assert source["semantic_sha256"] == pin["semantic_sha256"]
        assert source["parser"] == pin["parser"]
        assert source["expected_source_rows"] == pin["count"]
        assert source["reference_date"] == source["last_source_update"] == "2026-11-06"
        assert source["approval_mode"] == "semantic_sha256"
        if taranto_intent_current:
            assert intent["changes"][key] == {
                "count": pin["count"], "statuses": pin["statuses"],
                "reference_date": "2026-11-06", "sha256": pin["sha256"],
                "parser": pin["parser"], "records_sha256": pin["records_sha256"],
            }
    preserved = json.loads((ROOT / "data/publication/preserved_public_sources.json").read_text())
    assert len(preserved) == len(set(preserved))
    if taranto_intent_current and selected["release_tag"] == "public-data-43736522316-1":
        # Before promotion, only these two reviewed source keys may be rebuilt.
        assert set(preserved) == set(sources) - set(PINNED)
    elif taranto_intent_current:
        # The selector proposal modifies only selector/monitoring. The subsequent
        # preservation enrolment may not yet have been committed.
        assert set(preserved) in (set(sources) - set(PINNED), set(sources))
    else:
        # After a later source review, Taranto has to be preserved explicitly.
        assert set(PINNED) <= set(preserved)
    assert {"como-listed", "como-applicants", "biella-listed", "biella-applicants"} <= set(preserved)


def test_taranto_robot_catalog_is_regenerated_exactly_from_reviewed_sources():
    from white_list_archive.acquisition.prefecture_robots import generate_catalog
    catalog = json.loads((ROOT / "data/source_registry/prefecture_robots.json").read_text())
    assert catalog == generate_catalog(ROOT)
    robot = next(r for r in catalog["robots"] if r["authority_key"] == "taranto")
    assert {s["source_key"]: s["approved_sha256"] for s in robot["sources"]} == {
        k: v["sha256"] for k, v in PINNED.items()
    }
