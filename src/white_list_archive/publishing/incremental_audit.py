"""Exact observation-level delta checks for a reviewed incremental public release."""
from collections import Counter, defaultdict
import hashlib
import json


def _by_source(records):
    groups=defaultdict(list)
    for row in records: groups[row['source_key']].append(row)
    return groups


def _digest(rows):
    return hashlib.sha256(json.dumps(sorted(rows,key=lambda r:r['record_locator']),
        ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def audit_incremental(proposal, approved, changes):
    before,after=_by_source(approved['records']),_by_source(proposal['records'])
    if set(before)!=set(after) or not set(changes)<=set(before):
        raise ValueError('Incremental release changed source-series coverage')
    changed=[k for k in before if k not in changes and _digest(before[k])!=_digest(after[k])]
    if changed:
        raise ValueError('Unapproved changes outside the selected source scope: '+', '.join(sorted(changed)))
    for field in ('authority_count','register_count'):
        if proposal['meta'][field]!=approved['meta'][field]:
            raise ValueError('Incremental release changed '+field)
    expected=len(approved['records'])+sum(spec['count']-len(before[k]) for k,spec in changes.items())
    if len(proposal['records'])!=expected:
        raise ValueError('Incremental national observation denominator mismatch')
    reports={r['source_key']:r for r in proposal['meta']['sources']}
    summary={}
    for key,spec in changes.items():
        rows=after[key];report=reports[key]
        if len(rows)!=spec['count'] or dict(Counter(r['source_status'] for r in rows))!=spec['statuses']:
            raise ValueError('Reviewed observation/status denominator mismatch for '+key)
        for field in ('reference_date','sha256','parser'):
            if report.get(field)!=spec[field]:
                raise ValueError('Reviewed source report '+field+' mismatch for '+key)
        if any(r['reference_date']!=spec['reference_date'] or r['capture_sha256']!=spec['sha256']
               or r['parser_name']!=spec['parser'] for r in rows):
            raise ValueError('Reviewed row provenance mismatch for '+key)
        if sum(not r.get('name') for r in rows)!=spec.get('blank_names',0):
            raise ValueError('Unreviewed blank source-name count for '+key)
        summary[key]={'previous_records':len(before[key]),'proposed_records':len(rows),
                      'reference_date':spec['reference_date'],'statuses':spec['statuses']}
    return {'national_approved_baseline':len(approved['records']),'national_proposed':expected,
            'authority_count':proposal['meta']['authority_count'],'register_count':proposal['meta']['register_count'],
            'outside_scope_observations_changed':0,'sources_updated':summary,'published':False}
