from __future__ import annotations
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.extract_html_v1 import extract as extract_html
from src.integrity_kernel import exact_review_snapshot_hash
from src.prepublication_gate_v3 import evaluate as prepublish
from src.review_workflow_v3 import apply_reviews
from src.second_review_workflow_v3 import apply_second
from src.semantic_transform_generic_v1 import transform as generic_transform

ROOT=Path(__file__).resolve().parents[1]
SCHEMA=json.loads((ROOT/'schemas/knowledge_object.schema.v1.0.json').read_text(encoding='utf-8'))
PROPOSAL_SCHEMA=json.loads((ROOT/'schemas/proposal.schema.v1.0.json').read_text(encoding='utf-8'))
OUT=ROOT/'data/fixtures/baseline_v0_1/fractuurpreventie_page15_semantic_v2.jsonl'
SPEC=ROOT/'data/semantic_page15_spec.v2.0.json'
MANIFEST=ROOT/'data/source_manifest.v2.json'
CURRENT_OUT=ROOT/'data/fixtures/baseline_v0_1/fractuurpreventie_page15_semantic_v21.jsonl'
CURRENT_RAW=ROOT/'data/fixtures/baseline_v0_1/fractuurpreventie_page15_raw.jsonl'
CURRENT_SCHEMA=ROOT/'schemas/knowledge_object.schema.v1.1.json'


def rows():
    return [json.loads(x) for x in OUT.read_text(encoding='utf-8').splitlines() if x.strip()]


def current_rows():
    return [json.loads(x) for x in CURRENT_OUT.read_text(encoding='utf-8').splitlines() if x.strip()]


def test_closed_model_and_schema_valid():
    v=Draft202012Validator(SCHEMA)
    allowed={'document','section','definition','condition','score_rule','decision','action','recommendation','exception','out_of_scope','supersession'}
    for o in rows():
        assert not list(v.iter_errors(o))
        assert o['object_type'] in allowed
        assert o['object_type'] not in {'table','background','patient_information'}


