"""Native evidence fact must agree with actual confirmed support."""
import json
from pathlib import Path
import pytest
from tests.ko4_native_adversary_tmp import seed,approval,state,target_now,YES
from tests.semantic_fixture_support import install_fixture_history
from src.operations_console_v1 import ConsoleError
from src.integrity_kernel import stamp_canonical_hashes
from src.knowledge_relations_v1 import build_knowledge_relation,canonicalize_knowledge_relation_set
from src.review.knowledge_relation_review_v1 import relation_choice_value,legacy_confirmed_mirror

@pytest.mark.parametrize('scenario',['first_contradiction','second_contradiction','linked_false_positive','no_link_na_positive'])
def test_native_evidence_choice_agrees_with_confirmed_support(tmp_path,production_console,scenario):
 c,sid,_,actors,rows=seed(tmp_path,production_console,policy=scenario=='second_contradiction')
 relation=None
 if scenario!='no_link_na_positive':
  for row,typ in [(rows[0],'definition'),(rows[1],'explanation')]:
   c.confirm_object_type(actor_id=actors[0]['account_id'],snapshot_id=sid,object_id=row['object_id'],confirmed_object_type=typ,expected_revision=c.objects_revision(sid))
  history=c._load_objects(sid);claim=next(o for o in reversed(history) if o['object_id']==rows[0]['object_id']);peer=target_now(c,sid,rows[1]['object_id'])
  relation=build_knowledge_relation(source_object_id=claim['object_id'],source_object_version=claim['object_version'],relation_type='supported_by',target_object_id=peer['object_id'],target_object_version=peer['object_version'])
  selected=canonicalize_knowledge_relation_set([relation],source_object_id=claim['object_id'],source_object_version=claim['object_version'])
  claim['confirmed_knowledge_relations']=selected;claim['confirmed_relations']=legacy_confirmed_mirror(selected);stamp_canonical_hashes(claim)
  install_fixture_history(c,sid,history)
 current=target_now(c,sid,rows[0]['object_id'])
 if scenario=='second_contradiction':
  approval(c,sid,current,actors[0],assessment=YES,evidence_not_applicable=False,relation_review_ack=True,relation_choices=[relation_choice_value(relation)])
  current=target_now(c,sid,current['object_id'])
 before=state(c,sid)
 output={'sha':'2621773f545bf61816125a4028f0e3d3e53724a4','scenario':scenario,'has_confirmed_support':relation is not None,'explicit_na':scenario!='linked_false_positive'}
 try:
  if scenario=='second_contradiction':
   c.approve_second_review(actor_id=actors[1]['account_id'],snapshot_id=sid,object_id=current['object_id'],assessment=YES,evidence_not_applicable=True,expected_revision=c.objects_revision(sid))
  else:
   approval(c,sid,current,actors[0],assessment=YES,evidence_not_applicable=scenario!='linked_false_positive',relation_review_ack=True,relation_choices=[relation_choice_value(relation)] if relation else [])
 except ConsoleError as e: output.update(result='REFUSED',code=e.code,unchanged=state(c,sid)==before)
 else:
  bindings=[b for b in c.object_review_bindings(sid) if b.get('valid') and b['object_id']==current['object_id']]
  output.update(result='APPROVED',stored_facts=[b.get('supporting_evidence') for b in bindings])
 Path('/tmp/ko4-evidence-contradiction-262-'+scenario+'.json').write_text(json.dumps(output,indent=2));print(json.dumps(output))
 if scenario.endswith('contradiction'):
  assert output['result']=='REFUSED','Explicit N/A contradicts confirmed linked support but native approval accepted it'
  assert output['unchanged']
 else:
  assert output['result']=='APPROVED'
  expected='linked' if relation else 'not_applicable'
  assert output['stored_facts']==[{'version':'ko-supporting-evidence-v1','applicability':expected}]
