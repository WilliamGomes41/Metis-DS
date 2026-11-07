"""Independent native boom retry, exact replay versus fresh bad facts."""
import json,os
from pathlib import Path
import pytest
from tests.test_v225_beslisboom_path import _console,_accounts,_ingest_boom
from tests.test_explicit_review_policy import policy
from tests.ko4_native_adversary_tmp import state,YES,target_now
from src.operations_console_v1 import ConsoleError
from src.review.review_duty_v1 import authoritative_review_type
from src.review.knowledge_object_state_v1 import derive_ko_state
from src.review.review_interaction_v1 import build_review_interaction_evidence
from src.review.review_assessment_v1 import ReviewAssessment

@pytest.mark.parametrize('participation',[None,'required'])
@pytest.mark.parametrize('retry',['exact','negative','conflict'])
def test_boom_successful_approval_exact_replay_is_noop(tmp_path,production_console,participation,retry):
 c=_console(tmp_path,production_console=production_console);actors=_accounts(c)
 from tests.test_decision_graph_chain import ingest,complete_graph,command
 sid=ingest(c,actors,participation)['snapshot_id']
 c.update_decision_graph(**command(c,actors,sid,'independent-valid-graph',graph=complete_graph(c,sid)))
 row=next(o for o in c.snapshot_objects(sid) if authoritative_review_type(o)=='node' and not o.get('scorelist'))
 baseline=os.environ.get('KO4_REPLAY_BASELINE')=='1'
 def call(**extra):
  return c.review_object(actor_id=actors['researcher']['account_id'],snapshot_id=sid,object_id=row['object_id'],decision='approve',confirmed_object_type='node',type_action='dit_klopt',expected_revision=c.objects_revision(sid),**extra)
 initial={} if baseline else {'assessment':YES,'evidence_not_applicable':True}
 call(**initial)
 current=target_now(c,sid,row['object_id']);before=state(c,sid)
 facts=derive_ko_state(current,review_path='boom',bindings=c.object_review_bindings(sid),fragments=c.review_source_fragments(sid))
 extra=dict(initial)
 if retry=='negative':extra['assessment']={**YES,'complete':'adjust'}
 if retry=='conflict':
  extra['interaction_evidence']=build_review_interaction_evidence(interaction_id='ri_native-boom-replay-conflict',interaction_kind='contextual',reviewer_account_id=actors['researcher']['account_id'],snapshot_id=sid,review_stage='first_review',focal=current,objects=c.snapshot_objects(sid),review_path='boom',assessment=ReviewAssessment.from_evidence({**YES,'complete':'adjust'}))
 label='base837' if baseline else '01bc'
 output={'source_sha':'837b115f213bcfd0e9f4a71a1010231d2040365e' if baseline else '01bcfa173d904d7b1b1711bc2d23c22479e88a05','source_label':label,'participation':participation,'retry':retry,'before_state':facts}
 try:call(**extra)
 except ConsoleError as e:output.update(result='REFUSED',code=e.code,unchanged=state(c,sid)==before)
 else:output.update(result='ACCEPTED',unchanged=state(c,sid)==before)
 Path('/tmp/ko4-boom-replay-'+label+'-'+str(participation)+'-'+retry+'.json').write_text(json.dumps(output,indent=2));print(json.dumps(output))
 if retry=='exact':
  assert output['result']=='ACCEPTED','Exact successful native boom approval retry must not become refused transition'
  if not baseline:assert output['unchanged'],'Exact native replay must not write objects/bindings/envelope/events/source'
 else:
  assert output['result']=='REFUSED'
  assert output['unchanged']
