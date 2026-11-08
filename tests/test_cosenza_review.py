"""Synthetic-only privacy, provenance, deterministic diff and durable readback checks."""
from copy import deepcopy
from io import BytesIO
import hashlib
import json
import sys
from types import SimpleNamespace
from uuid import UUID

import pytest
from botocore.exceptions import ClientError

from white_list_archive.normalisation import cosenza_review as review
from white_list_archive.persistence.parse_snapshot import snapshot_sha256


class Client:
    def __init__(self): self.objects = {}; self.corrupt = False
    def put_object(self, **kw):
        assert kw['IfNoneMatch'] == '*'
        if kw['Key'] in self.objects:
            raise ClientError({'Error':{'Code':'PreconditionFailed'}},'PutObject')
        self.objects[kw['Key']] = kw['Body']
    def get_object(self, **kw):
        data=self.objects[kw['Key']]
        return {'Body':BytesIO(data+b'!' if self.corrupt else data)}


def row(n, raw, mention='mention'):
    return {'row_ordinal':n,'record_hash':hashlib.sha256(raw.encode()).hexdigest(),
            'mention_key':mention,'operator_name_raw':'PRIVATE SYNTHETIC NAME','raw_block':raw,
            'source_status':'listed'}


def inputs():
    return [{'capture_id':str(UUID(int=i)), 'parse_run_id':str(UUID(int=i+10)),
             'source_revision':'a'*40, 'expected_count':1} for i in (1,2)]


@pytest.fixture
def verified(monkeypatch):
    archive=SimpleNamespace(client=Client(),config=SimpleNamespace(bucket='private'))
    archive.read_verified=lambda manifest:b'original'
    rows=[row(1,'private-original')]
    diagnostics={'synthetic':True}
    sha=hashlib.sha256(b'original').hexdigest()
    snapshot=snapshot_sha256(rows,diagnostics)
    def qa(conn,**kw):
        return {'contract':'cosenza-source-qa-v1','capture_id':kw['capture_id'],
            'parse_run_id':kw['parse_run_id'],'source_parser_code_revision':kw['code_revision'],
            'verified_at':'changes-every-time','source_sha256':sha,'snapshot_sha256':snapshot,
            'writes':0,'semantic_ready':False,'publication_ready':False,
            'gates':{'structural_parser_lineage':{'status':'ready'}},'facts':{'dates':{'tokens':0}}}
    monkeypatch.setattr(review,'assess',qa)
    monkeypatch.setattr(review,'read_snapshot_verified',lambda *a:(deepcopy(rows),diagnostics))
    monkeypatch.setattr(review,'CaptureCatalogue',lambda store:None)
    monkeypatch.setattr(review,'load_catalogued_capture',lambda catalogue,**kw:(
        {'capture_id':kw['capture_id'],'sha256':sha,'byte_size':8,'captured_at':'2026-11-08T01:00:00Z'},
        {'catalogue_record_sha256':'b'*64}))
    def plan_records(records,**pins):
        payload={'rows':records,'pins':pins,'canonical_writes':0}
        return {'private_payload':payload,'candidate_sha256':review.digest(payload)}
    monkeypatch.setitem(sys.modules,'white_list_archive.normalisation.cosenza_candidate',
                        SimpleNamespace(plan_records=plan_records))
    return archive


def test_dossier_is_deterministic_private_and_all_three_objects_read_back(verified):
    first=review.retain_review(object(),verified,inputs=inputs(),dossier_code_revision='c'*40)
    again=review.retain_review(object(),verified,inputs=inputs(),dossier_code_revision='c'*40)
    assert first==again and len(verified.client.objects)==3
    dossier=review.load_retained_review(verified,first['dossier_sha256'])
    assert all(v['administrative_reference_date'] is None for v in dossier['versions'])
    assert all('verified_at' not in v['qa'] for v in dossier['versions'])
    assert dossier['versions'][0]['pins']['source_revision']=='a'*40
    assert dossier['dossier_code_revision']=='c'*40
    assert dossier['document_comparison']['legal_event_inference_performed'] is False
    assert 'PRIVATE SYNTHETIC NAME' in json.dumps(dossier)
    safe=json.dumps(first['safe_summary'])
    assert 'PRIVATE' not in safe and 'operations/' not in safe
    assert inputs()[0]['capture_id'] not in safe
    assert first['safe_summary']['immutable'] is True
    assert first['safe_summary']['semantic_ready'] is False


