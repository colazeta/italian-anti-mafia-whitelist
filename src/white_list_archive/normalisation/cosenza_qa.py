"""Read-only, aggregate readiness evidence for exactly pinned rich source inputs."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from uuid import UUID

from white_list_archive.acquisition.auto_transform import private_connection, read_snapshot_verified
from white_list_archive.persistence.capture_rich_cosenza import verify_rich_readback

REPORT_CONTRACT = 'cosenza-source-qa-v1'


def gate(status, numerator, denominator, reason):
    return dict(status=status, numerator=numerator, denominator=denominator, reason=reason)


def calendar_gate(facts):
    tokens = facts['dates'].get('tokens', 0)
    invalid = facts['dates'].get('invalid_calendar_dates', 0)
    return gate('unknown' if not tokens else ('blocked' if invalid else 'ready'),
                tokens-invalid, tokens, 'calendar_validation_only')


def source_facts(records):
    """Count uncertainty without turning names, dates or source outcomes into legal facts."""
    statuses = Counter()
    identifiers = Counter()
    dates = Counter()
    identifier_names = {}
    shapes = Counter()
    for row in records:
        statuses[row['source_status']] += 1
        for item in json.loads(row['identifiers_json']):
            value = item.get('raw_value', '')
            shapes[item.get('shape', 'undeclared')] += 1
            candidates = item.get('candidate_schemes', [])
            identifiers['tokens'] += 1
            identifiers['without_candidate_scheme'] += not bool(candidates)
            identifiers['ambiguous_scheme'] += len(candidates) != 1
            identifier_names.setdefault(value, set()).add(row['operator_name_normalised'])
        application_dates = json.loads(row['application_dates_json'])
        distinct_dates = {item.get('date') for item in application_dates if item.get('date')}
        # Source-cell multiplicity is a review signal, not evidence of separate procedures.
        dates['multiple_distinct_application_date_rows'] += len(distinct_dates) > 1
        dates['max_distinct_application_dates_per_row'] = max(
            dates['max_distinct_application_dates_per_row'], len(distinct_dates))
        for value in [d.get('date') for d in application_dates] + [
                row['observed_listing_date'], row['observed_expiry_date']]:
            if not value:
                continue
            dates['tokens'] += 1
            try:
                datetime.strptime(value, '%d/%m/%Y')
            except (ValueError, TypeError):
                dates['invalid_calendar_dates'] += 1
        dates['application_unparsed_rows'] += bool(row['application_date_field_raw'].strip()) and not bool(json.loads(row['application_dates_json']))
        identifiers['unparsed_rows'] += bool(row['identifier_field_raw'].strip()) and not bool(json.loads(row['identifiers_json']))
    identifiers['cross_name_tokens'] = sum(len(names) > 1 for names in identifier_names.values())
    return {'source_status_counts': dict(sorted(statuses.items())),
            'identifier_shape_counts':dict(sorted(shapes.items())),
            'identifiers': dict(identifiers), 'dates': dict(dates)}


def review_gate(decision, *, pins, edition_links):
    """Validate an external review claim, never authenticate or approve its contents.

    No caller may treat a syntactically valid JSON document as an approval.
    Independent reviewer authentication remains a mandatory external control.
    """
    if decision is None:
        return gate('blocked', 0, 1, 'reviewed_edition_attribution_not_supplied')
    required = {'contract', 'capture_id', 'parse_run_id', 'snapshot_sha256', 'edition_id',
                'reviewer', 'reviewed_at', 'evidence_reference', 'decision',
                'identity_basis', 'reference_date_basis', 'population_scope_basis', 'sector_scope_basis'}
    if not isinstance(decision, dict) or set(decision) != required:
        return gate('blocked', 0, 1, 'review_decision_contract_invalid')
    if decision['contract'] != 'edition-attribution-review-v1' or decision['decision'] != 'accepted':
        return gate('blocked', 0, 1, 'review_decision_not_accepted')
    if any(decision[k] != pins[k] for k in ('capture_id', 'parse_run_id', 'snapshot_sha256')):
        return gate('blocked', 0, 1, 'review_decision_input_mismatch')
    try:
        UUID(decision['edition_id'])
        reviewed_at = datetime.fromisoformat(decision['reviewed_at'])
        if reviewed_at.tzinfo is None or reviewed_at > datetime.now(timezone.utc):
            raise ValueError('Invalid review timestamp')
        if any(not isinstance(decision[k], str) or not decision[k].strip()
               for k in ('reviewer', 'evidence_reference', 'identity_basis', 'reference_date_basis',
                         'population_scope_basis', 'sector_scope_basis')):
            raise ValueError('Missing review evidence')
    except (ValueError, TypeError):
        return gate('blocked', 0, 1, 'review_decision_metadata_invalid')
    if len(edition_links) != 1 or str(edition_links[0][0]) != decision['edition_id']:
        return gate('blocked', 0, 1, 'reviewed_edition_not_uniquely_attributed')
    return gate('unknown', 0, 1, 'review_claim_requires_independent_authentication_and_scope_review')


def assess(conn, *, capture_id, parse_run_id, code_revision, expected_count, decision=None, qa_code_revision=None):
    capture_id, parse_run_id = str(UUID(capture_id)), str(UUID(parse_run_id))
    if not re.fullmatch('[0-9a-f]{40}', code_revision):
        raise ValueError('Exact executing code revision required')
    if type(expected_count) is not int or not 0 < expected_count <= 10000:
        raise ValueError('Bounded explicit record denominator required')
    with conn.cursor() as cur:
        cur.execute('SET TRANSACTION READ ONLY')
        cur.execute('''SELECT o.sha256,s.snapshot_sha256 FROM source.source_capture c
            JOIN source.content_object o USING(content_object_id)
            JOIN source.capture_parse_run cr USING(capture_id)
            JOIN source.parse_snapshot s USING(parse_run_id)
            WHERE c.capture_id=%s AND cr.parse_run_id=%s''', (capture_id, parse_run_id))
        selected = cur.fetchall()
        if len(selected) != 1:
            raise ValueError('Exact capture/run snapshot unavailable or ambiguous')
    source_sha, snapshot_sha = selected[0]
    pins = dict(capture_id=capture_id, parse_run_id=parse_run_id, source_sha256=source_sha,
                expected_count=expected_count, expected_snapshot_sha256=snapshot_sha,
                code_revision=code_revision)
    verify_rich_readback(conn, **pins)
    records, _ = read_snapshot_verified(conn, parse_run_id)
    facts = source_facts(records)
    with conn.cursor() as cur:
        cur.execute('''SELECT e.edition_id,e.edition_identity_status_code,ce.attribution_status_code
            FROM source.capture_edition ce JOIN source.source_edition e USING(edition_id)
            JOIN source.source_capture c ON c.capture_id=ce.capture_id AND c.series_id=e.series_id
            WHERE ce.capture_id=%s''', (capture_id,))
        links = cur.fetchall()
    uncertain = (facts['identifiers'].get('without_candidate_scheme', 0) +
                 facts['identifiers'].get('ambiguous_scheme', 0) +
                 facts['identifiers'].get('cross_name_tokens', 0) +
                 facts['identifiers'].get('unparsed_rows', 0) +
                 facts['dates'].get('application_unparsed_rows', 0) +
                 facts['dates'].get('multiple_distinct_application_date_rows', 0) +
                 facts['source_status_counts'].get('other_or_unknown', 0))
    review = review_gate(decision, pins={'capture_id':capture_id,'parse_run_id':parse_run_id,
                                       'snapshot_sha256':snapshot_sha}, edition_links=links)
    return {'contract':REPORT_CONTRACT, 'verified_at':datetime.now(timezone.utc).isoformat(),
        'capture_id':capture_id,'parse_run_id':parse_run_id,'source_parser_code_revision':code_revision,
        'qa_code_revision':qa_code_revision if qa_code_revision and re.fullmatch('[0-9a-f]{40}',qa_code_revision) else None,
        'source_sha256':source_sha,'snapshot_sha256':snapshot_sha,'expected_records':expected_count,
        'gates': {
            'structural_parser_lineage':gate('ready',len(records),expected_count,'full_readback_and_snapshot_rehash_verified'),
            'calendar_dates':calendar_gate(facts),
            'source_fact_review':gate('unknown' if uncertain else 'ready',len(records),expected_count,
                                     'candidate_identifiers_and_source_outcomes_are_not_canonical_legal_facts'),
            'identifier_checksum_and_identity':gate('unknown',0,facts['identifiers'].get('tokens',0),
                'candidate_scheme_shapes_are_not_checksum_or_identity_validation'),
            'edition_attribution_review':review,
            'semantic_execution':gate('blocked',0,1,'requires_authenticated_review_and_separate_semantic_caller_gate'),
            'publication_approval':gate('blocked',0,1,'requires_authorised_public_publisher_review')},
        'facts':facts,'edition_link_count':len(links),
        'field_values_verified':7*len(records),'mentions_verified':len(records),
        'semantic_ready':False,'publication_ready':False,'writes':0}


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--capture-id',required=True)
    cli.add_argument('--parse-run-id',required=True)
    cli.add_argument('--code-revision',required=True)
    cli.add_argument('--expected-count',required=True,type=int)
    cli.add_argument('--review-decision',type=Path)
    cli.add_argument('--qa-code-revision',default=os.environ.get('GITHUB_SHA'))
    args = cli.parse_args(argv)
    decision = json.loads(args.review_decision.read_text()) if args.review_decision else None
    try:
        with private_connection(os.environ['EVIDENCE_DATABASE_URL']) as conn:
            report = assess(conn,capture_id=args.capture_id,parse_run_id=args.parse_run_id,
                            code_revision=args.code_revision,expected_count=args.expected_count,
                            decision=decision,qa_code_revision=args.qa_code_revision)
            conn.rollback()
    except Exception as exc:
        # SQL/driver messages can contain private parameters; expose only a safe type.
        print(json.dumps({'contract':REPORT_CONTRACT, 'writes':0,
            'gates':{'structural_parser_lineage':gate('blocked',0,args.expected_count,
                'assessment_failed')}, 'error_type':type(exc).__name__,
            'semantic_ready':False,'publication_ready':False},sort_keys=True))
        return 1
    print(json.dumps(report,sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
