"""Compare source ordering on a recorded export without provider calls or source re-extraction."""
import argparse,csv,io,json,re,sys
from pathlib import Path
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.vorming.semantic_passage_v1 import semantic_source_blocks
from src.vorming.bounded_formation_v1 import tasks_for,_durable_targets
from src.vorming.recommendation_task_plan_v1 import build_plan,remaining_tasks
from src.vorming.semantic_replay_v1 import stable_json_hash
csv.field_size_limit(64000000)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence-zip',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
path=args.evidence_zip
with ZipFile(path) as z:
    rows=list(csv.DictReader(io.StringIO(z.read('attempt_diagnostics.csv').decode('utf-8-sig'))))
data=json.loads(rows[0]['diagnostic'])['validator_input']
blocks=semantic_source_blocks(data['fragments']); evidence=semantic_source_blocks(data['evidence_fragments'])
targets=_durable_targets(blocks,{'objects':[],'source_assessments':[]})
original=tasks_for(blocks,evidence,targets)
plan=build_plan(original,blocks,evidence)
planned=remaining_tasks(plan,blocks,evidence,targets)
expected=sorted((r['span']['block_id'],r['span']['start'],r['span']['end']) for r in targets)
actual=sorted((s['block_id'],s['start'],s['end']) for t in planned for s in t['target_spans'])
assert expected==actual
reference=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/smetten-reference.json').read_text())
normalize=lambda text: re.sub(r'\s+',' ',text).strip()
known=[r['text'] for m in reference['modules'] for r in m['recs']]
match=[]
for text in known:
    owners=[b['block_id'] for b in blocks if normalize(text) in normalize(b['text'])]
    old=[i+1 for i,t in enumerate(original) if any(s['block_id'] in owners for s in t['target_spans'])]
    new=[i+1 for i,t in enumerate(planned) if any(s['block_id'] in owners for s in t['target_spans'])]
    match.append({'source_match':bool(owners),'old_task_positions':old,'new_task_positions':new})
report={'fixture':'recorded Smetten validator input; independent smetten-reference.json',
    'validator_input_hash':stable_json_hash(data),'content_fragments':len(data['fragments']),
    'evidence_fragments':len(data['evidence_fragments']),'tasks':len(planned),
    'possible_recommendation_count':len(plan['possible_recommendations']),
    'first_planned_task_original_position':plan['tasks'][0]['source_order'],
    'priority_task_count':sum(t['priority']=='possible_recommendation' for t in plan['tasks']),
    'coverage_exact':True,'independent_reference_recommendations':len(known),'matches':match,
    'scope':'offline ordering/source-reference proof; no provider, automatic selection or clinical acceptance claim'}
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
