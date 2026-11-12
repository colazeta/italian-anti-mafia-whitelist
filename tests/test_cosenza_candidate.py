from copy import deepcopy
import json
from uuid import uuid4

import pytest

from test_capture_rich_cosenza import synthetic_record
from white_list_archive.normalisation.cosenza_candidate import canonical, plan_records
from white_list_archive.persistence.capture_rich_cosenza import validate_records


def planned(rows,**overrides):
    pins=dict(capture_id='9e769f09-3d3c-5d2a-b0f7-1b53ee5895c0',parse_run_id=str(uuid4()),
              source_sha256='a'*64,snapshot_sha256=validate_records(rows,len(rows)),
              source_revision='b'*40,planner_revision='c'*40)
    pins.update(overrides)
    return plan_records(rows,**pins)


def test_private_candidate_is_deterministic_and_preserves_source_ambiguity():
    row=synthetic_record()
    row['identifiers_json']=json.dumps([{'raw_value':'123','candidate_schemes':['IT_CF','IT_VAT']}])
    pins={'parse_run_id':str(uuid4())}
    first=planned([row],**pins)
    assert canonical(first)==canonical(planned([deepcopy(row)],**pins))
    candidate=first['private_payload']['rows'][0]
    assert candidate['canonical_entity_id'] is None
    assert candidate['canonical_legal_status'] is None
    assert candidate['edition_approval'] is None
    assert candidate['source_facts']['identifier_candidates'][0]['candidate_schemes']==['IT_CF','IT_VAT']
    assert 'Synthetic' not in json.dumps(first['safe_summary'])


def test_impossible_dates_retained_and_not_coerced():
    row=synthetic_record()
    row['application_dates_json']=json.dumps([{'date':'31/02/2026','raw_value':'31/02/2026'}])
    result=planned([row])
    fact=result['private_payload']['rows'][0]['source_facts']['application_date_candidates'][0]
    assert fact['calendar_date'] is None
    assert fact['source_value']['raw_value']=='31/02/2026'
    assert result['safe_summary']['issue_counts']['invalid_application_dates']==1


def test_pinned_snapshot_or_code_mismatch_fails_closed():
    with pytest.raises(ValueError,match='snapshot'):
        planned([synthetic_record()],snapshot_sha256='d'*64)
    with pytest.raises(ValueError,match='revisions'):
        planned([synthetic_record()],planner_revision='main')


def test_planner_does_not_turn_expiry_or_cancellation_into_legal_status():
    row=synthetic_record();row['observed_expiry_date']='01/01/2000'
    row['outcome_raw']='Cancellazione';row['source_status']='cancellation_related'
    row['outcome_json']=json.dumps({'status':'cancellation_related'})
    result=planned([row])
    assert result['private_payload']['rows'][0]['canonical_legal_status'] is None
    assert result['safe_summary']['canonical_execution_ready'] is False


def test_observed_dates_are_calendar_candidates_not_legal_effective_dates():
    row=synthetic_record()
    row['observed_listing_date']='28/06/2026'
    row['observed_expiry_date']='31/02/2027'
    result=planned([row])
    facts=result['private_payload']['rows'][0]['source_facts']
    assert facts['observed_listing_date_raw']=='28/06/2026'
    assert facts['observed_listing_date_calendar_candidate']=='2026-06-28'
    assert facts['observed_expiry_date_raw']=='31/02/2027'
    assert facts['observed_expiry_date_calendar_candidate'] is None
    assert result['safe_summary']['issue_counts']['invalid_observed_expiry_date']==1
    assert result['private_payload']['rows'][0]['canonical_legal_status'] is None


def test_multiple_application_dates_remain_distinct_private_candidates():
    row = synthetic_record()
    row['application_date_field_raw'] = '01/02/2026 (03/04/2026)'
    row['application_dates_json'] = json.dumps([
        {'date':'01/02/2026','raw_value':'01/02/2026','parenthesized':False},
        {'date':'03/04/2026','raw_value':'(03/04/2026)','parenthesized':True}])
    result = planned([row])
    facts = result['private_payload']['rows'][0]['source_facts']
    assert facts['application_date_field_raw'] == row['application_date_field_raw']
    assert [d['calendar_date'] for d in facts['application_date_candidates']] == [
        '2026-02-01','2026-04-03']
    assert facts['application_date_candidates'][1]['source_value']['parenthesized'] is True
    assert result['private_payload']['rows'][0]['edition_approval'] is None
    assert result['safe_summary']['semantic_execution_ready'] is False
