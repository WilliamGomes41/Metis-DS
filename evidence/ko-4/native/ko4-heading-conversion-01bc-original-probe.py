"""Actual structural approval must not transfer clinical approval to new KO."""
import json,os
from pathlib import Path
import pytest
from tests.test_v215_ingest_date_version_review_lanes import _console,_accounts,_ingest
from tests.ko4_native_adversary_tmp import state,target_now,seed,approval,YES
from src.operations_console_v1 import ConsoleError
from src.review.knowledge_object_state_v1 import is_knowledge_object
from src.review.four_eyes_v1 import requires_four_eyes

@pytest.mark.parametrize('mode',['heading_to_exception','existing_ko_type_change','structural_only'])
def test_type_change_cannot_inherit_structural_approval(tmp_path,production_console,mode):
 baseline=os.environ.get('KO4_HEADING_BASELINE')=='1'; label='base837' if baseline else '01bc'
 if mode=='existing_ko_type_change':
  c,sid,_,reviewers,rows=seed(tmp_path,production_console); actor=reviewers[0]['account_id']; row=rows[0]
  approval(c,sid,row,reviewers[0],**({} if baseline else {'assessment':YES,'evidence_not_applicable':True}))
 else:
  c=_console(tmp_path,production_console=production_console);actors=_accounts(c);actor=actors['reviewer']['account_id']
  sid=_ingest(c,actors,data=b'<!doctype html><html lang="nl"><body><h1>Tenzij samen met de cli\xc3\xabnt hiervan wordt afgezien</h1></body></html>',filename='reclass.html',title='Independent heading classification')['snapshot_id']
  row=next(o for o in c.snapshot_objects(sid) if o['object_type']=='heading')
  c.batch_confirm_headings(actor_id=actor,snapshot_id=sid,object_ids=[row['object_id']])
 previous=target_now(c,sid,row['object_id']);before=state(c,sid)
 output={'sha':'837b115f213bcfd0e9f4a71a1010231d2040365e' if baseline else '01bcfa173d904d7b1b1711bc2d23c22479e88a05','mode':mode,'before_version':previous['object_version'],'before_validation':previous['governance']['validation_status'],'before_is_ko':is_knowledge_object(previous,'richtlijn')}
 confirmed='heading' if mode=='structural_only' else 'exception'
 try: c.confirm_object_type(actor_id=actor,snapshot_id=sid,object_id=row['object_id'],confirmed_object_type=confirmed,expected_revision=c.objects_revision(sid))
 except ConsoleError as e: output.update(result='REFUSED',code=e.code,unchanged=state(c,sid)==before)
 else:
  fresh=target_now(c,sid,row['object_id']);bindings=[b for b in c.object_review_bindings(sid) if b['object_id']==row['object_id']]
  output.update(result='SAVED',after_version=fresh['object_version'],after_validation=fresh['governance']['validation_status'],after_is_ko=is_knowledge_object(fresh,'richtlijn'),requires_four_eyes=requires_four_eyes(fresh,confirmed_type=confirmed),valid_bindings=[b for b in bindings if b.get('valid')],publication=fresh['governance']['publication_status'])
 Path('/tmp/ko4-heading-conversion-'+label+'-'+mode+'.json').write_text(json.dumps(output,indent=2));print(json.dumps(output))
 assert output['result']=='SAVED','Supported type confirmation should create open KO instead of rejecting structurally approved predecessor'
 if mode=='structural_only':assert not output['after_is_ko']
 else:
  assert output['after_version']!=output['before_version']
  assert output['after_validation']=='needs_review','Structural/type approval must not become clinical approval for a new KO'
  assert output['requires_four_eyes'] is True
  assert output['valid_bindings']==[]
  assert output['publication']=='unpublished'
