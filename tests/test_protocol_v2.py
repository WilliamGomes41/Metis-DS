from __future__ import annotations
import copy
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parents[1]
SCHEMA=json.loads((ROOT/'schemas/knowledge_object.schema.v1.0.json').read_text(encoding='utf-8'))
PROPOSAL_SCHEMA=json.loads((ROOT/'schemas/proposal.schema.v1.0.json').read_text(encoding='utf-8'))
OUT=ROOT/'data/fixtures/baseline_v0_1/fractuurpreventie_page15_semantic_v2.jsonl'
SPEC=ROOT/'data/semantic_page15_spec.v2.0.json'
MANIFEST=ROOT/'data/source_manifest.v2.json'


def rows():
    return [json.loads(x) for x in OUT.read_text(encoding='utf-8').splitlines() if x.strip()]


def run_transform(out: Path, report: Path):
    return subprocess.run([
        sys.executable, str(ROOT/'src/semantic_transform_v2.py'), str(SPEC),
        '--source-manifest', str(MANIFEST), '--schema', str(ROOT/'schemas/knowledge_object.schema.v1.0.json'),
        '--root', str(ROOT), '--out', str(out), '--report', str(report)
    ], capture_output=True, text=True)


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
    a=tmp_path/'a.jsonl'; ar=tmp_path/'ar.json'
    b=tmp_path/'b.jsonl'; br=tmp_path/'br.json'
    assert run_transform(a,ar).returncode==0
    assert run_transform(b,br).returncode==0
    assert hashlib.sha256(a.read_bytes()).hexdigest()==hashlib.sha256(b.read_bytes()).hexdigest()


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
    out=tmp_path/'gate.json'
    r=subprocess.run([
        sys.executable,str(ROOT/'src/prepublication_gate_v2.py'),
        '--input',str(OUT),'--schema',str(ROOT/'schemas/knowledge_object.schema.v1.0.json'),
        '--source-manifest',str(MANIFEST),'--out',str(out)
    ],capture_output=True,text=True)
    assert r.returncode==2
    report=json.loads(out.read_text(encoding='utf-8'))
    assert report['status']=='BLOCKED'
    assert any(e['error']=='canonical_source_not_hash_verified' for e in report['errors'])


def test_review_snapshot_mismatch_detects_alcohol_fix(tmp_path: Path):
    # Minimal canonical review CSV representing what the already-sent workbook showed for score-07.
    review=tmp_path/'review.csv'
    fields=['object_id','review_decision','proposed_correction','review_comment','reviewer','review_date','reviewed_text','reviewed_operator','reviewed_threshold','reviewed_unit','reviewed_score_points']
    oid='vvn-osteoporose-fractuurpreventie-2024-p015-score-07'
    with review.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter=';'); w.writeheader()
        w.writerow({
            'object_id':oid,'review_decision':'approve','reviewer':'Reviewer A','review_date':'2026-08-19',
            'reviewed_text':'Roken en/of alcohol > 3 eenheden per dag -> 1 punt','reviewed_operator':'gt',
            'reviewed_threshold':'3','reviewed_unit':'eenheden alcohol per dag','reviewed_score_points':'1',
            'proposed_correction':'','review_comment':''
        })
    reviewed=tmp_path/'reviewed.jsonl'; revise=tmp_path/'revise.jsonl'; rejected=tmp_path/'rejected.jsonl'; report=tmp_path/'report.json'
    r=subprocess.run([
        sys.executable,str(ROOT/'src/validation_workflow_v2.py'), '--input',str(OUT),'--review',str(review),
        '--schema',str(ROOT/'schemas/knowledge_object.schema.v1.0.json'),'--reviewed-out',str(reviewed),
        '--revise-out',str(revise),'--rejected-out',str(rejected),'--report',str(report),
        '--default-reviewer','Reviewer A','--default-date','2026-08-19'
    ],capture_output=True,text=True)
    rep=json.loads(report.read_text(encoding='utf-8'))
    assert rep['stats']['snapshot_mismatch']==1
    out_obj=next(o for o in [json.loads(x) for x in reviewed.read_text(encoding='utf-8').splitlines() if x.strip()] if o['object_id']==oid)
    assert out_obj['governance']['validation_status']=='needs_review'


def test_published_is_separate_from_approved():
    for o in rows():
        assert o['governance']['publication_status']=='unpublished'
        assert o['governance']['validation_status']=='needs_review'


def test_second_reviewer_must_be_different(tmp_path: Path):
    obj=copy.deepcopy(next(o for o in rows() if o['risk']['requires_second_review']))
    obj['governance']['validation_status']='approved'
    obj['governance']['validated_by']='Reviewer A'
    obj['governance']['validation_date']='2026-08-19'
    obj['governance']['review_snapshot_hash']='first-snapshot'
    inp=tmp_path/'in.jsonl'; inp.write_text(json.dumps(obj,ensure_ascii=False)+'\n',encoding='utf-8')
    review=tmp_path/'second.csv'
    fields=['object_id','second_review_decision','second_reviewer','second_review_date','reviewed_content_hash','comment']
    with review.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter=';'); w.writeheader(); w.writerow({
            'object_id':obj['object_id'],'second_review_decision':'approve','second_reviewer':'Reviewer A',
            'second_review_date':'2026-08-19','reviewed_content_hash':obj['provenance']['content_hash'],'comment':''})
    out=tmp_path/'out.jsonl'; rep=tmp_path/'rep.json'
    r=subprocess.run([sys.executable,str(ROOT/'src/apply_second_review.py'),'--input',str(inp),'--review',str(review),'--out',str(out),'--report',str(rep)],capture_output=True,text=True)
    assert r.returncode==2
    report=json.loads(rep.read_text(encoding='utf-8'))
    assert any(e['error']=='second_reviewer_must_differ_from_first' for e in report['errors'])
