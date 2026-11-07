"""Independent actual current boom candidate admission probe."""
import json
from pathlib import Path
import pytest
from src.operations_console_v1 import ConsoleError
from src.review.knowledge_object_state_v1 import derive_ko_state,is_knowledge_object
from tests.ko4_native_adversary_tmp import state,YES,target_now
from tests.test_decision_graph_chain import ingest,complete_graph,command
from tests.test_v225_beslisboom_path import _console,_accounts,_ingest_boom

@pytest.mark.parametrize('mode',['unresolved_pdf','resolved_pdf','historical_html','structural_conversion'])
def test_existing_boom_candidate_is_not_the_conversion_exception(tmp_path,production_console,mode):
 c=_console(tmp_path,production_console=production_console); actors=_accounts(c)
 sid=(ingest(c,actors) if mode.endswith('pdf') else _ingest_boom(c,actors))['snapshot_id']
 if mode=='resolved_pdf': c.update_decision_graph(**command(c,actors,sid,'independent-resolve',graph=complete_graph(c,sid)))
 from src.review.review_duty_v1 import authoritative_review_type
 objects=c.snapshot_objects(sid)
 row=next(o for o in objects if authoritative_review_type(o)==('path' if mode=='structural_conversion' else 'node'))
 facts=derive_ko_state(row,review_path='boom',bindings=c.object_review_bindings(sid),fragments=c.review_source_fragments(sid))
 before=state(c,sid)
 outcome={'sha':'5b8fa397047dcbbd4becf5b0ab5f644dd380a898','mode':mode,'before_state':facts,'before_is_ko':is_knowledge_object(row,'boom'),'admission':row.get('metadata',{}).get('admission')}
 try:
  c.review_object(actor_id=actors['researcher']['account_id'],snapshot_id=sid,object_id=row['object_id'],decision='approve',
    confirmed_object_type='node',type_action='type_wijzigen' if mode=='structural_conversion' else 'dit_klopt',assessment=YES,evidence_not_applicable=True,expected_revision=c.objects_revision(sid))
 except ConsoleError as e:
  outcome.update(result='REFUSED',code=e.code,unchanged=state(c,sid)==before)
 else:
  saved=target_now(c,sid,row['object_id']);outcome.update(result='APPROVED',after_state=derive_ko_state(saved,review_path='boom',bindings=c.object_review_bindings(sid),fragments=c.review_source_fragments(sid)))
 Path('/tmp/ko4-boom-candidate-5b8-'+mode+'.json').write_text(json.dumps(outcome,indent=2));print(json.dumps(outcome))
 if mode=='unresolved_pdf':
  assert outcome['before_is_ko'] and facts['state']=='Kandidaat'
  assert outcome['result']=='REFUSED', 'Existing blocked boomKO Kandidaat can approve while only true nonKO conversion should be exempt'
  assert outcome['unchanged']
 else:
  assert outcome['result']=='APPROVED'
