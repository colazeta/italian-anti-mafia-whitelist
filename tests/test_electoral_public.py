import json
from pathlib import Path

from white_list_archive.publishing.public_artifact import validate_electoral


ROOT = Path(__file__).resolve().parents[1]


def test_electoral_payload_is_complete_and_separate_by_ballot():
    payload = json.loads((ROOT / "public-site/data/electoral.json").read_text(encoding="utf-8"))
    validate_electoral(payload)
    events = {event["id"]: event for event in payload["events"]}
    assert len(events) == 9
    assert len(events["eu-2024"]["provinces"]) == 107
    assert sum(row["status"] == "complete_in_extract" for row in events["eu-2024"]["provinces"]) == 101
    assert len(events["senato-2022"]["provinces"]) == 104
    for number in range(1, 6):
        assert len(events[f"referendum-2022-{number}"]["provinces"]) == 107
    assert events["referendum-2020"]["poll_close_local"] == "2020-09-21T15:00:00"


def test_incomplete_territories_do_not_receive_a_rank_metric():
    payload = json.loads((ROOT / "public-site/data/electoral.json").read_text(encoding="utf-8"))
    for event in payload["events"]:
        for row in event["provinces"]:
            if row["status"] != "complete_in_extract":
                assert "weighted_mean_hours" not in row
                assert "last_hours" not in row
