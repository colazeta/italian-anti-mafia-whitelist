"""Deterministic private source-fact candidates; never an executable legal projection."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import re
from uuid import UUID

from white_list_archive.acquisition.auto_transform import read_snapshot_verified
from white_list_archive.normalisation.cosenza_qa import assess
from white_list_archive.persistence.capture_rich_cosenza import validate_records
from white_list_archive.semantic.combined_whitelist_v1 import map_activity, parse_source_date

CONTRACT = 'cosenza-private-source-candidate-v1'
CONFIGURATION = {'row_identity':'parse_run_id+physical_row_locator',
    'dates':'calendar-valid source dates only; unknowns remain unknown',
    'identifiers':'source candidate schemes only; no canonical identity assertion',
    'status':'source outcome text/classification only; no legal effect',
    'activities':'requested source activity candidates only; no represented relationship sector'}


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


CONFIGURATION_SHA256 = hashlib.sha256(canonical(CONFIGURATION)).hexdigest()


def plan_records(records, *, capture_id, parse_run_id, source_sha256, snapshot_sha256,
                 source_revision, planner_revision):
    """Pure planner for ALREADY verified rich input.

    Call through build_candidate or an independently verified private dossier
    that performed the equivalent original, snapshot and full relational QA.

    The returned document contains private row values and must never reach logs or
    public artifacts. Its candidate digest excludes processing time and QA timestamps.
    """
    capture_id, parse_run_id = str(UUID(capture_id)), str(UUID(parse_run_id))
    if any(not isinstance(value,str) or not re.fullmatch('[0-9a-f]{40}',value)
           for value in (source_revision,planner_revision)):
        raise ValueError('Exact parser and planner code revisions required')
    if not isinstance(source_sha256,str) or not re.fullmatch('[0-9a-f]{64}',source_sha256):
        raise ValueError('Exact source hash required')
    if validate_records(records,len(records)) != snapshot_sha256:
        raise ValueError('Candidate source rows differ from pinned rich snapshot')
    rows = []
    issues = Counter()
    for record in records:
        loc = f'row:{record["row_ordinal"]:06d}'
        identifiers = json.loads(record['identifiers_json'])
        dates = []
        for item in json.loads(record['application_dates_json']):
            parsed = parse_source_date(item.get('date'))
            dates.append({'source_value':item,'calendar_date':parsed.isoformat() if parsed else None})
            issues['invalid_application_dates'] += parsed is None
        observed_dates = {}
        for field in ('observed_listing_date','observed_expiry_date'):
            raw = record[field]
            parsed = parse_source_date(raw)
            observed_dates[field + '_calendar_candidate'] = parsed.isoformat() if parsed else None
            issues['invalid_' + field] += bool(raw.strip()) and parsed is None
        for identifier in identifiers:
            issues['identifier_without_candidate_scheme'] += not bool(identifier.get('candidate_schemes'))
            issues['identifier_ambiguous_scheme'] += len(identifier.get('candidate_schemes',[])) != 1
        activities = json.loads(record['requested_activities_json'])
        # The physical parser emits activity strings; dictionary/unknown contracts fail closed.
        if any(not isinstance(activity,str) for activity in activities):
            raise ValueError('Unsupported requested activity source contract')
        rows.append({'provenance':{'capture_id':capture_id,'parse_run_id':parse_run_id,
            'record_locator':loc,'record_hash':record['record_hash']},
            'source_facts':{'name_raw':record['operator_name_raw'],
                'name_normalised':record['operator_name_normalised'],
                'registered_office_raw':record['registered_office_raw'],
                'secondary_office_raw':record['secondary_office_raw'],
                'identifier_field_raw':record['identifier_field_raw'],
                'identifier_candidates':identifiers,'application_date_field_raw':record['application_date_field_raw'],
                'application_date_candidates':dates,'requested_activities_raw':record['requested_activities_raw'],
                'observed_listing_date_raw':record['observed_listing_date'],
                'observed_expiry_date_raw':record['observed_expiry_date'],
                **observed_dates,
                'requested_activity_candidates':[{'source_value':a,'candidate_concept':map_activity(a)} for a in activities],
                'outcome_raw':record['outcome_raw'],'source_status':record['source_status']},
            'canonical_entity_id':None,'canonical_legal_status':None,'edition_approval':None})
    payload = {'contract':CONTRACT,'configuration_sha256':CONFIGURATION_SHA256,
        'capture_id':capture_id,'parse_run_id':parse_run_id,'source_sha256':source_sha256,
        'snapshot_sha256':snapshot_sha256,'source_parser_revision':source_revision,
        'planner_revision':planner_revision,'record_count':len(rows),'rows':rows,
        'issue_counts':dict(sorted(issues.items())),
        'execution_status':'blocked_requires_reviewed_edition_attribution_and_separate_semantic_gate',
        'writes':0,'publications':0}
    return {'private_payload':payload,'candidate_sha256':hashlib.sha256(canonical(payload)).hexdigest(),
        'safe_summary':{'contract':CONTRACT,'record_count':len(rows),'issue_counts':payload['issue_counts'],
            'semantic_execution_ready':False,'canonical_execution_ready':False,'writes':0,'publications':0}}


def build_candidate(conn, *, capture_id, parse_run_id, source_revision, expected_count,
                    planner_revision):
    """Verify all persisted source rows and return a private immutable candidate document."""
    qa = assess(conn,capture_id=capture_id,parse_run_id=parse_run_id,code_revision=source_revision,
                expected_count=expected_count,qa_code_revision=planner_revision)
    records,_ = read_snapshot_verified(conn,parse_run_id)
    result = plan_records(records,capture_id=qa['capture_id'],parse_run_id=qa['parse_run_id'],
        source_sha256=qa['source_sha256'],snapshot_sha256=qa['snapshot_sha256'],
        source_revision=source_revision,planner_revision=planner_revision)
    result['safe_summary']['candidate_sha256'] = result['candidate_sha256']
    return result