def test_single_version_does_not_fabricate_comparison_zeros(verified):
    result=review.retain_review(object(),verified,inputs=inputs()[:1],dossier_code_revision='c'*40)
    summary=result['safe_summary']
    assert summary['comparison_verified'] is False
    assert summary['before_only_occurrences'] is None


def test_multiset_diff_preserves_duplicate_occurrences_and_infers_no_legal_events():
    old=[row(1,'same'),row(2,'same'),row(3,'absent','other')]
    new=[row(1,'same'),row(2,'new','third')]
    diff=review.document_diff(old,new)
    assert diff['identical_occurrences']==1
    assert diff['before_only_occurrences']==2
    assert diff['after_only_occurrences']==1
    assert diff['legal_event_inference_performed'] is False
    assert diff['ambiguous_shared_mention_groups']==1
    assert not diff['changed_unambiguous_document_mentions']


def test_changed_unique_mention_is_document_change_not_identity_resolution():
    diff=review.document_diff([row(1,'old')],[row(9,'new')])
    assert len(diff['changed_unambiguous_document_mentions'])==1
    assert 'row_ordinal' not in diff['changed_unambiguous_document_mentions'][0]['changed_fields']
    assert diff['before_only_occurrences']==diff['after_only_occurrences']==1


def test_corrupt_durable_readback_prevents_verified_receipt(verified):
    verified.client.corrupt=True
    with pytest.raises(ValueError,match='exact readback'):
        review.retain_review(object(),verified,inputs=inputs(),dossier_code_revision='c'*40)
    assert not any('/receipts/' in key for key in verified.client.objects)


def test_original_mismatch_is_rejected_before_any_dossier_persistence(verified):
    verified.read_verified=lambda manifest:b'changed'
    with pytest.raises(ValueError,match='original/capture/QA'):
        review.retain_review(object(),verified,inputs=inputs(),dossier_code_revision='c'*40)
    assert not verified.client.objects


def test_snapshot_qa_mismatch_is_rejected(verified,monkeypatch):
    monkeypatch.setattr(review,'read_snapshot_verified',lambda *a:([row(1,'different')],{}))
    with pytest.raises(ValueError,match='QA/snapshot'):
        review.retain_review(object(),verified,inputs=inputs(),dossier_code_revision='c'*40)
    assert not verified.client.objects


def test_failed_lineage_gate_never_becomes_review_ready(verified,monkeypatch):
    monkeypatch.setattr(review,'assess',lambda *a,**kw:{'writes':0,'semantic_ready':False,
        'publication_ready':False,'gates':{'structural_parser_lineage':{'status':'blocked'}}})
    with pytest.raises(ValueError,match='lineage'):
        review.retain_review(object(),verified,inputs=inputs(),dossier_code_revision='c'*40)
    assert not verified.client.objects


def test_revision_and_order_change_identity_without_asserting_chronology(verified):
    first=review.retain_review(object(),verified,inputs=inputs(),dossier_code_revision='c'*40)
    changed=review.retain_review(object(),verified,inputs=inputs(),dossier_code_revision='d'*40)
    reversed_order=review.retain_review(object(),verified,inputs=list(reversed(inputs())),dossier_code_revision='c'*40)
    assert len({x['dossier_sha256'] for x in (first,changed,reversed_order)})==3


def test_duplicate_versions_and_nonexact_code_are_rejected(verified):
    with pytest.raises(ValueError,match='Duplicate'):
        review.retain_review(object(),verified,inputs=[inputs()[0]]*2,dossier_code_revision='c'*40)
    with pytest.raises(ValueError,match='Exact dossier'):
        review.retain_review(object(),verified,inputs=inputs(),dossier_code_revision='main')
