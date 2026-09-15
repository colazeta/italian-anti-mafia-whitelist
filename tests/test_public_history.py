"""History invariants; synthetic rows are fixtures, never released source facts."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest
from white_list_archive.publishing.public_history import (
    aggregate_registry, build_history, compare_releases, compare_rows,
    edition_id, empty_history, iso_date, merge_histories,
    validate_history, validate_history_registry, write_history,
)

ROOT = Path(__file__).resolve().parents[1]


def fixture_registry(day="2026-06-01", sha="a" * 64, statuses=("pending", "listed"), parser="1"):
    rows = []
    for i, status in enumerate(statuses, 1):
        rows.append(dict(record_locator=f"fixture:{day}:{i}", source_key="fixture-combined", authority_key="fixture", authority_name="Fixture Prefecture", register_key="fixture-ordinary", register_name="Fixture register", population_scope="listed_and_applicant", reference_date=day, name=f"Synthetic company {i}", identifiers=[f"{i:011d}"], identifier_field_raw=f"{i:011d}", requested_activities=["fixture"], source_status=status, source_row_ordinal=i, source_page_url="https://example.test/page", resource_url="https://example.test/document", capture_sha256=sha, parser_name="fixture_parser", parser_version=parser))
    return reconcile(rows)


def reconcile(rows):
    sources = {}
    for row in rows:
        key = (row['source_key'], row['reference_date'], row['capture_sha256'])
        sources[key] = dict(source_key=key[0], reference_date=key[1], sha256=key[2], document_checked_at="2026-09-15T12:00:00Z")
    return {"records": rows, "meta": {"record_count": len(rows), "source_count": len(sources), "authority_count": len({r['authority_key'] for r in rows}), "register_count": len({r['register_key'] for r in rows}), "authority_counts": dict(Counter(r['authority_key'] for r in rows)), "register_counts": dict(Counter(r['register_key'] for r in rows)), "status_counts": dict(Counter(r['source_status'] for r in rows)), "sources": list(sources.values())}}


def seed():
    return json.loads((ROOT / "data/history/public_history.json").read_text())


def test_frozen_cosenza_counts_and_evidence_reconcile():
    h = seed()
    validate_history(h)
    diff = next(c for c in h['comparisons'] if c['basis'] == 'frozen_observational_diff')
    e = {x['id']: x for x in h['editions']}
    assert (e[diff['before_id']]['total'], e[diff['after_id']]['total']) == (1327, 1334)
    assert (diff['added'], diff['disappeared'], diff['common'], diff['content_changed'], diff['status_changed']) == (21, 14, 1313, 66, 55)
    assert sum(diff['transition_counts'].values()) == 55
    assert all(x['evidence'] for x in e.values())


def test_repeating_an_edition_is_idempotent_but_keeps_new_checks():
    reg = fixture_registry()
    h = aggregate_registry(reg)
    assert merge_histories(h, h) == merge_histories(h)
    reg['meta']['sources'][0]['document_checked_at'] = '2026-09-16T12:00:00Z'
    joined = build_history(reg, h)
    assert len(joined['editions']) == 1 and len(joined['checks']) == 2
    assert not joined['comparisons']


def test_fingerprint_ignores_order_whitespace_and_physical_row_movement():
    a = fixture_registry()
    b = deepcopy(a)
    b['records'].reverse()
    b['records'][0]['name'] += '  '
    b['records'][0]['source_fields'] = {'physical_locator': 'p9:r200'}
    assert aggregate_registry(a)['editions'][0]['data_fingerprint'] == aggregate_registry(b)['editions'][0]['data_fingerprint']
    b['records'][0]['source_fields']['notes'] = ['A new source note']
    assert aggregate_registry(a)['editions'][0]['data_fingerprint'] != aggregate_registry(b)['editions'][0]['data_fingerprint']


def test_parser_revision_is_a_separate_version_not_an_overwrite():
    a = aggregate_registry(fixture_registry())
    b = aggregate_registry(fixture_registry(parser='2'))
    h = merge_histories(a, b)
    assert len(h['editions']) == 2
    assert len({e['document_sha256'] for e in h['editions']}) == 1
    assert not h['comparisons']


def test_safe_observational_deltas_reconcile():
    a = fixture_registry()
    b = fixture_registry('2026-07-01', 'b'*64, ('listed','listed','pending'))
    h = compare_releases(a,b)
    c = h['comparisons'][0]
    assert (c['added'],c['disappeared'],c['common'],c['content_changed'],c['status_changed']) == (1,0,2,1,1)
    assert c['transition_counts'] == {'pending->listed':1}
    assert len(merge_histories(h,h)['comparisons']) == 1


@pytest.mark.parametrize('problem', ['missing','duplicate','changed_bundle','name_conflict'])
def test_identity_uncertainty_never_becomes_complete_entrances_or_exits(problem):
    a = fixture_registry()['records']
    b = fixture_registry('2026-07-01','b'*64)['records']
    if problem == 'missing': b[0]['identifiers'] = []
    if problem == 'duplicate': b[1]['identifiers'] = b[0]['identifiers']
    if problem == 'changed_bundle': b[0]['identifiers'].append('99999999999')
    if problem == 'name_conflict': b[0]['name'] = 'Another legal identity'
    c = compare_rows(a,b,'a','b')
    assert c['added'] is None and c['disappeared'] is None
    assert c['unresolved_before'] + c['unresolved_after'] > 0


def test_different_registers_are_not_comparable():
    a = fixture_registry()
    b = fixture_registry('2026-07-01','b'*64)
    for r in b['records']: r['register_key'] = 'fixture-special'
    b = reconcile(b['records'])
    assert not compare_releases(a,b)['comparisons']


@pytest.mark.parametrize('raw', ['', '2026', '2026-02-30', '03/08/2026', '2026-08'])
def test_unknown_dates_do_not_use_capture_time(raw):
    assert iso_date(raw) is None
    h = aggregate_registry(fixture_registry(day=raw))
    assert h['editions'][0]['reference_date'] is None
    assert h['editions'][0]['reference_date_raw'] == raw


def test_partial_history_preserves_absent_scopes_and_does_not_zero_fill():
    old = seed()
    h = build_history(fixture_registry(),old)
    assert {e['authority_key'] for e in h['editions']} >= {'fixture','cosenza'}
    assert len(h['comparisons']) == len(old['comparisons'])


def test_conflicting_same_revision_fails_without_mutating_input():
    a = aggregate_registry(fixture_registry())
    saved = deepcopy(a)
    b = deepcopy(a)
    b['editions'][0]['data_fingerprint'] = 'c'*64
    with pytest.raises(ValueError,match='Same bytes/parser'):
        merge_histories(a,b)
    assert a == saved


@pytest.mark.parametrize('location',['edition','check','comparison'])
def test_closed_contract_rejects_unapproved_fields(location):
    h=seed()
    key={'edition':'editions','check':'checks','comparison':'comparisons'}[location]
    h[key][0]['private_information']='never publish'
    with pytest.raises(ValueError,match='[Uu]napproved|Invalid'):
        validate_history(h)


def test_current_registry_must_reconcile_and_full_rows_never_enter_history(tmp_path):
    reg=fixture_registry();h=build_history(reg,empty_history())
    validate_history_registry(h,reg)
    output=tmp_path/'history.json';write_history(output,h)
    content=output.read_text()
    assert 'Synthetic company' not in content and '00000000001' not in content
    h['editions'][0]['total'] += 1
    with pytest.raises(ValueError):validate_history_registry(h,reg)


def test_optional_previous_release_network_failure_is_explicit(monkeypatch,capsys):
    import white_list_archive.publishing.public_history as m
    def fail(*args,**kwargs):raise OSError('test-only unavailable')
    monkeypatch.setattr(m,'urlopen',fail)
    assert m.fetch_previous_public() == (None,None)
    assert 'no missing comparison is filled with zero' in capsys.readouterr().out


def test_js_history_invariants():
    subprocess.run(['node','--test','tests/public_history.test.cjs'],cwd=ROOT,check=True)
