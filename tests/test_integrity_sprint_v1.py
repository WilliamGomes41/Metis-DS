from __future__ import annotations
import copy, hashlib, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from src.integrity_kernel import (
    compute_canonical_object_hash, exact_review_snapshot_hash, load_verified_source_registry,
    schema_errors, stamp_canonical_hashes, validate_source_fragments,
)
from src.review_ledger import append_event, verify_ledger
from src.review_workflow_v3 import apply_reviews
from src.revision_workflow import create_revision
from src.second_review_workflow_v3 import apply_second

SCHEMA=ROOT/'schemas/knowledge_object.schema.v1.1.json'
SEM=ROOT/'data/fixtures/baseline_v0_1/fractuurpreventie_page15_semantic_v21.jsonl'
RAW=ROOT/'data/fixtures/baseline_v0_1/fractuurpreventie_page15_raw.jsonl'

def rows(): return [json.loads(x) for x in SEM.read_text(encoding='utf-8').splitlines() if x.strip()]

def test_canonical_hash_covers_source_context_target_and_uncertainty():
    base=next(o for o in rows() if o['object_type']=='recommendation')
    h=compute_canonical_object_hash(base)
    for mutate in [
      lambda x: x['source'].__setitem__('source_page',99),
      lambda x: x['content']['target_group'].append('other'),
      lambda x: x['content'].__setitem__('context_text','changed'),
      lambda x: x['uncertainty'].__setitem__('has_uncertainty',True),
    ]:
        y=copy.deepcopy(base); mutate(y); assert compute_canonical_object_hash(y)!=h

def test_schema_format_checker_rejects_bad_url():
    o=copy.deepcopy(rows()[1]); o['source']['source_url']='not a uri'
    assert any('not a' in e for e in schema_errors(o,SCHEMA))

def test_verified_registry_recomputes_binary_hash(tmp_path:Path):
    b=tmp_path/'source.pdf'; b.write_bytes(b'canonical')
    h=hashlib.sha256(b.read_bytes()).hexdigest(); reg=tmp_path/'reg.json'
    reg.write_text(json.dumps({'sources':[{'source_id':'s1','source_checksum':h,'integrity_status':'verified','binary_path':str(b)}]}))
    assert load_verified_source_registry(reg)=={'s1':h}
    b.write_bytes(b'tampered')
    assert load_verified_source_registry(reg)=={}

def test_source_fragment_refs_resolve_to_raw_hashes():
    raw={x['object_id']:x for x in [json.loads(z) for z in RAW.read_text().splitlines() if z.strip()]}
    o=next(o for o in rows() if o['object_type']=='score_rule')
    assert validate_source_fragments(o,raw)==[]
    bad=copy.deepcopy(o); bad['provenance']['source_fragments'][0]['raw_content_hash']='0'*64
    assert any('source_fragment_hash_mismatch' in e for e in validate_source_fragments(bad,raw))

def test_first_review_requires_exact_canonical_hash(tmp_path:Path):
    o=next(o for o in rows() if o['governance']['review_track']=='clinical')
    wrong=[{'object_id':o['object_id'],'decision':'approve','reviewer':'R1','review_date':'2026-08-19','reviewed_canonical_object_hash':'0'*64}]
    out,rep=apply_reviews([o],wrong,track='clinical',schema_path=SCHEMA,ledger_path=tmp_path/'ledger.jsonl')
    assert rep['stats']['snapshot_mismatch']==1 and out[0]['governance']['validation_status']=='needs_review'
    right=copy.deepcopy(wrong); right[0]['reviewed_canonical_object_hash']=exact_review_snapshot_hash(o)
    out,rep=apply_reviews([o],right,track='clinical',schema_path=SCHEMA,ledger_path=tmp_path/'ledger.jsonl')
    assert out[0]['governance']['validation_status']=='approved' and out[0]['governance']['review_snapshot_hash']==exact_review_snapshot_hash(out[0])

def test_technical_review_is_separate_track(tmp_path:Path):
    o=next(o for o in rows() if o['object_type']=='document')
    d=[{'object_id':o['object_id'],'decision':'approve','reviewer':'Tech Reviewer','review_date':'2026-08-19','reviewed_canonical_object_hash':exact_review_snapshot_hash(o)}]
    out,rep=apply_reviews([o],d,track='technical',schema_path=SCHEMA,ledger_path=tmp_path/'ledger.jsonl')
    assert out[0]['governance']['validation_status']=='approved'