def test_existing_expert_ids_preserved():
    old=[json.loads(x)['object_id'] for x in (ROOT/'data/fixtures/baseline_v0_1/fractuurpreventie_page15_semantic.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    new={o['object_id'] for o in rows()}
    assert set(old).issubset(new)
    assert len(new-set(old))==1
    assert next(iter(new-set(old))).endswith('-document')


def test_deterministic_transform_byte_identical(tmp_path: Path):
    html=tmp_path/'source.html'
    html.write_text('<h1>Test</h1><p>Adviseer passende zorg.</p>', encoding='utf-8')
    raw=extract_html(html, document_id='doc-test', source_id='source-test')
    fragment=raw[-1]['fragment_id']
    manifest={'canonical_source':{
        'source_id':'source-test','title':'Test source','publisher':'V&VN',
        'source_url':'https://example.org/test','source_type':'html','source_level':1,
        'canonicality':'canonical','source_checksum':None,'checksum_algorithm':'sha256',
        'integrity_status':'binary_unavailable','publication_date':'2025-04-01','version':'1.0'
    }}
    spec={
        'spec_version':'1.0','document_id':'doc-test','object_version':'1.0',
        'target_group':['verpleegkundige'],'care_setting':['wijkzorg'],'topic':['test'],
        'objects':[{
            'object_id':'doc-test-rec-01','object_type':'recommendation',
            'text':'Adviseer passende zorg.','source_fragment_ids':[fragment]
        }]
    }
    assert generic_transform(spec, manifest, raw)==generic_transform(spec, manifest, raw)


def test_risk_fields_force_second_review():
    high=[o for o in rows() if o['risk']['risk_level']=='high']
    assert high
    for o in high:
        assert o['risk']['requires_second_review'] is True
        assert o['governance']['second_review']['required'] is True
        assert o['governance']['second_review']['status']=='pending'
    # Known risky referral threshold must be included.
    obj=next(o for o in rows() if o['object_id'].endswith('rec-screening-60plus-02'))
    assert {'score_threshold','operator','escalation_decision'} <= set(obj['risk']['risk_fields'])


def test_corrected_alcohol_rule_is_gte_3():
    obj=next(o for o in rows() if o['object_id'].endswith('score-07'))
    pred=obj['logic']['predicates'][0]
    assert pred['operator']=='gte'
    assert pred['threshold']==3
    assert '≥ 3' in obj['content']['clean_text']


def test_ai_proposal_is_separate_schema_and_not_canonical():
    proposal={
        'proposal_id':'proposal-1','target_object_id':None,'proposal_type':'classification',
        'proposal':{'object_type':'definition'},'model':'test-model','created_at':'2026-08-19T12:00:00+02:00','status':'proposal'
    }
    assert not list(Draft202012Validator(PROPOSAL_SCHEMA).iter_errors(proposal))
    assert list(Draft202012Validator(SCHEMA).iter_errors(proposal))
    assert all(o['provenance']['proposal_id'] is None for o in rows())


def test_decision_graph_nodes_edges_supported():
    base=copy.deepcopy(next(o for o in rows() if o['object_type']=='condition'))
    base['object_id']='synthetic-decision'
    base['object_type']='decision'
    base['parent_object_id']=None
    base['relations']=[]
    base['decision_graph']={
        'node_id':'node-1','node_kind':'question',
        'edges':[{'edge_id':'e1','target_node_id':'node-2','branch_label':'Ja','exclusive':True}]
    }
    assert not list(Draft202012Validator(SCHEMA).iter_errors(base))


def test_source_manifest_blocks_publication_until_hash_verified():
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
    assert manifest['canonical_source']['integrity_status']=='binary_unavailable'
    assert manifest['canonical_source']['source_checksum'] is None
    assert manifest['canonical_source']['publication_eligibility']=='blocked_until_binary_hash_verified'


def test_prepublication_gate_fails_closed(tmp_path: Path):
    registry=tmp_path/'source_registry.json'
    registry.write_text(json.dumps({'sources':[]}), encoding='utf-8')
    report=prepublish(
        current_rows(),
        schema=CURRENT_SCHEMA,
        source_registry=registry,
        raw_extract=CURRENT_RAW,
    )
    assert report['status']=='BLOCKED'
    assert report['errors']


def test_review_snapshot_mismatch_detects_alcohol_fix(tmp_path: Path):
    obj=copy.deepcopy(next(o for o in current_rows() if o['object_id'].endswith('score-07')))
    decisions=[{
        'object_id':obj['object_id'],'decision':'approve','reviewer':'Reviewer A',
        'review_date':'2026-08-19','reviewed_canonical_object_hash':'0'*64,
    }]
    out,report=apply_reviews(
        [obj],decisions,track=obj['governance']['review_track'],
        schema_path=CURRENT_SCHEMA,ledger_path=tmp_path/'ledger.jsonl',
    )
    assert report['stats']['snapshot_mismatch']==1
    assert out[0]['governance']['validation_status']=='needs_review'


def test_published_is_separate_from_approved():
    for o in rows():
        assert o['governance']['publication_status']=='unpublished'
        assert o['governance']['validation_status']=='needs_review'


def test_second_reviewer_must_be_different(tmp_path: Path):
    obj=copy.deepcopy(next(o for o in current_rows() if o['risk']['requires_second_review']))
    obj['governance']['validation_status']='approved'
    obj['governance']['validated_by']='Reviewer A'
    obj['governance']['validation_date']='2026-08-19'
    obj['governance']['review_snapshot_hash']=exact_review_snapshot_hash(obj)
    decisions=[{
        'object_id':obj['object_id'],'decision':'approve','reviewer':'Reviewer A',
        'review_date':'2026-08-19',
        'reviewed_canonical_object_hash':exact_review_snapshot_hash(obj),'comment':'',
    }]
    _,report=apply_second([obj],decisions,tmp_path/'ledger.jsonl')
    assert any(e['error']=='second_reviewer_must_differ' for e in report['errors'])
