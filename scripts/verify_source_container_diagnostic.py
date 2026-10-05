"""Offline acceptance of recorded proposal preservation, not new model recall."""
import json
from collections import Counter
from src.pre_review_semantic_v1 import _replay_identity, semantic_spec_from_fragments
from src.semantic_replay_v1 import validated_inference_record
from src.semantic_passage_v1 import semantic_source_blocks
from src.pre_review_semantic_v1 import _candidate_fragments, _evidence_fragments
from src.semantic_transform_generic_v1 import transform
from src.admission_gate_v1 import apply_admission_gate
from src.passage_register_v1 import apply_passage_register
from src.source_containers_v1 import partition
from src.bounded_formation_v1 import tasks_for
import argparse
parser = argparse.ArgumentParser(description="Offline replay of supplied processing diagnostic; never calls a model or mutates a working revision")
parser.add_argument("diagnostic")
parser.add_argument("--output", required=True)
parser.add_argument("--bounded", action="store_true", help="Route the recorded provider proposals through each new bounded task; still no live inference")
args = parser.parse_args()
x=json.load(open(args.diagnostic))
v=x['validator_input']; fragments=v['evidence_fragments']; doc=v['document_id']
b=semantic_source_blocks(_candidate_fragments(fragments)); e=semantic_source_blocks(_evidence_fragments(fragments))
ctx={'snapshot_id':'snap-proof','source_sha256':x['source_hash']}
identity=_replay_identity(document_id=doc,model='recorded-proof',blocks=b,evidence_blocks=e,source_fragments=fragments,formation_context=ctx,field_contract_v3=True)
ctx['semantic_replay']=validated_inference_record(identity=identity,proposal=x['resolved_proposal'])
calls = []
raw_recorded = json.loads(x['provider_evidence']['response']['output_text'])
if args.bounded:
    from src.source_evidence_resolution_v1 import resolve_proposal_evidence
    resolved_recorded = resolve_proposal_evidence(raw_recorded, blocks=b, evidence_blocks=e, field_contract_v3=True)
    if resolved_recorded['objects'] != x['resolved_proposal']['objects'] or raw_recorded.get('relations'):
        raise ValueError('Bounded fixture replay requires the unchanged accepted object list and no cross-object relations')
def fail(*args): raise AssertionError('Offline proof must not call model')
def recorded_provider(_url, _headers, payload, _timeout):
    data = json.loads(payload['input'][1]['content'])
    task = data['formation_task']
    raw = raw_recorded
    objects = [obj for obj, resolved in zip(raw['objects'], x['resolved_proposal']['objects'])
               if all(any(t['block_id'] == span['block_id'] and t['start'] <= span['start'] < span['end'] <= t['end']
                          for t in task['selectable_ranges']) for span in resolved['spans'])]
    calls.append({'task_id': task['task_id'], 'phase': task['phase'], 'object_count': len(objects)})
    value = {'objects': objects, 'relations': [], 'source_assessments': [],
             'abstain_reason': None if objects else 'no_more_recorded_proposals'}
    return {'status': 'completed', 'output': [{'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}
if args.bounded:
    ctx.pop('semantic_replay')
spec=semantic_spec_from_fragments(document_id=doc,title='Smetten',family='smetten',class_='richtlijn',fragments=fragments,content_kind='pdf',api_key='offline-fixture' if args.bounded else '',model='recorded-proof',formation_context=ctx,field_contract_v3=True,post_json=recorded_provider if args.bounded else fail)
manifest={'canonical_source':{'source_id':fragments[0]['source_id'],'title':'Smetten','source_type':'pdf','source_url':'test','source_level':'national','canonicality':'canonical','integrity_status':'verified','source_checksum':x['source_hash'],'version':'1.0'}}
objects=transform(spec,manifest,fragments)
objects=apply_passage_register(apply_admission_gate(objects,klasse='richtlijn',fragments=fragments,document_version='1.0',source_hash=x['source_hash']))
p=partition(objects)
tasks=tasks_for(b,e)
from src.recommendation_coverage_v1 import assess
report={'recommendation_signals': dict(Counter(r['status'] for r in assess(b,x['resolved_proposal'])['entries'])), 'source_sha256':x['source_hash'],'method':'recorded proposals routed through bounded tasks' if args.bounded else 'offline reconstruction of recorded proposals',
 'limitation':'No live inference; no clinical completeness claim', 'fixture_calls': len(calls),
 'knowledge_count':len(p['knowledge']),'knowledge_types':dict(Counter(o.get('proposed_object_type') for o in p['knowledge'])),
 'formation_incomplete':(spec.get('_semantic_replay',{}).get('provider_evidence') or {}).get('formation_incomplete'),
 'admission':dict(Counter(o['metadata']['admission']['gate_result'] for o in p['knowledge'])),
 'blocked':[{'text':o['content']['clean_text'],'reasons':o['metadata']['admission']['reason_codes']} for o in p['knowledge'] if o['metadata']['admission']['gate_result']=='blocked'],
 'source_records':len(p['source']),'source_usage':dict(Counter(r['usage']['kind'] for r in p['source'])),
 'context_entries':sum(len(o['metadata'].get('source_bound_context',{}).get('entries',[])) for o in p['knowledge']),
 'tasks':len(tasks),'oversized_tasks':sum('error_code' in t for t in tasks),
 'max_candidate_chars':max(sum(len(b['text']) for b in t['source_blocks']) for t in tasks),
 'max_context_chars':max(sum(len(b['text']) for b in t['evidence_blocks']) for t in tasks)}
print(json.dumps(report,ensure_ascii=False,indent=2))
open(args.output,'w').write(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