def test_revision_creates_new_version_and_resets_review(tmp_path:Path):
    o=copy.deepcopy(next(o for o in rows() if o['object_type']=='recommendation'))
    o['governance']['validation_status']='revise'; o['governance']['validated_by']='R1'; o['governance']['validation_date']='2026-08-19'; o['governance']['review_snapshot_hash']=exact_review_snapshot_hash(o)
    patch={'reason':'Expert correction','operations':[{'op':'set','path':'content.clean_text','value':o['content']['clean_text']+' corrected'}]}
    new=create_revision(o,patch,actor='semantic-manager',schema_path=SCHEMA,ledger=tmp_path/'ledger.jsonl')
    assert new['object_version']=='1.0.1'
    assert new['provenance']['previous_object_version']=='1.0'
    assert new['governance']['validation_status']=='needs_review'
    assert new['governance']['validated_by'] is None
    assert new['provenance']['canonical_object_hash']!=o['provenance']['canonical_object_hash']

def test_second_review_exact_hash_and_different_reviewer(tmp_path:Path):
    o=copy.deepcopy(next(o for o in rows() if o['risk']['requires_second_review']))
    o['governance']['validation_status']='approved'; o['governance']['validated_by']='R1'; o['governance']['validation_date']='2026-08-19'; o['governance']['review_snapshot_hash']=exact_review_snapshot_hash(o)
    decision=[{'object_id':o['object_id'],'decision':'approve','reviewer':'R2','review_date':'2026-08-19','reviewed_canonical_object_hash':exact_review_snapshot_hash(o)}]
    out,rep=apply_second([o],decision,tmp_path/'ledger.jsonl')
    assert out[0]['governance']['second_review']['status']=='approved' and rep['errors']==[]
    decision[0]['reviewer']='R1'; out,rep=apply_second([o],decision)
    assert any(e['error']=='second_reviewer_must_differ' for e in rep['errors'])

def test_review_ledger_detects_tamper(tmp_path:Path):
    p=tmp_path/'ledger.jsonl'; append_event(p,event_type='x',object_id='o',object_version='1',actor='a',details={'x':1}); append_event(p,event_type='y',object_id='o',object_version='1',actor='b',details={'y':2})
    assert verify_ledger(p)==[]
    data=p.read_text().replace('"x": 1','"x": 9'); p.write_text(data)
    assert any('event_hash_mismatch' in e for e in verify_ledger(p))

def test_pdf_v2_extractor_captures_coordinates_and_full_fragment_hash(tmp_path:Path):
    import fitz
    from src.extract_pdf_v2 import extract, fragment_payload
    from src.integrity_kernel import stable_hash
    pdf=tmp_path/'x.pdf'; doc=fitz.open(); page=doc.new_page(); page.insert_text((72,72),'Signalering test'); doc.save(pdf); doc.close()
    frags=extract(pdf,document_id='doc1',source_id='source1',pages=[1])
    assert frags and len(frags[0]['bbox'])==4 and all(isinstance(v,float) for v in frags[0]['bbox'])
    assert frags[0]['fragment_hash']==stable_hash(fragment_payload(frags[0]))

def test_verified_source_can_be_bound_into_new_manifest(tmp_path:Path):
    from src.source_registry import register_source
    from src.bind_source_manifest import bind
    manifest=json.loads((ROOT/'data/source_manifest.v2.json').read_text())
    sid=manifest['canonical_source']['source_id']; b=tmp_path/'source.pdf'; b.write_bytes(b'official-pdf-binary')
    rec=register_source(sid,b,manifest['canonical_source']['source_url'],manifest['canonical_source']['version'])
    reg=tmp_path/'reg.json'; reg.write_text(json.dumps({'sources':[rec]}))
    out=bind(manifest,reg)
    assert out['canonical_source']['integrity_status']=='verified'
    assert out['canonical_source']['source_checksum']==hashlib.sha256(b.read_bytes()).hexdigest()
    assert out['manifest_version']=='2.1'
