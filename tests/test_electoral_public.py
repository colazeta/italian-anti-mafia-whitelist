import json
import pytest
from pathlib import Path
from runpy import run_path

from white_list_archive.publishing.public_artifact import validate_electoral


ROOT = Path(__file__).resolve().parents[1]
combine_ballots = run_path(str(ROOT / "scripts/elections/build_electoral_data.py"))["combine_ballots"]


def test_electoral_payload_has_one_row_per_election():
    payload = json.loads((ROOT / "public-site/data/electoral.json").read_text(encoding="utf-8"))
    validate_electoral(payload)
    events = {event["id"]: event for event in payload["events"]}
    assert len(events) == 4
    assert len(events["eu-2024"]["provinces"]) == 107
    assert sum(row["status"] == "complete_in_extract" for row in events["eu-2024"]["provinces"]) == 101
    assert len(events["politiche-2022"]["provinces"]) == 106
    assert sum(row["status"] == "complete_in_extract" for row in events["politiche-2022"]["provinces"]) == 97
    assert len(events["referendum-2022"]["provinces"]) == 107
    assert sum(row["status"] == "complete_in_extract" for row in events["referendum-2022"]["provinces"]) == 107
    assert events["referendum-2020"]["poll_close_local"] == "2020-09-21T15:00:00"
    overall = payload["overall"]["provinces"]
    assert len(overall) == 107
    assert sum(row["status"] == "complete_in_all" for row in overall) == 94
    assert all(row["events_complete"] == 4 for row in overall if row["status"] == "complete_in_all")


def test_incomplete_territories_do_not_receive_a_rank_metric():
    payload = json.loads((ROOT / "public-site/data/electoral.json").read_text(encoding="utf-8"))
    for event in payload["events"]:
        for row in event["provinces"]:
            if row["status"] != "complete_in_extract":
                assert "weighted_mean_hours" not in row
                assert "last_hours" not in row


def test_ballots_count_sections_once_and_require_all_to_complete():
    a = [dict(cod_prov='1', desc_prov='ALFA', cod_com='10', sz_tot='3', sz_perv='3', dt_agg='20220926010000'),
         dict(cod_prov='1', desc_prov='ALFA', cod_com='11', sz_tot='2', sz_perv='2', dt_agg='20220926010000')]
    b = [dict(cod_prov='1', desc_prov='ALFA', cod_com='10', sz_tot='3', sz_perv='3', dt_agg='20220926030000')]
    rows = combine_ballots([a, b], lambda r: r['cod_com'])
    assert rows[0]['sz_tot'] == '3' and rows[0]['dt_agg'] == '20220926030000'
    assert rows[1]['sz_tot'] == '2' and rows[1]['sz_perv'] == '' and not rows[1]['dt_agg']


@pytest.mark.parametrize('defect', ['score', 'hours', 'coverage', 'infinity', 'hash'])
def test_electoral_validator_rejects_plausible_but_inconsistent_values(defect):
    data = json.loads((ROOT / 'public-site/data/electoral.json').read_text())
    row = next(r for r in data['overall']['provinces'] if r['status'] == 'complete_in_all')
    if defect == 'score':
        row['scores']['last_hours'] += .001
    elif defect == 'hours':
        row['event_hours']['eu-2024']['last_hours'] += .001
    elif defect == 'coverage':
        next(r for r in data['overall']['provinces'] if r['status'] == 'incomplete_coverage')['events_complete'] = 0
    elif defect == 'infinity':
        data['events'][0]['provinces'][0]['last_hours'] = float('inf')
    else:
        data['events'][0]['provenance']['sha256']['municipal'] = 'invalid'
    with pytest.raises(ValueError):
        validate_electoral(data)
