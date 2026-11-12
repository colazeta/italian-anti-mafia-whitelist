from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from white_list_archive.normalisation.cosenza_qa import calendar_gate, review_gate, source_facts
from test_capture_rich_cosenza import synthetic_record


def test_source_uncertainty_remains_visible_without_legal_inference():
    facts = source_facts([synthetic_record()])
    assert facts['identifiers']['unparsed_rows'] == 1
    assert facts['source_status_counts'] == {'other_or_unknown':1}


def test_invalid_calendar_and_cross_name_identifier_are_counted():
    import json
    first = synthetic_record()
    first['identifiers_json'] = json.dumps([{'raw_value':'123','candidate_schemes':['IT_CF','IT_VAT']}])
    first['observed_listing_date'] = '31/02/2026'
    second = deepcopy(first); second['operator_name_normalised'] = 'DIFFERENT NAME'
    facts = source_facts([first,second])
    assert facts['dates']['invalid_calendar_dates'] == 2
    assert facts['identifiers']['cross_name_tokens'] == 1
    assert facts['identifiers']['ambiguous_scheme'] == 2


def test_unsigned_review_never_makes_semantics_ready():
    pins = {'capture_id':str(uuid4()),'parse_run_id':str(uuid4()),'snapshot_sha256':'a'*64}
    edition = str(uuid4())
    decision = dict(contract='edition-attribution-review-v1',**pins,edition_id=edition,
                    reviewer='reviewer',reviewed_at=datetime.now(timezone.utc).isoformat(),
                    evidence_reference='private:review-item',decision='accepted', identity_basis='document heading',
                    reference_date_basis='heading',population_scope_basis='both source populations reviewed',
                    sector_scope_basis='source scope reviewed')
    assert review_gate(None,pins=pins,edition_links=[])['status'] == 'blocked'
    assert review_gate(decision,pins=pins,edition_links=[])['status'] == 'blocked'
    assert review_gate(decision,pins=pins,edition_links=[(edition,'explicit','explicit')])['status'] == 'unknown'
    decision['snapshot_sha256'] = 'b'*64
    assert review_gate(decision,pins=pins,edition_links=[(edition,'explicit','explicit')])['reason'] == 'review_decision_input_mismatch'


def test_calendar_gate_does_not_claim_validation_without_dates():
    result = calendar_gate(source_facts([synthetic_record()]))
    assert result['status'] == 'unknown'
    assert result['numerator'] == result['denominator'] == 0
    assert calendar_gate({'dates':{'tokens':2,'invalid_calendar_dates':1}})['status'] == 'blocked'
    assert calendar_gate({'dates':{'tokens':2}})['status'] == 'ready'


def test_multiple_distinct_application_dates_require_source_fact_review():
    import json
    rows = []
    for i, values in enumerate((['01/01/2026'], ['01/01/2026', '02/01/2026'],
                                ['01/01/2026', '02/01/2026', '03/01/2026'],
                                ['01/01/2026', '02/01/2026', '03/01/2026', '04/01/2026']), 1):
        row = synthetic_record()
        row['row_ordinal'] = i
        row['application_date_field_raw'] = ' / '.join(values)
        row['application_dates_json'] = json.dumps([{'date': value, 'raw_value': value} for value in values])
        rows.append(row)
    dates = source_facts(rows)['dates']
    assert dates['multiple_distinct_application_date_rows'] == 3
    assert dates['max_distinct_application_dates_per_row'] == 4
    assert dates['tokens'] == 10
    assert dates['invalid_calendar_dates'] == 0
    assert 'edition_date' not in dates


def test_repeating_a_date_does_not_create_a_second_distinct_candidate():
    import json
    row = synthetic_record()
    row['application_dates_json'] = json.dumps([
        {'date': '01/01/2026', 'raw_value': '01/01/2026'},
        {'date': '01/01/2026', 'raw_value': '(01/01/2026)'}])
    dates = source_facts([row])['dates']
    assert dates['multiple_distinct_application_date_rows'] == 0
    assert dates['max_distinct_application_dates_per_row'] == 1
    assert dates['tokens'] == 2
