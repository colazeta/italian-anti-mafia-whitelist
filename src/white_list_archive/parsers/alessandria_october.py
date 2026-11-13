"""Reviewed October source profile for the existing Alessandria table family.

No physical parser fork: reuse the established conflict-preserving family, but
require the independently reviewed full-document fingerprint and denominators.
"""
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import re

import pdfplumber
from white_list_archive.parsers import multi_prefecture_tables as family

PARSER_VERSION = '1'
REFERENCE_DATE = '2026-10-28'
PROFILES = {
    'listed': dict(sha256='7081de5f4bd1a583abc2a9024396857db3717e2ed6d1ad0f5a4d6e30dc7152cf',
                   bytes=1296335, pages=60, physical_rows=752, source_rows=715, records=390,
                   row_digest='a7dd2256d23f25b6f59fd8746b15434468060e580c473c9087072a6647837aef',
                   statuses={'listed':272,'renewal_update_in_progress':116,'other_or_unknown':2},
                   identifiers=372, raw_identifiers=18),
    'applicants': dict(sha256='b10733818c5e7f04b40c3b7d76da837acbe12e300e2d2e9b79f249bd48837b34',
                       bytes=161221, pages=10, physical_rows=67, source_rows=65, records=65,
                       row_digest='76f52ecfdbebc98fd7ef55f951700b93e5772813cce64be887b98ef8c9f2c943',
                       statuses={'pending':64,'other_or_unknown':1}, identifiers=63,raw_identifiers=2),
}


def _validate_identity(path, cfg, label):
    p=PROFILES[label]
    expected=dict(source_key='alessandria-'+label, authority_key='alessandria',
                  register_key='alessandria-ordinary', reference_date=REFERENCE_DATE,
                  population_scope='listed' if label=='listed' else 'applicant',
                  parser='alessandria_'+label+'_2026_10', sha256=p['sha256'])
    if any(cfg.get(k)!=v for k,v in expected.items()):
        raise RuntimeError('Alessandria October reviewed configuration drift')
    if path.stat().st_size!=p['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=p['sha256']:
        raise RuntimeError('Alessandria October original byte identity drift')


def _physical_profile(path,label):
    p=PROFILES[label];digest=hashlib.sha256();physical=identities=0
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages)!=p['pages']:
            raise RuntimeError('Alessandria October page-count drift')
        for pno,page in enumerate(pdf.pages,1):
            tables=page.find_tables()
            if len(tables)!=1:
                raise RuntimeError('Alessandria October table-count drift')
            for tno,table in enumerate(tables,1):
                for rno,raw in enumerate(table.extract() or [],1):
                    cells=[family._clean(v) for v in raw];physical+=1
                    if len(cells)!=(7 if label=='listed' else 6):
                        raise RuntimeError('Alessandria October table-width drift')
                    digest.update(json.dumps([pno,tno,rno,cells],ensure_ascii=False,separators=(',',':')).encode())
                    index=3 if label=='listed' else 2
                    if cells[0] and len(re.sub(r'[^A-Za-z0-9]','',cells[index]))>=8 and re.search(r'\d',cells[index]):
                        identities+=1
    if physical!=p['physical_rows'] or identities!=p['source_rows'] or digest.hexdigest()!=p['row_digest']:
        raise RuntimeError('Alessandria October complete physical-row profile drift')


def _validate_batch(batch,label):
    p=PROFILES[label];d=batch.diagnostics
    expected={'date_rows':p['source_rows'],'public_records':p['records'],'dropped_date_rows':0,
              'identifier_coverage':p['identifiers'],'raw_identifier_only':p['raw_identifiers']}
    if any(d.get(k)!=v for k,v in expected.items()) or len(batch.records)!=p['records']:
        raise RuntimeError('Alessandria October parser denominator/drop drift')
    if dict(Counter(r['source_status'] for r in batch.records))!=p['statuses']:
        raise RuntimeError('Alessandria October source-status drift')
    if label=='listed':
        if (d.get('sector_rows')!=715 or d.get('date_conflict_identity_groups')!=4
                or d.get('reconciled_malformed_date_rows')!=2):
            raise RuntimeError('Alessandria October conflict/malformed date population drift')
    else:
        for r in batch.records:
            # The generic family's syntactic date recogniser must not conceal an
            # invalid calendar date in the reviewed applicant edition.
            date.fromisoformat(r['application_date'])
    if any(not r['name'] for r in batch.records):
        raise RuntimeError('Alessandria October unreviewed blank name')


def _parse(path,cfg,label):
    _validate_identity(path,cfg,label)
    _physical_profile(path,label)
    batch=family.PARSERS['alessandria_'+label](path,cfg)
    _validate_batch(batch,label)
    batch.diagnostics.update(parser=cfg['parser'],parser_version=PARSER_VERSION,
                             reviewed_source_profile=REFERENCE_DATE,source_pages=PROFILES[label]['pages'])
    return batch


def parse_listed(path,cfg): return _parse(path,cfg,'listed')
def parse_applicants(path,cfg): return _parse(path,cfg,'applicants')
PARSERS={'alessandria_listed_2026_10':parse_listed,'alessandria_applicants_2026_10':parse_applicants}
