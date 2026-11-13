"""Synthetic source-profile regressions; no company data."""
from types import SimpleNamespace
import pytest
from white_list_archive.parsers import alessandria_october as october
from white_list_archive.publishing.incremental_audit import audit_incremental


def test_new_profile_never_accepts_unreviewed_bytes_or_date(tmp_path):
    p=tmp_path/'source.pdf';p.write_bytes(b'unreviewed')
    cfg=dict(source_key='alessandria-listed',authority_key='alessandria',register_key='alessandria-ordinary',
             reference_date='2026-10-28',population_scope='listed',parser='alessandria_listed_2026_10',
             sha256=october.PROFILES['listed']['sha256'])
    with pytest.raises(RuntimeError,match='byte identity'): october._validate_identity(p,cfg,'listed')
    cfg['reference_date']='2026-09-04'
    with pytest.raises(RuntimeError,match='configuration'): october._validate_identity(p,cfg,'listed')


def sample(key, date='2026-09-04', sha='old', parser='old'):
    return dict(source_key=key,record_locator=key+':'+date+':1',reference_date=date,capture_sha256=sha,
                parser_name=parser,source_status='listed',name='SYNTHETIC')


def test_incremental_release_rejects_unrelated_row_changes_and_wrong_provenance():
    approved={'records':[sample('updated'),sample('unchanged')],
              'meta':dict(authority_count=2,register_count=2,sources=[])}
    spec=dict(count=1,statuses={'listed':1},reference_date='2026-10-28',sha256='reviewed',parser='reviewed_parser')
    proposal={'records':[sample('updated',spec['reference_date'],spec['sha256'],spec['parser']),sample('unchanged')],
              'meta':dict(authority_count=2,register_count=2,sources=[{'source_key':'updated',**spec}])}
    assert audit_incremental(proposal,approved,{'updated':spec})['outside_scope_observations_changed']==0
    proposal['records'][1]['name']='UNREVIEWED CHANGE'
    with pytest.raises(ValueError,match='outside'): audit_incremental(proposal,approved,{'updated':spec})
    proposal['records'][1]=sample('unchanged');proposal['records'][0]['capture_sha256']='different'
    with pytest.raises(ValueError,match='provenance'): audit_incremental(proposal,approved,{'updated':spec})


def test_reviewed_manifest_binds_all_october_row_denominators():
    import json
    from pathlib import Path
    cfg=json.loads((Path(__file__).resolve().parents[1]/'data/publication/multi_prefecture_pilot.json').read_text())
    sources={r['source_key']:r for r in cfg['sources']}
    for label,p in october.PROFILES.items():
        source=sources['alessandria-'+label]
        assert source['sha256']==p['sha256']
        assert source['reference_date']==october.REFERENCE_DATE
        assert source['expected_source_rows']==p['records']
    assert sources['alessandria-listed']['expected_sector_rows']==715
