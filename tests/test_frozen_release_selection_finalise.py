from __future__ import annotations

import pytest

from white_list_archive.publishing.frozen_release_selection import (
    FrozenReleaseSelectionError,
    finalise_parser_revisions,
)


def test_finalise_parser_revisions_freezes_replay_output_and_rejects_drift():
    manifest = {
        "sources": [
            {
                "source_key": "alpha-listed",
                "parser_revision": "selection-preflight",
            }
        ]
    }
    registry = {
        "records": [
            {
                "source_key": "alpha-listed",
                "parser_name": "alpha_parser",
                "parser_version": "7",
            }
        ]
    }

    final = finalise_parser_revisions(manifest, registry)
    assert final["sources"][0]["parser_revision"] == "alpha_parser@7"

    registry["records"].append(
        {
            "source_key": "alpha-listed",
            "parser_name": "alpha_parser",
            "parser_version": "8",
        }
    )
    with pytest.raises(FrozenReleaseSelectionError, match="inconsistent parser revisions"):
        finalise_parser_revisions(manifest, registry)


def test_finalise_parser_revisions_requires_every_selected_source():
    manifest = {
        "sources": [
            {"source_key": "alpha-listed", "parser_revision": "selection-preflight"},
            {"source_key": "beta-applicants", "parser_revision": "selection-preflight"},
        ]
    }
    registry = {
        "records": [
            {
                "source_key": "alpha-listed",
                "parser_name": "alpha_parser",
                "parser_version": "7",
            }
        ]
    }

    with pytest.raises(FrozenReleaseSelectionError, match="did not produce every selected source"):
        finalise_parser_revisions(manifest, registry)
